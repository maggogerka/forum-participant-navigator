from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.normalizer import absolute_url, canonicalize_url, clean_text, source_slug_from_url, url_hash
from scraper.schemas import DiscoveryItem


def parse_speaker_list(html: str, page_url: str) -> tuple[list[DiscoveryItem], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    items_by_url: dict[str, DiscoveryItem] = {}

    for link in soup.select('a[href*="/speakers/"]'):
        href = link.get("href")
        if not href:
            continue
        canonical = canonicalize_url(href, page_url)
        slug = source_slug_from_url(canonical)
        if not slug or canonical.rstrip("/") == canonicalize_url("/speakers/").rstrip("/"):
            continue
        if "/events/" in canonical:
            continue

        card = link
        for parent in link.parents:
            classes = " ".join(parent.get("class", []))
            if any(token in classes.lower() for token in ("speaker", "person", "participant", "card")):
                card = parent
                break

        display_name = clean_text(link.get_text(" ", strip=True))
        if not display_name:
            title_tag = card.select_one("h1,h2,h3,h4,.name,.title,[itemprop='name']")
            display_name = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None

        img = card.select_one("img")
        image_url = None
        if img:
            image_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if image_url:
                image_url = absolute_url(image_url, page_url)

        summary = clean_text(card.get_text(" ", strip=True))
        items_by_url[canonical] = DiscoveryItem(
            source_url=canonical,
            source_slug=slug,
            display_name=display_name,
            photo_source_url=image_url,
            summary=summary,
            url_hash=url_hash(canonical),
        )

    return list(items_by_url.values()), _find_next_url(soup, page_url)


def _find_next_url(soup: BeautifulSoup, page_url: str) -> str | None:
    selectors = (
        'a[rel="next"]',
        "a.next",
        ".next a",
        ".pagination a[aria-label*='Next']",
        ".pagination a[aria-label*='След']",
        ".pagination__next",
        ".pagination__next a",
        ".page-navigation__next",
        ".page-navigation__next a",
    )
    for selector in selectors:
        link = soup.select_one(selector)
        if link and link.get("href"):
            return absolute_url(link["href"], page_url)

    next_words = ("след", "next", ">", "›", "»")
    for link in soup.select("a[href]"):
        text = clean_text(link.get_text(" ", strip=True)) or ""
        aria = clean_text(link.get("aria-label")) or ""
        classes = " ".join(link.get("class", []))
        haystack = f"{text} {aria} {classes}".casefold()
        if any(word in haystack for word in next_words):
            return absolute_url(link["href"], page_url)

    page_links = [
        absolute_url(link["href"], page_url)
        for link in soup.select("a[href]")
        if "PAGEN_" in link.get("href", "") or "page=" in link.get("href", "").lower()
    ]
    return page_links[0] if page_links else None
