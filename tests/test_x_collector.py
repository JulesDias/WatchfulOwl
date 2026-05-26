import asyncio
from datetime import timezone
from typing import Any

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.collectors.x_collector import XCollector, _parse_x_datetime, _title_from_text
from app.config import Settings
from app.models import Signal
from app.processing.pipeline import build_collectors, run_collection_cycle


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "HTTP error",
                request=httpx.Request("GET", "https://api.twitter.com/2/tweets/search/recent"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeAsyncClient:
    response = FakeResponse(200)
    last_params: dict[str, Any] | None = None
    last_headers: dict[str, str] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs
        FakeAsyncClient.last_headers = kwargs.get("headers")

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, _: str, params: dict[str, Any]) -> FakeResponse:
        FakeAsyncClient.last_params = params
        return self.response


def test_x_collector_disabled_without_token() -> None:
    collector = XCollector(bearer_token=None, max_results=5, timeout_seconds=1)

    assert asyncio.run(collector.collect()) == []


def test_x_collector_maps_recent_search_response(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "data": [
                {
                    "id": "123",
                    "author_id": "42",
                    "text": "PoC released for CVE-2026-1234 affecting Windows RCE",
                    "created_at": "2026-05-20T08:15:00.000Z",
                },
                {
                    "id": "456",
                    "author_id": "99",
                    "text": "Second tweet should be trimmed by max_results",
                    "created_at": "2026-05-20T08:16:00.000Z",
                },
            ],
            "includes": {
                "users": [
                    {"id": "42", "username": "security_user"},
                    {"id": "99", "username": "other_user"},
                ]
            },
        },
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    collector = XCollector(bearer_token="token", max_results=1, timeout_seconds=1)

    signals = asyncio.run(collector.collect())

    assert len(signals) == 1
    assert signals[0].source == "X"
    assert signals[0].source_type == "x"
    assert signals[0].author == "security_user"
    assert signals[0].url == "https://x.com/security_user/status/123"
    assert signals[0].published_at is not None
    assert signals[0].published_at.tzinfo is not None
    assert FakeAsyncClient.last_headers == {"Authorization": "Bearer token"}
    assert FakeAsyncClient.last_params is not None
    assert FakeAsyncClient.last_params["max_results"] == 10


def test_x_collector_handles_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(429, {"detail": "rate limited"})
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    collector = XCollector(bearer_token="token", max_results=5, timeout_seconds=1)

    assert asyncio.run(collector.collect()) == []


def test_x_pipeline_collects_enriches_and_saves_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "data": [
                {
                    "id": "999",
                    "author_id": "42",
                    "text": "PoC released for CVE-2026-9999 affecting Windows RCE",
                    "created_at": "2026-05-20T08:15:00.000Z",
                }
            ],
            "includes": {"users": [{"id": "42", "username": "security_user"}]},
        },
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    settings = Settings(
        enable_rss=False,
        enable_github=False,
        enable_x=True,
        enable_x_snscrape=False,
        x_bearer_token="token",
        discord_webhook_url=None,
    )

    with Session(engine) as session:
        summary = asyncio.run(run_collection_cycle(session=session, settings=settings))
        signals = session.exec(select(Signal)).all()

    assert summary.collected == 1
    assert summary.new == 1
    assert len(signals) == 1
    assert signals[0].source_type == "x"
    assert "CVE-2026-9999" in signals[0].cves
    assert signals[0].score > 0


def test_build_collectors_uses_x_collector_when_enabled() -> None:
    settings = Settings(
        enable_rss=False,
        enable_github=False,
        enable_x=True,
        enable_x_snscrape=False,
        x_bearer_token=None,
    )

    collectors = build_collectors(settings)

    assert len(collectors) == 1
    assert isinstance(collectors[0], XCollector)


def test_build_collectors_skips_x_collector_when_disabled() -> None:
    settings = Settings(
        enable_rss=False,
        enable_github=False,
        enable_x=False,
        enable_x_snscrape=False,
        x_bearer_token="token",
    )

    assert build_collectors(settings) == []


def test_x_helpers_are_stable() -> None:
    long_text = "x" * 150
    parsed = _parse_x_datetime("2026-05-20T08:15:00.000Z")

    assert _title_from_text("") == "X post"
    assert _title_from_text(long_text).endswith("...")
    assert len(_title_from_text(long_text)) == 120
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert _parse_x_datetime("not-a-date") is None
