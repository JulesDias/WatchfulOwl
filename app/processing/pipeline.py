import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.alerts.discord import send_discord_alert
from app.collectors.base import BaseCollector
from app.collectors.github_collector import GitHubCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.x_feed_collector import XFeedCollector
from app.collectors.x_collector import XCollector
from app.collectors.snscrape_collector import SnscrapeCollector
from app.config import Settings, get_settings
from app.database import engine
from app.models import CollectionRun, Signal
from app.processing.deduplicate import compute_fingerprint, fingerprint_exists
from app.processing.extract import enrich_signal
from app.processing.score import score_signal
from app.schemas import CollectionSummary, SignalCreate

logger = logging.getLogger(__name__)


@dataclass
class CollectorResult:
    source: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    success: bool
    signals: list[SignalCreate]
    error_message: str | None = None


async def run_collection_cycle(
    session: Session | None = None,
    settings: Settings | None = None,
) -> CollectionSummary:
    settings = settings or get_settings()
    owns_session = session is None
    if session is None:
        session = Session(engine)

    summary = CollectionSummary()
    try:
        collectors = build_collectors(settings)
        logger.info(
            "Starting collection cycle with collectors: %s",
            ", ".join(collector.source_type for collector in collectors) or "none",
        )
        raw_signals = await _collect_all(collectors, session=session, settings=settings)
        summary.collected = len(raw_signals)

        for raw_signal in raw_signals:
            signal = Signal(**raw_signal.model_dump())
            enrich_signal(signal)
            score_signal(signal)
            fingerprint = compute_fingerprint(signal)

            if fingerprint_exists(session, fingerprint):
                summary.duplicates += 1
                logger.info("Duplicate signal ignored: %s", signal.title)
                continue

            session.add(signal)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                summary.duplicates += 1
                logger.info("Duplicate signal ignored after unique constraint: %s", signal.title)
                continue

            session.refresh(signal)
            summary.new += 1

            if signal.score >= settings.alert_score_threshold:
                try:
                    sent = await send_discord_alert(signal, settings=settings)
                    if sent:
                        signal.status = "alerted"
                        session.add(signal)
                        session.commit()
                        summary.alerted += 1
                except Exception as exc:
                    logger.error("Failed to send Discord alert for signal %s: %s", signal.id, exc)
                    # Don't fail entire collection cycle if Discord alert fails

        logger.info(
            "Collection cycle done: collected=%s new=%s duplicates=%s alerted=%s",
            summary.collected,
            summary.new,
            summary.duplicates,
            summary.alerted,
        )
        return summary
    finally:
        if owns_session:
            session.close()


def build_collectors(settings: Settings) -> list[BaseCollector]:
    collectors: list[BaseCollector] = []
    if settings.enable_rss:
        collectors.append(
            RSSCollector(
                feed_urls=settings.rss_feed_urls,
                max_results=settings.max_results_per_source,
                timeout_seconds=settings.http_timeout_seconds,
                max_concurrent_feeds=settings.rss_feed_concurrency,
            )
        )
    if settings.enable_github:
        collectors.append(
            GitHubCollector(
                token=settings.github_token,
                max_results=settings.max_results_per_source,
                timeout_seconds=settings.http_timeout_seconds,
                min_stars=settings.github_min_stars,
            )
        )
    if settings.enable_x:
        collectors.append(
            XCollector(
                bearer_token=settings.x_bearer_token,
                max_results=settings.max_results_per_source,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    if settings.enable_x_snscrape:
        collectors.append(
            SnscrapeCollector(
                max_results=settings.max_results_per_source,
                queries=settings.x_snscrape_queries,
                min_interest_terms=settings.x_snscrape_min_interest_terms,
            )
        )
    if settings.enable_x_feed:
        collectors.append(
            XFeedCollector(
                feed_urls=settings.x_feed_urls,
                max_results=settings.max_results_per_source,
                timeout_seconds=settings.http_timeout_seconds,
                min_interest_terms=settings.x_feed_min_interest_terms,
            )
        )
    return collectors


async def _collect_all(
    collectors: list[BaseCollector],
    session: Session,
    settings: Settings,
) -> list[SignalCreate]:
    results = await _run_collectors(collectors, settings)
    _record_collection_runs(session, results)

    raw_signals: list[SignalCreate] = []
    for result in results:
        if not result.success:
            continue
        logger.info("Collector %s produced %s signals", result.source, len(result.signals))
        raw_signals.extend(result.signals)
    return raw_signals


async def _run_collectors(
    collectors: list[BaseCollector],
    settings: Settings,
) -> list[CollectorResult]:
    semaphore = asyncio.Semaphore(settings.max_concurrent_collectors)

    async def run_one(collector: BaseCollector) -> CollectorResult:
        async with semaphore:
            started_at = datetime.now(timezone.utc)
            signals: list[SignalCreate] = []
            error_message: str | None = None
            success = False
            try:
                signals = await asyncio.wait_for(
                    collector.collect(),
                    timeout=settings.collector_timeout_seconds,
                )
                success = True
            except TimeoutError:
                error_message = (
                    f"Collector exceeded {settings.collector_timeout_seconds:.1f}s timeout"
                )
                logger.warning("Collector %s timed out", collector.source_type)
            except Exception as exc:
                error_message = str(exc) or exc.__class__.__name__
                logger.exception("Collector %s failed", collector.source_type)

            finished_at = datetime.now(timezone.utc)
            return CollectorResult(
                source=collector.source_type,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                success=success,
                signals=signals,
                error_message=_truncate_error(error_message),
            )

    return await asyncio.gather(*(run_one(collector) for collector in collectors))


def _record_collection_runs(session: Session, results: list[CollectorResult]) -> None:
    if not results:
        return

    for result in results:
        session.add(
            CollectionRun(
                source=result.source,
                started_at=result.started_at,
                finished_at=result.finished_at,
                duration_ms=result.duration_ms,
                success=result.success,
                collected_count=len(result.signals) if result.success else 0,
                error_message=result.error_message,
            )
        )

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist collection run metadata")


def _truncate_error(error_message: str | None, max_length: int = 1000) -> str | None:
    if error_message is None or len(error_message) <= max_length:
        return error_message
    return f"{error_message[: max_length - 3]}..."
