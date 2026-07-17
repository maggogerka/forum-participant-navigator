from pathlib import Path

from scraper.parsers.speaker_list import parse_speaker_list


def test_parse_speaker_list_dedupes_and_canonicalizes_urls():
    html = Path("tests/fixtures/speaker_list.html").read_text(encoding="utf-8")
    items, next_url = parse_speaker_list(html, "https://roscongress.ru/speakers/")

    assert [item.source_slug for item in items] == ["ivan-ivanov", "maria-petrova"]
    assert items[0].source_url == "https://roscongress.ru/speakers/ivan-ivanov/"
    assert next_url == "https://roscongress.ru/speakers/?page=2"
