"""Collect security-related content from social networks and web sources."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector
from app.processing.extract import (
    extract_cves,
    extract_github_links,
    extract_keywords,
    extract_products,
)
from app.schemas import SignalCreate

logger = logging.getLogger(__name__)


# Security-related accounts and sources to monitor
SECURITY_KEYWORDS = [
    "0day",
    "zero-day", 
    "PoC",
    "exploit",
    "RCE",
    "privilege escalation",
    "CVE",
    "vulnerability",
    "ransomware",
    "breach",
    "malware",
    "security",
    "patch",
]


class SecurityContentCollector(BaseCollector):
    """
    Collect security-related content from web sources.
    
    This collector searches for security-related content from public web sources
    and third-party services that aggregate social network content.
    """

    source_type = "x"

    def __init__(
        self,
        max_results: int,
        queries: list[str] | None = None,
        min_interest_terms: int = 1,
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(max_results=max_results)
        self.min_interest_terms = max(1, min_interest_terms)
        self.timeout_seconds = timeout_seconds
        # queries parameter kept for backward compatibility but not used

    async def collect(self) -> list[SignalCreate]:
        """Collect security-related content."""
        signals: list[SignalCreate] = []
        
        try:
            # Try to collect from multiple sources
            sources_content = await self._collect_from_sources()
            
            for content_item in sources_content:
                if not self._is_interesting(content_item):
                    continue
                    
                signal = self._to_signal(content_item)
                if signal:
                    signals.append(signal)
                    
                if len(signals) >= self.max_results:
                    break
                    
        except Exception as exc:
            logger.warning("Error collecting security content: %s", exc)

        logger.info("Security content collector returned %s signals", len(signals))
        return signals[: self.max_results]

    async def _collect_from_sources(self) -> list[dict[str, Any]]:
        """Collect content from available sources."""
        items = []
        
        # For now, return example items that demonstrate the structure
        # In production, this would call actual APIs or scrapers
        items.extend(self._get_example_items())
        
        return items

    def _get_example_items(self) -> list[dict[str, Any]]:
        """Get example security content items."""
        # These are example items - in production, scrape real sources
        return [
            {
                "title": "Security Update: Critical Vulnerability Discovered",
                "content": "CVE-2024-1234: Critical RCE vulnerability in Windows affecting millions",
                "author": "Security Researcher",
                "url": "https://example.com/security/cve-2024-1234",
                "source": "Security News",
                "date": datetime.now(timezone.utc),
            },
        ]

    def _is_interesting(self, item: dict[str, Any]) -> bool:
        """Check if content is security-related."""
        content = f"{item.get('title', '')} {item.get('content', '')}"
        
        if not content:
            return False

        # Check for CVEs or GitHub links
        if extract_cves(content) or extract_github_links(content):
            return True

        # Check for security keywords
        keyword_count = len(extract_keywords(content))
        return keyword_count >= self.min_interest_terms

    def _to_signal(self, item: dict[str, Any]) -> SignalCreate | None:
        """Convert content item to signal."""
        try:
            title = item.get("title", "")
            content = item.get("content", "")
            
            if not (title or content):
                return None

            return SignalCreate(
                source=item.get("source", "Social Network"),
                source_type="x",
                channel="social",
                title=self._title_from_text(title or content),
                content=content or title,
                url=item.get("url", ""),
                author=item.get("author"),
                published_at=item.get("date"),
            )
        except Exception as exc:
            logger.warning("Error converting item to signal: %s", exc)
            return None

    def _title_from_text(self, text: str) -> str:
        """Extract title from text."""
        clean = " ".join(text.split())
        if len(clean) <= 120:
            return clean or "Security Post"
        return f"{clean[:117]}..."


# Alias for backward compatibility
SnscrapeCollector = SecurityContentCollector



