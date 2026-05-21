import json
import logging
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def send_discord_alert(signal: Any, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.discord_webhook_url:
        return False

    message = _format_alert(signal)
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(
                settings.discord_webhook_url,
                json={"content": message},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Discord alert failed for signal %s: %s", getattr(signal, "id", None), exc)
        return False

    logger.info("Discord alert sent for signal %s", getattr(signal, "id", None))
    return True


def _format_alert(signal: Any) -> str:
    cves = ", ".join(_as_list(getattr(signal, "cves", []))) or "None"
    keywords = ", ".join(_as_list(getattr(signal, "keywords", []))) or "None"
    products = ", ".join(_as_list(getattr(signal, "products", []))) or "None"
    severity = (getattr(signal, "severity", "") or "info").upper()
    source_type = (getattr(signal, "source_type", "") or "unknown").upper()
    return (
        "🦉 The Watchful Owl — Cyber Alert\n\n"
        f"Severity: {severity}\n"
        f"Score: {getattr(signal, 'score', 0)}\n"
        f"Confidence: {getattr(signal, 'confidence', 'low')}\n"
        f"Source: {source_type}\n"
        f"Title: {getattr(signal, 'title', 'Untitled')}\n"
        f"CVE: {cves}\n"
        f"Keywords: {keywords}\n"
        f"Products: {products}\n"
        f"URL: {getattr(signal, 'url', None) or 'N/A'}"
    )


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
    return []
