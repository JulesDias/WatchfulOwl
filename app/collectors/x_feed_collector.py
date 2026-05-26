import calendar
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.collectors.base import BaseCollector
from app.processing.extract import (
    extract_cves,
    extract_github_links,
    extract_keywords,
    extract_products,
)
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


class XFeedCollector(BaseCollector):
    """Collect tweet-like posts from user-provided RSS/Atom feeds.

    This collector intentionally does not scrape x.com directly, does not use
    cookies, and does not bypass anti-bot controls. It consumes feeds exposed by
    services the operator has chosen and is allowed to use.
    """

    source_type = "x_feed"

    def __init__(
        self,
        feed_urls: list[str],
        max_results: int,
        timeout_seconds: float,
        min_interest_terms: int = 1,
    ) -> None:
        super().__init__(max_results=max_results)
        self.feed_urls = feed_urls
        self.timeout_seconds = timeout_seconds
        self.min_interest_terms = max(1, min_interest_terms)

    async def collect(self) -> list[SignalCreate]:
        if not self.feed_urls:
            logger.info("X feed collector disabled: no X_FEED_URLS configured")
            return []

        signals: list[SignalCreate] = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for feed_url in self.feed_urls:
                if len(signals) >= self.max_results:
                    break
                signals.extend(await self._collect_feed(client, feed_url, self.max_results - len(signals)))

        logger.info("X feed collector returned %s signals", len(signals))
        return signals[: self.max_results]

    async def _collect_feed(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
        remaining: int,
    ) -> list[SignalCreate]:
        try:
            response = await client.get(feed_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("X feed fetch failed for %s: %s", feed_url, exc)
            return []

        parsed = feedparser.parse(response.content)
        if parsed.bozo:
            logger.warning("X feed parse warning for %s: %s", feed_url, parsed.bozo_exception)

        feed_title = _clean_text(parsed.feed.get("title", "X feed"))
        signals: list[SignalCreate] = []
        for entry in parsed.entries:
            if len(signals) >= remaining:
                break
            title = _clean_text(entry.get("title", "X post"))
            content = _entry_content(entry)
            if not is_interesting_x_post(title=title, content=content, min_terms=self.min_interest_terms):
                continue
            signals.append(
                SignalCreate(
                    source=feed_title,
                    source_type="x",
                    channel="social",
                    title=_title_from_text(title or content),
                    content=content or title,
                    url=entry.get("link") or entry.get("id"),
                    author=_entry_author(entry, feed_title),
                    published_at=_entry_datetime(entry),
                )
            )
        return signals


def is_interesting_x_post(title: str, content: str, min_terms: int = 1) -> bool:
    text = f"{title} {content}"
    if extract_cves(text) or extract_github_links(text):
        return True

    interest_count = len(extract_keywords(text)) + len(extract_products(text))
    return interest_count >= max(1, min_terms)


def _entry_content(entry: Any) -> str:
    if entry.get("summary"):
        return _clean_text(entry.get("summary", ""))
    content = entry.get("content")
    if isinstance(content, list) and content:
        return _clean_text(content[0].get("value", ""))
    if entry.get("description"):
        return _clean_text(entry.get("description", ""))
    return ""


def _entry_author(entry: Any, fallback: str) -> str | None:
    author = entry.get("author") or entry.get("author_detail", {}).get("name")
    if author:
        return _clean_text(author)
    return _author_from_title(entry.get("title")) or fallback


def _author_from_title(title: str | None) -> str | None:
    if not title:
        return None
    prefix, separator, _ = title.partition(":")
    if not separator:
        return None
    prefix = prefix.strip()
    if prefix.startswith("@") or len(prefix.split()) <= 2:
        return prefix.removeprefix("@")
    return None


def _entry_datetime(entry: Any) -> datetime | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _title_from_text(text: str) -> str:
    clean = _clean_text(text)
    if len(clean) <= 120:
        return clean or "X post"
    return f"{clean[:117]}..."


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())
