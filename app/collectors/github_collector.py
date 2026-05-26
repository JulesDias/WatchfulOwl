import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

DEFAULT_QUERIES = [
    "CVE exploit PoC",
    "0day exploit",
    "exploit released",
    "privilege escalation PoC",
    "RCE exploit",
    "auth bypass PoC",
    "no CVE exploit",
]


class GitHubCollector(BaseCollector):
    source_type = "github"

    def __init__(
        self,
        token: str | None,
        max_results: int,
        timeout_seconds: float,
        min_stars: int = 0,
        queries: list[str] | None = None,
    ) -> None:
        super().__init__(max_results=max_results)
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.min_stars = min_stars
        self.queries = queries or DEFAULT_QUERIES

    async def collect(self) -> list[SignalCreate]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        signals: list[SignalCreate] = []
        seen_urls: set[str] = set()
        created_after = (datetime.now(timezone.utc) - timedelta(days=45)).date().isoformat()

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            for query in self.queries:
                if len(signals) >= self.max_results:
                    break
                remaining = self.max_results - len(signals)
                params = {
                    "q": f"{query} created:>{created_after}",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": min(10, remaining),
                }
                try:
                    response = await client.get(GITHUB_SEARCH_URL, params=params)
                    if response.status_code in {403, 429}:
                        logger.warning(
                            "GitHub rate limit or access error (%s): %s",
                            response.status_code,
                            response.text[:300],
                        )
                        break
                    response.raise_for_status()
                    
                    # Parse JSON response with error handling
                    try:
                        payload = response.json()
                    except ValueError as exc:  # ValueError covers json.JSONDecodeError
                        logger.warning("GitHub API returned invalid JSON for query %r: %s", query, exc)
                        continue
                    
                except httpx.HTTPError as exc:
                    logger.warning("GitHub search failed for query %r: %s", query, exc)
                    continue

                for item in payload.get("items", []):
                    if len(signals) >= self.max_results:
                        break
                    url = item.get("html_url")
                    if not url or url in seen_urls:
                        continue
                    stars = item.get("stargazers_count", 0)
                    if stars < self.min_stars:
                        continue
                    seen_urls.add(url)
                    signals.append(_repo_to_signal(item))

        logger.info("GitHub collector returned %s signals", len(signals))
        return signals


def _repo_to_signal(item: dict[str, Any]) -> SignalCreate:
    owner = item.get("owner") or {}
    full_name = item.get("full_name") or "unknown/repository"
    description = item.get("description") or ""
    stars = item.get("stargazers_count", 0)
    created_at = _parse_github_datetime(item.get("created_at"))
    updated_at = item.get("updated_at") or "unknown"
    content = (
        f"{description}\n"
        f"GitHub repository: {full_name}\n"
        f"Stars: {stars}\n"
        f"Created at: {item.get('created_at') or 'unknown'}\n"
        f"Updated at: {updated_at}"
    )
    return SignalCreate(
        source="GitHub",
        source_type="github",
        channel="github",
        title=full_name,
        content=content,
        url=item.get("html_url"),
        author=owner.get("login"),
        published_at=created_at,
        github_stars=stars,
    )


def _parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
