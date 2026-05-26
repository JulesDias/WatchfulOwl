import asyncio
from typing import Any

import httpx
import pytest

from app.collectors.x_feed_collector import XFeedCollector, is_interesting_x_post
from app.config import Settings
from app.processing.pipeline import build_collectors


class FakeFeedResponse:
    def __init__(self, content: str) -> None:
        self.content = content.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeFeedClient:
    feeds: dict[str, str] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeFeedClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str) -> FakeFeedResponse:
        return FakeFeedResponse(self.feeds[url])


def test_x_feed_collector_filters_for_interesting_security_posts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeFeedClient.feeds = {
        "https://feeds.example.test/security.xml": _feed(
            "Security watchlist",
            [
                ("@researcher: CVE-2026-1234 RCE PoC released", "PoC for Windows RCE"),
                ("@noise: lunch update", "nothing to see here"),
                (
                    "@reverse: exploit notes",
                    "Exploit released with repo https://github.com/acme/poc",
                ),
            ],
        )
    }
    monkeypatch.setattr(httpx, "AsyncClient", FakeFeedClient)
    collector = XFeedCollector(
        feed_urls=list(FakeFeedClient.feeds),
        max_results=10,
        timeout_seconds=1,
    )

    signals = asyncio.run(collector.collect())

    assert [signal.author for signal in signals] == ["researcher", "reverse"]
    assert all(signal.source_type == "x" for signal in signals)
    assert signals[0].url == "https://x.example.test/1"
    assert signals[1].title == "@reverse: exploit notes"


def test_interesting_x_post_heuristic() -> None:
    assert is_interesting_x_post("CVE-2026-1234", "")
    assert is_interesting_x_post("", "Repository https://github.com/acme/poc")
    assert is_interesting_x_post("", "PoC released for Fortinet auth bypass", min_terms=2)
    assert not is_interesting_x_post("conference agenda", "general cyber chatter", min_terms=2)


def test_build_collectors_uses_x_feed_only_when_enabled() -> None:
    disabled = Settings(enable_rss=False, enable_github=False, enable_x=False, enable_x_snscrape=False)
    enabled = Settings(
        enable_rss=False,
        enable_github=False,
        enable_x=False,
        enable_x_snscrape=False,
        enable_x_feed=True,
        x_feed_urls=["https://feeds.example.test/security.xml"],
    )

    assert build_collectors(disabled) == []
    collectors = build_collectors(enabled)
    assert len(collectors) == 1
    assert isinstance(collectors[0], XFeedCollector)


def _feed(title: str, items: list[tuple[str, str]]) -> str:
    entries = "\n".join(
        f"""
        <item>
          <title>{item_title}</title>
          <description>{description}</description>
          <link>https://x.example.test/{index}</link>
        </item>
        """
        for index, (item_title, description) in enumerate(items, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>{title}</title>
    {entries}
  </channel>
</rss>
"""
