import hashlib
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlmodel import Session, select

from app.models import Signal


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def compute_fingerprint(signal: Any) -> str:
    url = getattr(signal, "url", None)
    cves = _as_list(getattr(signal, "cves", []))
    source_type = getattr(signal, "source_type", "") or ""
    title = getattr(signal, "title", "") or ""

    if url:
        fingerprint = _hash(f"url:{normalize_url(url)}")
    elif cves:
        fingerprint = _hash(f"cve:{','.join(sorted(cves))}:{source_type.lower()}")
    else:
        fingerprint = _hash(f"title:{normalize_title(title)}")

    signal.fingerprint = fingerprint
    return fingerprint


def fingerprint_exists(session: Session, fingerprint: str) -> bool:
    statement = select(Signal.id).where(Signal.fingerprint == fingerprint)
    return session.exec(statement).first() is not None


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_KEYS and not key.startswith(TRACKING_QUERY_PREFIXES)
    ]
    query = urlencode(query_items)
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
