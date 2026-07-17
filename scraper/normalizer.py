from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import urljoin, urlparse, urlunparse

from scraper.config import ROSCONGRESS_BASE_URL

SPACE_RE = re.compile(r"\s+")
QUOTE_RE = re.compile(r"[\"'«»„“”]")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = html.unescape(value).replace("\xa0", " ")
    value = unicodedata.normalize("NFKC", value)
    value = SPACE_RE.sub(" ", value).strip()
    return value or None


def normalize_for_match(value: str | None) -> str:
    cleaned = clean_text(value) or ""
    return cleaned.casefold().replace("ё", "е")


def normalize_organization_name(value: str | None) -> str:
    normalized = normalize_for_match(value)
    normalized = QUOTE_RE.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def canonicalize_url(url: str, base_url: str = ROSCONGRESS_BASE_URL) -> str:
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def absolute_url(url: str, base_url: str = ROSCONGRESS_BASE_URL) -> str:
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))


def source_slug_from_url(url: str) -> str:
    parsed = urlparse(canonicalize_url(url))
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else ""


def url_hash(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def content_hash(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
