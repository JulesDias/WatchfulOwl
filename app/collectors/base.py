from abc import ABC, abstractmethod

from app.schemas import SignalCreate


class BaseCollector(ABC):
    source_type: str

    def __init__(self, max_results: int) -> None:
        self.max_results = max_results

    @abstractmethod
    async def collect(self) -> list[SignalCreate]:
        """Collect raw signals from a public source."""
