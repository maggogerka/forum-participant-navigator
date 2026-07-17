from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper.normalizer import absolute_url, canonicalize_url, clean_text, source_slug_from_url
from scraper.schemas import EventData, PositionData, SpeakerProfile

POSITION_SPLIT_RE = re.compile(r"\s+[—-]\s+|\s+\|\s+")


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            objects.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                objects.extend(item for item in graph if isinstance(item, dict))
            objects.append(data)
    return objects


def _meta_content(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return None


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if text:
                return text
    return None


def _extract_name(soup: BeautifulSoup) -> str | None:
    for obj in _json_ld_objects(soup):
        if obj.get("@type") == "Person" and obj.get("name"):
            return clean_text(str(obj["name"]))
    return _first_text(
        soup,
        (
            "h1[itemprop='name']",
            "[data-speaker-name]",
            ".speaker__name",
            ".person__name",
            "h1",
            "meta[property='og:title']",
        ),
    ) or _meta_content(soup, "og:title", "twitter:title")


def _extract_photo(soup: BeautifulSoup, page_url: str) -> str | None:
    for obj in _json_ld_objects(soup):
        if obj.get("@type") == "Person" and obj.get("image"):
            image = obj["image"][0] if isinstance(obj["image"], list) else obj["image"]
            if image:
                return absolute_url(str(image), page_url)
    image = _meta_content(soup, "og:image", "twitter:image")
    if image:
        return absolute_url(image, page_url)
    img = soup.select_one("[data-speaker-photo] img, .speaker img, .person img, img[itemprop='image']")
    if img:
        src = img.get("src") or img.get("data-src")
        if src:
            return absolute_url(src, page_url)
    return None


def _extract_biography(soup: BeautifulSoup) -> str | None:
    bio = _first_text(
        soup,
        (
            "[itemprop='description']",
            ".speaker__bio",
            ".person__bio",
            ".biography",
            ".text-content",
            "section:has(h2)",
        ),
    )
    if bio:
        return bio
    return _meta_content(soup, "description", "og:description")


def _split_position(text: str) -> PositionData | None:
    text = clean_text(text)
    if not text:
        return None
    parts = [clean_text(part) for part in POSITION_SPLIT_RE.split(text, maxsplit=1)]
    parts = [part for part in parts if part]
    if not parts:
        return None
    if len(parts) == 1:
        return PositionData(title=parts[0], organization_name=None)
    return PositionData(title=parts[0], organization_name=parts[1])


def _extract_positions(soup: BeautifulSoup) -> list[PositionData]:
    positions: list[PositionData] = []
    for obj in _json_ld_objects(soup):
        if obj.get("@type") == "Person":
            job_title = obj.get("jobTitle")
            org = obj.get("worksFor") or obj.get("affiliation")
            org_name = org.get("name") if isinstance(org, dict) else org
            if job_title:
                positions.append(
                    PositionData(
                        title=clean_text(str(job_title)) or str(job_title),
                        organization_name=clean_text(str(org_name)) if org_name else None,
                    )
                )

    selectors = (
        "[data-position]",
        "[itemprop='jobTitle']",
        ".speaker__position",
        ".person__position",
        ".position",
        ".post",
    )
    for selector in selectors:
        for node in soup.select(selector):
            parsed = _split_position(node.get_text(" ", strip=True))
            if parsed and parsed.title not in {position.title for position in positions}:
                positions.append(parsed)
    return positions


def _extract_events(soup: BeautifulSoup, page_url: str) -> list[EventData]:
    events: dict[str, EventData] = {}
    for link in soup.select('a[href*="/events/"]'):
        href = link.get("href")
        name = clean_text(link.get_text(" ", strip=True))
        if not href or not name:
            continue
        canonical = canonicalize_url(href, page_url)
        path = urlparse(canonical).path
        if "/events/" not in path:
            continue
        events[canonical] = EventData(name=name, source_url=canonical, participation_role="speaker")
    return list(events.values())


def parse_speaker_profile(html: str, page_url: str, fetched_at: datetime, parser_version: str) -> SpeakerProfile:
    soup = BeautifulSoup(html, "html.parser")
    canonical_url = canonicalize_url(page_url)
    name = _extract_name(soup)
    if not name:
        raise ValueError("Speaker profile has no full name")

    return SpeakerProfile(
        source="roscongress",
        source_url=canonical_url,
        source_slug=source_slug_from_url(canonical_url),
        full_name=name,
        biography=_extract_biography(soup),
        photo_source_url=_extract_photo(soup, canonical_url),
        positions=_extract_positions(soup),
        events=_extract_events(soup, canonical_url),
        related_counts={},
        fetched_at=fetched_at,
        parser_version=parser_version,
    )
