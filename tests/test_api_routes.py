from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.routes import router
from app.database import get_session
from app.models import CollectionRun, Signal


def test_stats_and_alerts_ignore_deleted_signals() -> None:
    client, engine = _test_client()
    with Session(engine) as session:
        session.add(
            Signal(
                source="RSS",
                source_type="rss",
                title="Active critical signal",
                score=100,
                severity="critical",
                fingerprint="active-critical",
            )
        )
        session.add(
            Signal(
                source="RSS",
                source_type="rss",
                title="Deleted critical signal",
                score=100,
                severity="critical",
                deleted_at=datetime.now(timezone.utc),
                fingerprint="deleted-critical",
            )
        )
        session.commit()

    stats = client.get("/stats")
    alerts = client.get("/alerts")

    assert stats.status_code == 200
    assert stats.json()["total_signals"] == 1
    assert stats.json()["total_alerts"] == 1
    assert stats.json()["count_by_severity"] == {"critical": 1}
    assert alerts.status_code == 200
    assert [signal["title"] for signal in alerts.json()] == ["Active critical signal"]


def test_trash_response_includes_deleted_at() -> None:
    client, engine = _test_client()
    deleted_at = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(
            Signal(
                source="RSS",
                source_type="rss",
                title="Deleted signal",
                deleted_at=deleted_at,
                fingerprint="deleted-signal",
            )
        )
        session.commit()

    response = client.get("/trash")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Deleted signal"
    assert payload[0]["deleted_at"] is not None


def test_signals_support_offset_pagination_headers() -> None:
    client, engine = _test_client()
    with Session(engine) as session:
        for index, title in enumerate(["Oldest", "Middle", "Newest"], start=1):
            session.add(
                Signal(
                    source="RSS",
                    source_type="rss",
                    title=title,
                    collected_at=datetime(2026, 5, 26, 8, index, tzinfo=timezone.utc),
                    fingerprint=f"signal-{index}",
                )
            )
        session.commit()

    response = client.get("/signals?limit=1&offset=1")

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "3"
    assert response.headers["X-Page-Limit"] == "1"
    assert response.headers["X-Page-Offset"] == "1"
    assert response.headers["X-Has-More"] == "true"
    assert [signal["title"] for signal in response.json()] == ["Middle"]


def test_collection_runs_endpoint_filters_and_paginates() -> None:
    client, engine = _test_client()
    with Session(engine) as session:
        session.add(
            CollectionRun(
                source="rss",
                started_at=datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 5, 26, 8, 0, 1, tzinfo=timezone.utc),
                duration_ms=1000,
                success=True,
                collected_count=3,
            )
        )
        session.add(
            CollectionRun(
                source="github",
                started_at=datetime(2026, 5, 26, 8, 1, tzinfo=timezone.utc),
                finished_at=datetime(2026, 5, 26, 8, 1, 1, tzinfo=timezone.utc),
                duration_ms=1000,
                success=False,
                collected_count=0,
                error_message="rate limited",
            )
        )
        session.commit()

    response = client.get("/collection-runs?success=false&limit=1")

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["source"] == "github"
    assert payload[0]["success"] is False
    assert payload[0]["error_message"] == "rate limited"


def _test_client() -> tuple[TestClient, object]:
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
    return TestClient(test_app), engine
