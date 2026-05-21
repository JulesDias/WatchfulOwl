import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.alerts.discord import send_discord_alert
from app.collectors.base import BaseCollector
from app.collectors.github_collector import GitHubCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.x_collector import XCollector
from app.config import Settings, get_settings
from app.database import engine
from app.models import Signal
from app.processing.deduplicate import compute_fingerprint, fingerprint_exists
from app.processing.extract import enrich_signal
from app.processing.score import score_signal
from app.schemas import CollectionSummary, SignalCreate

logger = logging.getLogger(__name__)


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
        raw_signals = await _collect_all(collectors)
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
    return collectors


async def _collect_all(collectors: list[BaseCollector]) -> list[SignalCreate]:
    raw_signals: list[SignalCreate] = []
    for collector in collectors:
        try:
            collected = await collector.collect()
        except Exception:
            logger.exception("Collector %s failed", collector.source_type)
            continue
        logger.info("Collector %s produced %s signals", collector.source_type, len(collected))
        raw_signals.extend(collected)
    return raw_signals
