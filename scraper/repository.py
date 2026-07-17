from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Event,
    EventParticipant,
    Organization,
    Person,
    PersonPosition,
    PersonTag,
    ReviewQueueItem,
    ScrapeRun,
    SourceDocument,
    Tag,
    utcnow,
)
from scraper.normalizer import normalize_for_match, normalize_organization_name, source_slug_from_url
from scraper.schemas import FetchResult, SpeakerProfile
from scraper.tagger import RuleTagger, TagEvidence


class Repository:
    def __init__(self, session: Session, tagger: RuleTagger | None = None) -> None:
        self.session = session
        self.tagger = tagger or RuleTagger()

    def create_run(self, parser_version: str, requested_limit: int | None, dry_run: bool) -> ScrapeRun:
        run = ScrapeRun(
            parser_version=parser_version,
            requested_limit=requested_limit,
            dry_run=dry_run,
            status="running",
            error_log=[],
        )
        self.session.add(run)
        self.session.flush()
        return run

    def finish_run(self, run: ScrapeRun, status: str = "completed") -> None:
        run.status = status
        run.finished_at = utcnow()
        self.session.flush()

    def save_source_document(
        self,
        result: FetchResult,
        parser_version: str,
        parse_status: str = "fetched",
        error_message: str | None = None,
    ) -> SourceDocument:
        document = self.session.scalar(
            select(SourceDocument).where(SourceDocument.source_url == result.url)
        )
        if document is None:
            document = SourceDocument(
                source_url=result.url,
                content_hash=result.content_hash,
                http_status=result.status_code,
                etag=result.etag,
                last_modified=result.last_modified,
                fetched_at=result.fetched_at,
                parser_version=parser_version,
                parse_status=parse_status,
                error_message=error_message,
            )
            self.session.add(document)
        else:
            document.content_hash = result.content_hash
            document.http_status = result.status_code
            document.etag = result.etag
            document.last_modified = result.last_modified
            document.fetched_at = result.fetched_at
            document.parser_version = parser_version
            document.parse_status = parse_status
            document.error_message = error_message
        self.session.flush()
        return document

    def mark_unavailable(self, source_url: str) -> bool:
        person = self.session.scalar(select(Person).where(Person.source_url == source_url))
        if not person:
            return False
        person.status = "unavailable"
        person.last_verified_at = utcnow()
        self.session.flush()
        return True

    def upsert_profile(self, profile: SpeakerProfile) -> tuple[Person, str, int]:
        now = utcnow()
        normalized_name = normalize_for_match(profile.full_name)
        person = self.session.scalar(select(Person).where(Person.source_url == profile.source_url))
        action = "updated"
        if person is None:
            same_name = list(
                self.session.scalars(select(Person).where(Person.normalized_name == normalized_name))
            )
            if same_name:
                self.add_review(
                    "person",
                    None,
                    "possible_duplicate_same_name",
                    {"incoming": profile.model_dump(mode="json"), "candidate_ids": [item.id for item in same_name]},
                )
            person = Person(
                source=profile.source,
                source_slug=profile.source_slug,
                full_name=profile.full_name,
                normalized_name=normalized_name,
                biography=profile.biography,
                photo_source_url=profile.photo_source_url,
                source_url=profile.source_url,
                first_seen_at=now,
                last_seen_at=now,
                last_verified_at=now,
                status="active",
            )
            self.session.add(person)
            self.session.flush()
            action = "created"
        else:
            person.source_slug = profile.source_slug
            person.full_name = profile.full_name
            person.normalized_name = normalized_name
            person.biography = profile.biography
            person.photo_source_url = profile.photo_source_url
            person.last_seen_at = now
            person.last_verified_at = now
            person.status = "active"

        self._sync_positions(person, profile, now)
        self._sync_events(person, profile, now)
        tag_count = self._sync_tags(person, self.tagger.tag_profile(profile))
        self.session.flush()
        return person, action, tag_count

    def add_review(
        self, entity_type: str, entity_id: str | None, reason: str, payload: dict
    ) -> ReviewQueueItem:
        item = ReviewQueueItem(
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            payload_json=payload,
            status="open",
            created_at=utcnow(),
        )
        self.session.add(item)
        self.session.flush()
        return item

    def _sync_positions(self, person: Person, profile: SpeakerProfile, now: datetime) -> None:
        incoming_keys: set[tuple[str, str]] = set()
        for position in profile.positions:
            title = normalize_for_match(position.title)
            org = self._get_or_create_organization(position.organization_name)
            org_key = org.normalized_name if org else ""
            incoming_keys.add((title, org_key))
            current = self.session.scalar(
                select(PersonPosition).where(
                    PersonPosition.person_id == person.id,
                    PersonPosition.normalized_title == title,
                    PersonPosition.organization_id == (org.id if org else None),
                    PersonPosition.is_current.is_(True),
                )
            )
            if current:
                current.last_seen_at = now
                continue
            self.session.add(
                PersonPosition(
                    person_id=person.id,
                    organization_id=org.id if org else None,
                    title=position.title,
                    normalized_title=title,
                    is_current=True,
                    source_url=profile.source_url,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )

        if not incoming_keys:
            return
        current_positions = list(
            self.session.scalars(
                select(PersonPosition).where(
                    PersonPosition.person_id == person.id,
                    PersonPosition.is_current.is_(True),
                )
            )
        )
        for existing in current_positions:
            org_key = existing.organization.normalized_name if existing.organization else ""
            if (existing.normalized_title, org_key) not in incoming_keys:
                existing.is_current = False
                existing.valid_to = now

    def _get_or_create_organization(self, name: str | None) -> Organization | None:
        if not name:
            return None
        normalized = normalize_organization_name(name)
        org = self.session.scalar(
            select(Organization).where(Organization.normalized_name == normalized)
        )
        if org:
            return org
        org = Organization(name=name, normalized_name=normalized)
        self.session.add(org)
        self.session.flush()
        return org

    def _sync_events(self, person: Person, profile: SpeakerProfile, now: datetime) -> None:
        for event_data in profile.events:
            event = self.session.scalar(select(Event).where(Event.source_url == event_data.source_url))
            if event is None:
                event = Event(
                    source_slug=source_slug_from_url(event_data.source_url),
                    name=event_data.name,
                    source_url=event_data.source_url,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                self.session.add(event)
                self.session.flush()
            else:
                event.name = event_data.name
                event.last_seen_at = now
            participant = self.session.scalar(
                select(EventParticipant).where(
                    EventParticipant.event_id == event.id,
                    EventParticipant.person_id == person.id,
                    EventParticipant.participation_role == event_data.participation_role,
                )
            )
            if participant:
                participant.last_seen_at = now
            else:
                self.session.add(
                    EventParticipant(
                        event_id=event.id,
                        person_id=person.id,
                        participation_role=event_data.participation_role,
                        source_url=event_data.source_url,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )

    def _sync_tags(self, person: Person, evidence_items: list[TagEvidence]) -> int:
        count = 0
        for evidence in evidence_items:
            tag = self.session.get(Tag, evidence.tag_id)
            if tag is None:
                tag = Tag(id=evidence.tag_id, label=evidence.label)
                self.session.add(tag)
                self.session.flush()
            existing = self.session.scalar(
                select(PersonTag).where(
                    PersonTag.person_id == person.id,
                    PersonTag.tag_id == evidence.tag_id,
                    PersonTag.source_field == evidence.source_field,
                    PersonTag.evidence == evidence.evidence,
                )
            )
            if existing is None:
                self.session.add(
                    PersonTag(
                        person_id=person.id,
                        tag_id=evidence.tag_id,
                        source_type="rule",
                        source_field=evidence.source_field,
                        evidence=evidence.evidence,
                        confidence=evidence.confidence,
                    )
                )
                count += 1
        return count

