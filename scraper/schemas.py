from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class DiscoveryItem(BaseModel):
    source_url: str
    source_slug: str
    display_name: str | None = None
    photo_source_url: str | None = None
    summary: str | None = None
    url_hash: str


class PositionData(BaseModel):
    title: str
    organization_name: str | None = None
    is_current: bool = True


class EventData(BaseModel):
    name: str
    source_url: str
    participation_role: str = "speaker"


class SpeakerProfile(BaseModel):
    source: str = "roscongress"
    source_url: str
    source_slug: str
    full_name: str
    biography: str | None = None
    photo_source_url: str | None = None
    positions: list[PositionData] = Field(default_factory=list)
    events: list[EventData] = Field(default_factory=list)
    related_counts: dict[str, int] = Field(default_factory=dict)
    fetched_at: datetime
    parser_version: str


class FetchResult(BaseModel):
    url: str
    status_code: int
    text: str | None = None
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    fetched_at: datetime
    from_cache: bool = False
    error: str | None = None

