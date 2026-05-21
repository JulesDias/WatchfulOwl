import json

from app.models import Signal
from app.processing.deduplicate import compute_fingerprint, normalize_title, normalize_url


def test_url_fingerprint_ignores_tracking_parameters_and_trailing_slash() -> None:
    first = Signal(
        source="rss",
        source_type="rss",
        title="First",
        url="HTTPS://Example.com/post/?utm_source=x&id=1",
    )
    second = Signal(
        source="rss",
        source_type="rss",
        title="Second",
        url="https://example.com/post?id=1",
    )

    assert compute_fingerprint(first) == compute_fingerprint(second)


def test_cve_fingerprint_is_used_when_url_is_missing() -> None:
    first = Signal(source="rss", source_type="rss", title="A")
    first.cves = json.dumps(["CVE-2025-1000", "CVE-2025-2000"])
    second = Signal(source="rss", source_type="rss", title="B")
    second.cves = json.dumps(["CVE-2025-2000", "CVE-2025-1000"])

    assert compute_fingerprint(first) == compute_fingerprint(second)


def test_title_normalization() -> None:
    assert normalize_title("  New   RCE   PoC  ") == "new rce poc"
    assert normalize_url("https://example.com/a/?utm_campaign=x") == "https://example.com/a"
