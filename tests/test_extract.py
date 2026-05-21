import json

from app.models import Signal
from app.processing.extract import (
    enrich_signal,
    extract_cves,
    extract_github_links,
    extract_keywords,
    extract_products,
)


def test_extract_cves_deduplicates_and_uppercases() -> None:
    text = "cve-2024-1234 and CVE-2024-1234 plus CVE-2025-1234567"
    assert extract_cves(text) == ["CVE-2024-1234", "CVE-2025-1234567"]


def test_extract_keywords_products_and_github_links() -> None:
    text = (
        "PoC released for Windows RCE with auth bypass. "
        "See https://github.com/example/CVE-2025-1111."
    )
    assert "PoC" in extract_keywords(text)
    assert "PoC released" in extract_keywords(text)
    assert "RCE" in extract_keywords(text)
    assert "auth bypass" in extract_keywords(text)
    assert "Windows" in extract_products(text)
    assert extract_github_links(text) == ["https://github.com/example/CVE-2025-1111"]


def test_enrich_signal_normalizes_metadata_fields() -> None:
    signal = Signal(
        source="unit",
        source_type="rss",
        title="CVE-2025-2222 exploit released for Fortinet",
        content="PoC: https://github.com/acme/poc",
        url="https://example.test/post",
    )
    enrich_signal(signal)

    assert json.loads(signal.cves) == ["CVE-2025-2222"]
    assert "exploit released" in json.loads(signal.keywords)
    assert "Fortinet" in json.loads(signal.products)
    assert json.loads(signal.github_links) == ["https://github.com/acme/poc"]
