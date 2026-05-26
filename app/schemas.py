from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignalCreate(BaseModel):
    source: str
    source_type: str
    title: str
    content: str = ""
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    github_stars: int = 0


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_type: str
    title: str
    content: str
    url: str | None
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    deleted_at: datetime | None = None
    cves: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    github_links: list[str] = Field(default_factory=list)
    github_stars: int = 0
    score: int
    confidence: str
    severity: str
    status: str
    is_favorite: bool
    fingerprint: str


class GitHubRepoAddRequest(BaseModel):
    repo_url: str = Field(min_length=3)


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int
    success: bool
    collected_count: int
    error_message: str | None


class CollectionSummary(BaseModel):
    collected: int = 0
    new: int = 0
    duplicates: int = 0
    alerted: int = 0


class StatsResponse(BaseModel):
    total_signals: int
    total_alerts: int
    count_by_source_type: dict[str, int]
    count_by_severity: dict[str, int]
    top_keywords: list[tuple[str, int]]
    top_products: list[tuple[str, int]]
