from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Person, PersonPosition
from scraper.parsers.speaker_profile import parse_speaker_profile
from scraper.repository import Repository


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def test_repeat_import_updates_person_without_duplicate():
    session = make_session()
    repo = Repository(session)
    html = Path("tests/fixtures/speaker_profile.html").read_text(encoding="utf-8")
    profile = parse_speaker_profile(html, "https://roscongress.ru/speakers/ivan-ivanov/", now(), "0.2.0")

    repo.upsert_profile(profile)
    repo.upsert_profile(profile)
    session.commit()

    assert len(list(session.scalars(select(Person)))) == 1


def test_position_change_keeps_history():
    session = make_session()
    repo = Repository(session)
    first_html = Path("tests/fixtures/speaker_profile.html").read_text(encoding="utf-8")
    second_html = Path("tests/fixtures/speaker_profile_updated.html").read_text(encoding="utf-8")
    first = parse_speaker_profile(first_html, "https://roscongress.ru/speakers/ivan-ivanov/", now(), "0.2.0")
    second = parse_speaker_profile(second_html, "https://roscongress.ru/speakers/ivan-ivanov/", now(), "0.2.0")

    repo.upsert_profile(first)
    repo.upsert_profile(second)
    session.commit()

    positions = list(session.scalars(select(PersonPosition).order_by(PersonPosition.first_seen_at)))
    assert len(positions) == 2
    assert len([position for position in positions if position.is_current]) == 1
    assert any(position.valid_to is not None for position in positions)
