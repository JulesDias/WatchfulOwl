import asyncio
from typing import Any

import httpx
import pytest

from app.collectors.rss_collector import RSSCollector


class FakeRSSResponse:
    def __init__(self, content: str) -> None:
        self.content = content.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeRSSClient:
    feeds: dict[str, str] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeRSSClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> FakeRSSResponse:
        return FakeRSSResponse(self.feeds[url])


def test_rss_collector_round_robins_results_across_feeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeRSSClient.feeds = {
        "https://example.test/a.xml": _feed("Feed A", ["A1", "A2", "A3"]),
        "https://example.test/b.xml": _feed("Feed B", ["B1", "B2", "B3"]),
    }
    monkeypatch.setattr(httpx, "AsyncClient", FakeRSSClient)
    collector = RSSCollector(
        feed_urls=list(FakeRSSClient.feeds),
        max_results=4,
        timeout_seconds=1,
    )

    signals = asyncio.run(collector.collect())

    assert [signal.title for signal in signals] == ["A1", "B1", "A2", "B2"]
    assert [signal.source for signal in signals] == ["Feed A", "Feed B", "Feed A", "Feed B"]


def _feed(title: str, item_titles: list[str]) -> str:
    items = "\n".join(
        f"<item><title>{item_title}</title><link>https://example.test/{item_title}</link></item>"
        for item_title in item_titles
    )
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>{title}</title>
    {items}
  </channel>
</rss>
"""
