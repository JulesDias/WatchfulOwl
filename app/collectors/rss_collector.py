import calendar
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.collectors.base import BaseCollector
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


@dataclass
class FeedResult:
    feed_url: str
    signals: list[SignalCreate]


class RSSCollector(BaseCollector):
    source_type = "rss"

    def __init__(
        self,
        feed_urls: list[str],
        max_results: int,
        timeout_seconds: float,
        max_concurrent_feeds: int = 5,
    ) -> None:
        super().__init__(max_results=max_results)
        self.feed_urls = feed_urls
        self.timeout_seconds = timeout_seconds
        self.max_concurrent_feeds = max(1, max_concurrent_feeds)

    async def collect(self) -> list[SignalCreate]:
        if not self.feed_urls or self.max_results <= 0:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrent_feeds)
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            results = await asyncio.gather(
                *[
                    self._collect_feed(client, feed_url, semaphore)
                    for feed_url in self.feed_urls
                ]
            )

        signals = _round_robin_signals([result.signals for result in results], self.max_results)
        logger.info("RSS collector returned %s signals", len(signals))
        return signals

    async def _collect_feed(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
        semaphore: asyncio.Semaphore,
    ) -> FeedResult:
        async with semaphore:
            try:
                response = await client.get(feed_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("RSS fetch failed for %s: %s", feed_url, exc)
                return FeedResult(feed_url=feed_url, signals=[])

            parsed = feedparser.parse(response.content)
            if parsed.bozo:
                logger.warning("RSS parse warning for %s: %s", feed_url, parsed.bozo_exception)

            feed_title = parsed.feed.get("title", feed_url)
            signals = [
                SignalCreate(
                    source=feed_title,
                    source_type=self.source_type,
                    title=_clean_text(entry.get("title", "Untitled RSS entry")),
                    content=_entry_content(entry),
                    url=entry.get("link"),
                    author=entry.get("author"),
                    published_at=_entry_datetime(entry),
                )
                for entry in parsed.entries
            ]
            return FeedResult(feed_url=feed_url, signals=signals)


def _round_robin_signals(
    feed_signals: list[list[SignalCreate]],
    max_results: int,
) -> list[SignalCreate]:
    signals: list[SignalCreate] = []
    max_feed_size = max((len(signals) for signals in feed_signals), default=0)
    for index in range(max_feed_size):
        for source_signals in feed_signals:
            if index >= len(source_signals):
                continue
            signals.append(source_signals[index])
            if len(signals) >= max_results:
                return signals
    return signals


def _entry_content(entry: Any) -> str:
    if entry.get("summary"):
        return _clean_text(entry.get("summary", ""))
    content = entry.get("content")
    if isinstance(content, list) and content:
        return _clean_text(content[0].get("value", ""))
    if entry.get("description"):
        return _clean_text(entry.get("description", ""))
    return ""


def _entry_datetime(entry: Any) -> datetime | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _clean_text(value: str) -> str:
    return " ".join(value.split())
