import asyncio
import time

from sqlmodel import Session, SQLModel, create_engine, select

from app.collectors.base import BaseCollector
from app.config import Settings
from app.models import CollectionRun
from app.processing.pipeline import _collect_all
from app.schemas import SignalCreate


class FakeCollector(BaseCollector):
    def __init__(
        self,
        source_type: str,
        delay_seconds: float,
        signals: list[SignalCreate] | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(max_results=10)
        self.source_type = source_type
        self.delay_seconds = delay_seconds
        self.signals = signals or []
        self.error = error

    async def collect(self) -> list[SignalCreate]:
        await asyncio.sleep(self.delay_seconds)
        if self.error:
            raise self.error
        return self.signals


def test_collect_all_runs_collectors_concurrently_and_records_runs() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    settings = Settings(
        max_concurrent_collectors=2,
        collector_timeout_seconds=1,
    )
    collectors = [
        FakeCollector(
            source_type="rss",
            delay_seconds=0.15,
            signals=[
                SignalCreate(source="RSS", source_type="rss", title="RSS signal"),
            ],
        ),
        FakeCollector(
            source_type="github",
            delay_seconds=0.15,
            error=RuntimeError("boom"),
        ),
    ]

    started = time.perf_counter()
    with Session(engine) as session:
        signals = asyncio.run(_collect_all(collectors, session=session, settings=settings))
        runs = session.exec(select(CollectionRun).order_by(CollectionRun.source)).all()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.28
    assert [signal.title for signal in signals] == ["RSS signal"]
    assert len(runs) == 2
    assert runs[0].source == "github"
    assert runs[0].success is False
    assert runs[0].collected_count == 0
    assert runs[0].error_message == "boom"
    assert runs[1].source == "rss"
    assert runs[1].success is True
    assert runs[1].collected_count == 1
