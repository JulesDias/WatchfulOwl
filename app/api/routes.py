import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.collectors.github_collector import _repo_to_signal
from app.config import get_settings
from app.database import get_session
from app.models import Signal
from app.processing.pipeline import run_collection_cycle
from app.processing.deduplicate import compute_fingerprint
from app.processing.extract import enrich_signal
from app.processing.score import score_signal
from app.schemas import CollectionSummary, GitHubRepoAddRequest, SignalRead, StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter()

GITHUB_REPO_REFERENCE_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<url_owner>[A-Za-z0-9_.-]+)/"
    r"(?P<url_repo>[A-Za-z0-9_.-]+)(?:[/?#].*)?$|"
    r"^(?P<short_owner>[A-Za-z0-9_.-]+)/(?P<short_repo>[A-Za-z0-9_.-]+)$"
)


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}


@router.get("/signals", response_model=list[SignalRead])
async def list_signals(
    limit: int = Query(default=50, ge=1, le=500),
    source_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    is_favorite: bool | None = None,
    unread: bool | None = None,
    min_score: int | None = Query(default=None, ge=0),
    q: str | None = None,
    session: Session = Depends(get_session),
) -> list[SignalRead]:
    statement = select(Signal).where(Signal.deleted_at.is_(None))
    if source_type:
        statement = statement.where(Signal.source_type == source_type)
    if severity:
        statement = statement.where(Signal.severity == severity)
    if status:
        statement = statement.where(Signal.status == status)
    if is_favorite is not None:
        statement = statement.where(Signal.is_favorite == is_favorite)
    if unread:
        statement = statement.where(Signal.status != "reviewed")
    if min_score is not None:
        statement = statement.where(Signal.score >= min_score)
    if q:
        like = f"%{q}%"
        statement = statement.where(or_(Signal.title.ilike(like), Signal.content.ilike(like)))
    statement = statement.order_by(Signal.collected_at.desc()).limit(limit)
    signals = session.exec(statement).all()
    return [_to_signal_read(signal) for signal in signals]


@router.get("/signals/{signal_id}", response_model=SignalRead)
async def get_signal(signal_id: int, session: Session = Depends(get_session)) -> SignalRead:
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _to_signal_read(signal)


@router.post("/signals/{signal_id}/read", response_model=SignalRead)
async def mark_signal_read(signal_id: int, session: Session = Depends(get_session)) -> SignalRead:
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.status = "reviewed"
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return _to_signal_read(signal)


@router.post("/signals/{signal_id}/favorite", response_model=SignalRead)
async def toggle_signal_favorite(
    signal_id: int,
    session: Session = Depends(get_session),
) -> SignalRead:
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.is_favorite = not signal.is_favorite
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return _to_signal_read(signal)


@router.post("/signals/{signal_id}/delete", response_model=SignalRead)
async def delete_signal(signal_id: int, session: Session = Depends(get_session)) -> SignalRead:
    """Soft delete a signal (move to trash)."""
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Signal is already deleted")
    
    signal.deleted_at = datetime.now(timezone.utc)
    session.add(signal)
    session.commit()
    session.refresh(signal)
    logger.info("Deleted signal: %s", signal.title)
    return _to_signal_read(signal)


@router.post("/signals/{signal_id}/restore", response_model=SignalRead)
async def restore_signal(signal_id: int, session: Session = Depends(get_session)) -> SignalRead:
    """Restore a deleted signal from trash."""
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.deleted_at is None:
        raise HTTPException(status_code=400, detail="Signal is not deleted")
    
    signal.deleted_at = None
    session.add(signal)
    session.commit()
    session.refresh(signal)
    logger.info("Restored signal: %s", signal.title)
    return _to_signal_read(signal)


