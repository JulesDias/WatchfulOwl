import logging
from datetime import datetime
from typing import Any

import httpx

from app.collectors.base import BaseCollector
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


X_RECENT_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

DEFAULT_X_QUERY = (
    '("0day" OR "zero-day" OR "PoC released" OR "exploit released" OR "no CVE" '
    'OR "unpatched") ("RCE" OR "LPE" OR "bypass" OR "privilege escalation" '
    'OR "auth bypass" OR "BitLocker" OR "EDR") -is:retweet'
)


class XCollector(BaseCollector):
    source_type = "x"

    def __init__(
        self,
        bearer_token: str | None,
        max_results: int,
        timeout_seconds: float,
        query: str = DEFAULT_X_QUERY,
    ) -> None:
        super().__init__(max_results=max_results)
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds
        self.query = query

    async def collect(self) -> list[SignalCreate]:
        if not self.bearer_token:
            logger.info("X collector disabled: X_BEARER_TOKEN is not configured")
            return []

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "query": self.query,
            "max_results": min(max(self.max_results, 10), 100),
            "tweet.fields": "created_at,author_id,entities",
            "expansions": "author_id",
            "user.fields": "username,name",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(X_RECENT_SEARCH_URL, params=params)
                if response.status_code == 429:
                    logger.warning("X API rate limit reached: %s", response.text[:300])
                    return []
                response.raise_for_status()
                
                # Parse JSON response with error handling
                try:
                    payload = response.json()
                except ValueError as exc:  # ValueError covers json.JSONDecodeError
                    logger.warning("X API returned invalid JSON: %s", exc)
                    return []
                    
        except httpx.HTTPError as exc:
            logger.warning("X recent search failed: %s", exc)
            return []

        users = {
            user["id"]: user
            for user in payload.get("includes", {}).get("users", [])
            if user.get("id")
        }

        signals: list[SignalCreate] = []
        for tweet in payload.get("data", [])[: self.max_results]:
            signals.append(_tweet_to_signal(tweet, users))

        logger.info("X collector returned %s signals", len(signals))
        return signals


def _tweet_to_signal(tweet: dict[str, Any], users: dict[str, dict[str, Any]]) -> SignalCreate:
    author_id = tweet.get("author_id")
    user = users.get(author_id or "", {})
    username = user.get("username")
    tweet_id = tweet.get("id", "")
    url = (
        f"https://x.com/{username}/status/{tweet_id}"
        if username
        else f"https://x.com/i/web/status/{tweet_id}"
    )
    text = tweet.get("text", "")
    return SignalCreate(
        source="X",
        source_type="x",
        channel="social",
        title=_title_from_text(text),
        content=text,
        url=url,
        author=username or author_id,
        published_at=_parse_x_datetime(tweet.get("created_at")),
    )


def _title_from_text(text: str) -> str:
    clean = " ".join(text.split())
    if len(clean) <= 120:
        return clean or "X post"
    return f"{clean[:117]}..."


def _parse_x_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
