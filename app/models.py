from datetime import datetime, timezone

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class Signal(SQLModel, table=True):
    __tablename__ = "signals"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    source_type: str = Field(index=True)
    title: str
    content: str = ""
    url: str | None = Field(default=None, index=True)
    author: str | None = None
    published_at: datetime | None = Field(default=None, index=True)
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    cves: str = "[]"
    keywords: str = "[]"
    products: str = "[]"
    github_links: str = "[]"
    github_stars: int = Field(default=0, index=True)
    score: int = Field(default=0, index=True)
    confidence: str = Field(default="low", index=True)
    severity: str = Field(default="info", index=True)
    status: str = Field(default="new", index=True)
    is_favorite: bool = Field(default=False, index=True)
    fingerprint: str = Field(
        default="",
        sa_column=Column(String, unique=True, index=True, nullable=False),
    )