@router.get("/trash", response_model=list[SignalRead])
async def list_trash(
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[SignalRead]:
    """List all deleted signals in trash."""
    statement = (
        select(Signal)
        .where(Signal.deleted_at.isnot(None))
        .order_by(Signal.deleted_at.desc())
        .limit(limit)
    )
    signals = session.exec(statement).all()
    return [_to_signal_read(signal) for signal in signals]


@router.post("/trash/{signal_id}/purge")
async def purge_signal(signal_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Permanently delete a signal from trash."""
    signal = session.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.deleted_at is None:
        raise HTTPException(status_code=400, detail="Signal is not in trash")
    
    title = signal.title
    session.delete(signal)
    session.commit()
    logger.info("Permanently purged signal: %s", title)
    return {"status": "deleted", "signal_id": signal_id, "title": title}


@router.post("/trash/purge-all")
async def purge_all_trash(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Permanently delete all signals in trash."""
    statement = select(Signal).where(Signal.deleted_at.isnot(None))
    deleted_signals = session.exec(statement).all()
    count = len(deleted_signals)
    
    for signal in deleted_signals:
        session.delete(signal)
    
    session.commit()
    logger.info("Purged %d signals from trash", count)
    return {"status": "purged", "count": count}


@router.get("/alerts", response_model=list[SignalRead])
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[SignalRead]:
    settings = get_settings()
    statement = (
        select(Signal)
        .where(or_(Signal.status == "alerted", Signal.score >= settings.alert_score_threshold))
        .order_by(Signal.score.desc(), Signal.collected_at.desc())
        .limit(limit)
    )
    signals = session.exec(statement).all()
    return [_to_signal_read(signal) for signal in signals]


@router.get("/stats", response_model=StatsResponse)
async def stats(session: Session = Depends(get_session)) -> StatsResponse:
    settings = get_settings()
    signals = session.exec(select(Signal)).all()
    source_counter = Counter(signal.source_type for signal in signals)
    severity_counter = Counter(signal.severity for signal in signals)
    keyword_counter: Counter[str] = Counter()
    product_counter: Counter[str] = Counter()

    for signal in signals:
        keyword_counter.update(_json_list(signal.keywords))
        product_counter.update(_json_list(signal.products))

    total_alerts = sum(
        1
        for signal in signals
        if signal.status == "alerted" or signal.score >= settings.alert_score_threshold
    )
    return StatsResponse(
        total_signals=len(signals),
        total_alerts=total_alerts,
        count_by_source_type=dict(source_counter),
        count_by_severity=dict(severity_counter),
        top_keywords=keyword_counter.most_common(10),
        top_products=product_counter.most_common(10),
    )


@router.post("/collect/run", response_model=CollectionSummary)
async def run_collect(session: Session = Depends(get_session)) -> CollectionSummary:
    return await run_collection_cycle(session=session)


@router.post("/github/add", response_model=SignalRead)
async def add_github_repo(
    payload: GitHubRepoAddRequest | None = Body(default=None),
    repo_url: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> SignalRead:
    """Add a GitHub repository manually from a URL or owner/repo reference."""
    settings = get_settings()
    raw_repo = payload.repo_url if payload else repo_url
    if not raw_repo:
        raise HTTPException(status_code=422, detail="Missing repo_url")

    owner, repo_name = _parse_github_repo_reference(raw_repo)
    repo_data = await _fetch_github_repo(owner, repo_name, settings)
    signal_create = _repo_to_signal(repo_data)
    signal = Signal(**signal_create.model_dump())

    enrich_signal(signal)
    score_signal(signal)
    signal.fingerprint = compute_fingerprint(signal)

    existing = session.exec(
        select(Signal).where(Signal.fingerprint == signal.fingerprint)
    ).first()
    if existing:
        logger.info("GitHub repo already exists: %s", existing.title)
        return _to_signal_read(existing)

    session.add(signal)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(Signal).where(Signal.fingerprint == signal.fingerprint)
        ).first()
        if existing:
            return _to_signal_read(existing)
        raise HTTPException(status_code=409, detail="Repository already added") from None

    session.refresh(signal)
    logger.info("Manually added GitHub repo: %s", signal.title)
    return _to_signal_read(signal)


def _parse_github_repo_reference(value: str) -> tuple[str, str]:
    reference = value.strip()
    if reference.startswith("git@github.com:"):
        reference = reference.replace("git@github.com:", "", 1)
    reference = reference.removesuffix(".git").rstrip("/")

    match = GITHUB_REPO_REFERENCE_PATTERN.match(reference)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository. Use https://github.com/owner/repo or owner/repo.",
        )

    owner = match.group("url_owner") or match.group("short_owner")
    repo_name = match.group("url_repo") or match.group("short_repo")
    return owner, repo_name.removesuffix(".git")


async def _fetch_github_repo(owner: str, repo_name: str, settings: Any) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds, headers=headers) as client:
            response = await client.get(f"https://api.github.com/repos/{owner}/{repo_name}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="GitHub repository not found")
            if response.status_code in {403, 429}:
                logger.warning("GitHub API rate/access limit while adding %s/%s", owner, repo_name)
                raise HTTPException(
                    status_code=502,
                    detail="GitHub API rate limit or access error. Try again later.",
                )
            response.raise_for_status()
            payload = response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning("GitHub API error while adding %s/%s: %s", owner, repo_name, exc)
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API error: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("GitHub request failed while adding %s/%s: %s", owner, repo_name, exc)
        raise HTTPException(status_code=502, detail="Failed to reach GitHub API") from exc
    except ValueError as exc:
        logger.warning("GitHub API returned invalid JSON for %s/%s: %s", owner, repo_name, exc)
        raise HTTPException(status_code=502, detail="Invalid GitHub API response") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Invalid GitHub API response")
    return payload


def _to_signal_read(signal: Signal) -> SignalRead:
    return SignalRead(
        id=signal.id or 0,
        source=signal.source,
        source_type=signal.source_type,
        title=signal.title,
        content=signal.content,
        url=signal.url,
        author=signal.author,
        published_at=signal.published_at,
        collected_at=signal.collected_at,
        cves=_json_list(signal.cves),
        keywords=_json_list(signal.keywords),
        products=_json_list(signal.products),
        github_links=_json_list(signal.github_links),
        github_stars=signal.github_stars,
        score=signal.score,
        confidence=signal.confidence,
        severity=signal.severity,
        status=signal.status,
        is_favorite=signal.is_favorite,
        fingerprint=signal.fingerprint,
    )


def _json_list(value: str) -> list[str]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    return []
