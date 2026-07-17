from __future__ import annotations

from scraper.parsers.speaker_list import parse_speaker_list
from scraper.schemas import DiscoveryItem


def parse_event_speakers(html: str, page_url: str) -> tuple[list[DiscoveryItem], str | None]:
    return parse_speaker_list(html, page_url)

