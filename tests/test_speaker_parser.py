from datetime import UTC, datetime
from pathlib import Path

from scraper.parsers.speaker_profile import parse_speaker_profile


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def test_parse_speaker_profile_extracts_required_data():
    html = Path("tests/fixtures/speaker_profile.html").read_text(encoding="utf-8")
    profile = parse_speaker_profile(
        html,
        "https://roscongress.ru/speakers/ivan-ivanov/",
        datetime(2026, 7, 14, 12, 0, 0),
        "0.2.0",
    )

    assert profile.full_name == "Иван Иванов"
    assert profile.photo_source_url == "https://roscongress.ru/upload/ivan.jpg"
    assert profile.positions[0].title == "Генеральный директор"
    assert profile.positions[0].organization_name == "АО «Энергия»"
    assert profile.events[0].source_url == "https://roscongress.ru/events/example-forum/"


def test_parse_speaker_profile_rejects_missing_name():
    try:
        parse_speaker_profile("<html></html>", "https://roscongress.ru/speakers/no-name/", now(), "0.2.0")
    except ValueError as exc:
        assert "full name" in str(exc)
    else:
        raise AssertionError("missing name should raise ValueError")
