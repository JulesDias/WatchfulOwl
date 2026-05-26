from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RSS_FEEDS = [
    "https://www.bleepingcomputer.com/feed/",
    "https://thehackernews.com/feeds/posts/default",
    "https://www.darkreading.com/rss.xml",
    "https://www.cisa.gov/news.xml",
    "https://news.ycombinator.com/rss",  # HackerNews - trending tech/security stories
    "https://www.reddit.com/r/netsec/.rss",  # Reddit r/netsec - network security discussions
    "https://www.reddit.com/r/cybersecurity/.rss",  # Reddit r/cybersecurity - general discussions
    "https://www.reddit.com/r/hacking/.rss",  # Reddit r/hacking - pentesting & hacking
    "https://0dayfans.com/feed.rss",
    "https://www.cshub.com/rss/categories/attacks",
    "https://www.cshub.com/rss/categories/malware",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "The Watchful Owl"
    database_url: str = "sqlite:///./watchful_owl.db"
    log_level: str = "INFO"

    github_token: str | None = None
    x_bearer_token: str | None = None
    discord_webhook_url: str | None = None

    enable_rss: bool = True
    enable_github: bool = True
    enable_x: bool = True
    enable_scheduler: bool = True

    collection_interval_minutes: int = 15
    alert_score_threshold: int = 15
    max_results_per_source: int = 25
    max_concurrent_collectors: int = 3
    collector_timeout_seconds: float = 60.0
    rss_feed_concurrency: int = 5
    http_timeout_seconds: float = 15.0
    github_min_stars: int = 0

    rss_feed_urls: list[str] = Field(default_factory=lambda: DEFAULT_RSS_FEEDS.copy())

    @field_validator(
        "github_token", "x_bearer_token", "discord_webhook_url", mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("rss_feed_urls", mode="before")
    @classmethod
    def parse_rss_feed_urls(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return DEFAULT_RSS_FEEDS.copy()
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
