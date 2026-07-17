from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree

from scraper.config import DEFAULT_SPEAKERS_URL
from scraper.fetcher import FetchBlockedError, Fetcher
from scraper.normalizer import canonicalize_url, source_slug_from_url, url_hash
from scraper.parsers.event_speakers import parse_event_speakers
from scraper.parsers.speaker_list import parse_speaker_list
from scraper.schemas import DiscoveryItem


class SpeakerDiscovery:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    def discover(self, limit: int, start_url: str = DEFAULT_SPEAKERS_URL) -> list[DiscoveryItem]:
        discovered: dict[str, DiscoveryItem] = {}
        page_url: str | None = canonicalize_url(start_url)
        visited_pages: set[str] = set()

        while page_url and len(discovered) < limit and page_url not in visited_pages:
            visited_pages.add(page_url)
            try:
                result = self.fetcher.fetch(page_url)
            except FetchBlockedError as exc:
                if page_url == canonicalize_url(DEFAULT_SPEAKERS_URL):
                    sitemap_items = self.discover_from_sitemap(limit)
                    if sitemap_items:
                        return sitemap_items
                    raise FetchBlockedError(
                        f"{exc}; sitemap fallback did not return speaker URLs"
                    ) from exc
                raise
            if result.status_code != 200 or not result.text:
                break
            parser = parse_event_speakers if "/events/" in page_url else parse_speaker_list
            items, next_url = parser(result.text, page_url)
            for item in items:
                discovered.setdefault(item.source_url, item)
                if len(discovered) >= limit:
                    break
            page_url = next_url

        return list(discovered.values())[:limit]

    def discover_from_sitemap(self, limit: int) -> list[DiscoveryItem]:
        sitemap_urls = [
            "https://roscongress.ru/sitemap.xml",
            "https://roscongress.ru/sitemap-speakers.xml",
        ]
        discovered: dict[str, DiscoveryItem] = {}
        visited: set[str] = set()
        queue = sitemap_urls[:]

        while queue and len(discovered) < limit:
            sitemap_url = queue.pop(0)
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)
            try:
                result = self.fetcher.fetch(sitemap_url)
            except FetchBlockedError:
                continue
            if result.status_code != 200 or not result.text:
                continue

            root = ElementTree.fromstring(result.text.encode("utf-8"))
            namespace = ""
            if root.tag.startswith("{"):
                namespace = root.tag.split("}", 1)[0] + "}"

            if root.tag.endswith("sitemapindex"):
                for loc in root.findall(f".//{namespace}loc"):
                    if loc.text and "sitemap" in loc.text:
                        queue.append(loc.text.strip())
                continue

            for loc in root.findall(f".//{namespace}loc"):
                if not loc.text:
                    continue
                canonical = canonicalize_url(loc.text.strip())
                if "/speakers/" not in canonical:
                    continue
                slug = source_slug_from_url(canonical)
                if not slug or canonical.rstrip("/") == canonicalize_url(DEFAULT_SPEAKERS_URL).rstrip("/"):
                    continue
                discovered.setdefault(
                    canonical,
                    DiscoveryItem(
                        source_url=canonical,
                        source_slug=slug,
                        display_name=None,
                        photo_source_url=None,
                        summary=None,
                        url_hash=url_hash(canonical),
                    ),
                )
                if len(discovered) >= limit:
                    break

        return list(discovered.values())[:limit]


def dedupe_discovery_items(items: Iterable[DiscoveryItem]) -> list[DiscoveryItem]:
    unique: dict[str, DiscoveryItem] = {}
    for item in items:
        unique.setdefault(item.source_url, item)
    return list(unique.values())
