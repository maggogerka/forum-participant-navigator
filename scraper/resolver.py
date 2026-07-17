from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Person
from scraper.normalizer import normalize_for_match
from scraper.schemas import SpeakerProfile


class DuplicateResolver:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_exact_person(self, profile: SpeakerProfile) -> Person | None:
        return self.session.scalar(select(Person).where(Person.source_url == profile.source_url))

    def same_name_candidates(self, profile: SpeakerProfile) -> list[Person]:
        normalized = normalize_for_match(profile.full_name)
        return list(self.session.scalars(select(Person).where(Person.normalized_name == normalized)))

