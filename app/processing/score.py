import json
import re
from typing import Any


GENERIC_TITLES = {
    "alert",
    "cybersecurity news",
    "exploit",
    "news",
    "poc",
    "security update",
    "vulnerability",
}


def score_signal(signal: Any) -> int:
    cves = _as_list(getattr(signal, "cves", []))
    keywords = _as_list(getattr(signal, "keywords", []))
    products = _as_list(getattr(signal, "products", []))
    github_links = _as_list(getattr(signal, "github_links", []))
    github_stars = getattr(signal, "github_stars", 0) or 0
    source_type = (getattr(signal, "source_type", "") or "").lower()
    title = getattr(signal, "title", "") or ""
    content = getattr(signal, "content", "") or ""
    text = f"{title} {content}"

    score = 0
    if cves:
        score += 5
    if _contains(text, r"\b0day\b|\bzero-day\b"):
        score += 5
    if _contains(text, r"\bno\s+CVE\b|\bunpatched\b"):
        score += 5
    if _contains(text, r"\bPoC\s+released\b|\bexploit\s+released\b"):
        score += 4
    if github_links:
        score += 4
    if source_type == "github":
        score += 4
    if products:
        score += 3
    if _contains(text, r"\bRCE\b"):
        score += 3
    if _contains(text, r"\bauth\s+bypass\b"):
        score += 3
    if _contains(text, r"\bprivilege\s+escalation\b|\bLPE\b"):
        score += 3
    if source_type == "x":
        score += 2
    if len(keywords) > 1:
        score += 2
    if source_type == "rss":
        score += 1
    
    score += _github_star_score(github_stars)

    if len(text.strip()) < 20:
        score -= 4
    if _is_generic_title(title) and not cves:
        score -= 3
    if not cves and not keywords and not products:
        score -= 3

    score = max(score, 0)
    signal.score = score
    signal.severity = severity_from_score(score)
    signal.confidence = confidence_from_score(score)
    return score


def severity_from_score(score: int) -> str:
    if score >= 19:
        return "critical"
    if score >= 12:
        return "important"
    if score >= 6:
        return "watch"
    return "info"


def confidence_from_score(score: int) -> str:
    if score >= 16:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def _github_star_score(stars: int) -> int:
    if stars >= 5000:
        return 12
    if stars >= 1000:
        return 10
    if stars >= 500:
        return 8
    if stars >= 100:
        return 6
    if stars >= 50:
        return 4
    if stars >= 10:
        return 2
    return 0


def _contains(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _is_generic_title(title: str) -> bool:
    normalized = " ".join(title.lower().split())
    if normalized in GENERIC_TITLES:
        return True
    words = normalized.split()
    return len(words) <= 2 and not _contains(title, r"CVE-\d{4}-\d{4,7}")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
    return []
