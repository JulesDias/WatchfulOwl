import calendar
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.collectors.base import BaseCollector
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    source_type = "rss"

    def __init__(
        self,
        feed_urls: list[str],
        max_results: int,
        timeout_seconds: float,
    ) -> None:
        super().__init__(max_results=max_results)
        self.feed_urls = feed_urls
        self.timeout_seconds = timeout_seconds

    async def collect(self) -> list[SignalCreate]:
        signals: list[SignalCreate] = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for feed_url in self.feed_urls:
                if len(signals) >= self.max_results:
                    break
                try:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("RSS fetch failed for %s: %s", feed_url, exc)
                    continue

                parsed = feedparser.parse(response.content)
                if parsed.bozo:
                    logger.warning("RSS parse warning for %s: %s", feed_url, parsed.bozo_exception)

                feed_title = parsed.feed.get("title", feed_url)
                for entry in parsed.entries:
                    if len(signals) >= self.max_results:
                        break
                    title = _clean_text(entry.get("title", "Untitled RSS entry"))
                    content = _entry_content(entry)
                    signals.append(
                        SignalCreate(
                            source=feed_title,
                            source_type=self.source_type,
                            title=title,
                            content=content,
                            url=entry.get("link"),
                            author=entry.get("author"),
                            published_at=_entry_datetime(entry),
                        )
                    )

        logger.info("RSS collector returned %s signals", len(signals))
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
