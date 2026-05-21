import json

from app.models import Signal
from app.processing.extract import enrich_signal
from app.processing.score import (
    _github_star_score,
    confidence_from_score,
    score_signal,
    severity_from_score,
)


def test_score_signal_marks_high_value_rce_poc_as_critical() -> None:
    signal = Signal(
        source="GitHub",
        source_type="github",
        title="CVE-2025-9999 RCE exploit released",
        content="PoC released for VMware auth bypass https://github.com/acme/poc",
        url="https://github.com/acme/poc",
    )
    enrich_signal(signal)

    score = score_signal(signal)

    assert score >= 19
    assert signal.severity == "critical"
    assert signal.confidence == "high"


def test_score_signal_applies_malus_for_generic_empty_signal() -> None:
    signal = Signal(source="rss", source_type="rss", title="News", content="")
    signal.cves = json.dumps([])
    signal.keywords = json.dumps([])
    signal.products = json.dumps([])
    signal.github_links = json.dumps([])

    assert score_signal(signal) == 0
    assert signal.severity == "info"
    assert signal.confidence == "low"


def test_score_mappings() -> None:
    assert severity_from_score(5) == "info"
    assert severity_from_score(6) == "watch"
    assert severity_from_score(12) == "important"
    assert severity_from_score(19) == "critical"
    assert confidence_from_score(7) == "low"
    assert confidence_from_score(8) == "medium"
    assert confidence_from_score(16) == "high"


def test_github_stars_have_stronger_weight() -> None:
    assert _github_star_score(0) == 0
    assert _github_star_score(10) == 2
    assert _github_star_score(50) == 4
    assert _github_star_score(100) == 6
    assert _github_star_score(500) == 8
    assert _github_star_score(1000) == 10
    assert _github_star_score(5000) == 12


def test_popular_github_repo_gets_promoted_by_stars() -> None:
    signal = Signal(
        source="GitHub",
        source_type="github",
        title="CVE-2026-1234 exploit research",
        content="PoC released for Windows RCE",
        url="https://github.com/acme/poc",
        github_stars=1000,
    )
    enrich_signal(signal)

    score = score_signal(signal)

    assert score >= 19
    assert signal.severity == "critical"
    assert signal.confidence == "high"
