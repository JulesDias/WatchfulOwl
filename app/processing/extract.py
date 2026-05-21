import json
import re
from typing import Any


CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
GITHUB_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?github\.com/[^\s\]\)\}\"'>]+",
    re.IGNORECASE,
)

DANGEROUS_KEYWORDS = [
    "0day",
    "zero-day",
    "no CVE",
    "unpatched",
    "PoC",
    "PoC released",
    "exploit",
    "exploit released",
    "RCE",
    "LPE",
    "privilege escalation",
    "auth bypass",
    "sandbox escape",
    "EDR bypass",
    "AV bypass",
    "ransomware",
    "active exploitation",
    "full disclosure",
    "patch bypass",
    "wormable",
    "critical",
    "CVSS 10",
    "supply chain",
    "backdoor",
    "botnet",
    "APT",
    "nation state",
    "lateral movement",
    "persistence",
    "rootkit",
    "remote code execution",
    
]

SENSITIVE_PRODUCTS = [
    "Windows",
    "Linux",
    "Linux kernel",
    "BitLocker",
    "Active Directory",
    "Exchange",
    "SharePoint",
    "Fortinet",
    "FortiGate",
    "Ivanti",
    "Citrix",
    "Palo Alto",
    "Cisco",
    "VMware",
    "ESXi",
    "Kubernetes",
    "Docker",
    "OpenSSH",
    "Apache",
    "Nginx",
    "WordPress",
    "GitLab",
    "Jenkins",
    "Atlassian",
    "Confluence",
    "Jira",
    "EDR",
    "VPN",
    "firewall",
]


def extract_cves(text: str | None) -> list[str]:
    if not text:
        return []
    return _dedupe_preserve_order(match.upper() for match in CVE_PATTERN.findall(text))


def extract_keywords(text: str | None) -> list[str]:
    return _extract_terms(text, DANGEROUS_KEYWORDS)


def extract_products(text: str | None) -> list[str]:
    return _extract_terms(text, SENSITIVE_PRODUCTS)


def extract_github_links(text: str | None) -> list[str]:
    if not text:
        return []
    links = [match.rstrip(".,;:") for match in GITHUB_URL_PATTERN.findall(text)]
    return _dedupe_preserve_order(links)


def enrich_signal(signal: Any) -> Any:
    text = " ".join(
        part
        for part in [
            getattr(signal, "title", "") or "",
            getattr(signal, "content", "") or "",
            getattr(signal, "url", "") or "",
        ]
        if part
    )
    signal.cves = json.dumps(extract_cves(text))
    signal.keywords = json.dumps(extract_keywords(text))
    signal.products = json.dumps(extract_products(text))
    signal.github_links = json.dumps(extract_github_links(text))
    return signal


def _extract_terms(text: str | None, terms: list[str]) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for term in terms:
        if _contains_term(text, term):
            found.append(term)
    return found


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    pattern = re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(text))


def _dedupe_preserve_order(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
