from collections.abc import Generator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes import _parse_github_repo_reference, router
from app.database import get_session
from app.models import Signal


class FakeGitHubResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)
        self.response = httpx.Response(status_code)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "HTTP error",
                request=httpx.Request("GET", "https://api.github.com/repos/acme/poc"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeAsyncClient:
    response = FakeGitHubResponse(200, {})
    requested_urls: list[str] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str) -> FakeGitHubResponse:
        self.requested_urls.append(url)
        return self.response


def test_parse_github_repo_reference_accepts_url_and_short_form() -> None:
    assert _parse_github_repo_reference("https://github.com/acme/poc") == ("acme", "poc")
    assert _parse_github_repo_reference("github.com/acme/poc/issues/1") == ("acme", "poc")
    assert _parse_github_repo_reference("acme/poc.git") == ("acme", "poc")


def test_add_github_repo_accepts_json_and_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeGitHubResponse(
        200,
        {
            "full_name": "acme/poc",
            "description": "PoC released for CVE-2026-1234 affecting Windows RCE",
            "html_url": "https://github.com/acme/poc",
            "owner": {"login": "acme"},
            "stargazers_count": 42,
            "created_at": "2026-05-20T08:15:00Z",
            "updated_at": "2026-05-20T09:15:00Z",
        },
    )
    FakeAsyncClient.requested_urls = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_session] = override_get_session
    client = TestClient(test_app)

    first = client.post("/github/add", json={"repo_url": "acme/poc"})
    second = client.post("/github/add", json={"repo_url": "https://github.com/acme/poc"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["title"] == "acme/poc"
    assert first.json()["source_type"] == "github"
    assert first.json()["github_stars"] == 42
    assert FakeAsyncClient.requested_urls == [
        "https://api.github.com/repos/acme/poc",
        "https://api.github.com/repos/acme/poc",
    ]

    with Session(engine) as session:
        signals = session.exec(select(Signal)).all()

    assert len(signals) == 1
    assert signals[0].fingerprint
