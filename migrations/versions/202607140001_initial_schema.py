"""initial schema

Revision ID: 202607140001
Revises:
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "202607140001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("requested_limit", sa.Integer()),
        sa.Column("discovered_count", sa.Integer(), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("not_modified_count", sa.Integer(), nullable=False),
        sa.Column("parsed_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("error_log", sa.JSON(), nullable=False),
    )
    op.create_table(
        "persons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_slug", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("normalized_name", sa.String(512), nullable=False),
        sa.Column("biography", sa.Text()),
        sa.Column("photo_source_url", sa.Text()),
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_persons_source_slug", "persons", ["source_slug"])
    op.create_index("ix_persons_normalized_name", "persons", ["normalized_name"])
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("normalized_name", sa.String(512), nullable=False),
        sa.Column("organization_type", sa.String(64)),
        sa.Column("source_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_organizations_normalized_name"),
    )
    op.create_index("ix_organizations_normalized_name", "organizations", ["normalized_name"])
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_slug", sa.String(255), nullable=False),
        sa.Column("name", sa.String(1024), nullable=False),
        sa.Column("event_date_from", sa.DateTime()),
        sa.Column("event_date_to", sa.DateTime()),
        sa.Column("location", sa.String(512)),
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_events_source_slug", "events", ["source_slug"])
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("etag", sa.String(512)),
        sa.Column("last_modified", sa.String(512)),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("parse_status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text()),
    )
    op.create_table(
        "review_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "person_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id")),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("normalized_title", sa.String(1024), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime()),
        sa.Column("valid_to", sa.DateTime()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("participation_role", sa.String(128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "person_id", "participation_role", name="uq_event_person_role"),
    )
    op.create_table(
        "person_tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("tag_id", sa.String(64), sa.ForeignKey("tags.id"), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_field", sa.String(128), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.UniqueConstraint("person_id", "tag_id", "source_field", "evidence", name="uq_person_tag_evidence"),
    )


def downgrade() -> None:
    op.drop_table("person_tags")
    op.drop_table("event_participants")
    op.drop_table("person_positions")
    op.drop_table("tags")
    op.drop_table("review_queue")
    op.drop_table("source_documents")
    op.drop_index("ix_events_source_slug", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_organizations_normalized_name", table_name="organizations")
    op.drop_table("organizations")
    op.drop_index("ix_persons_normalized_name", table_name="persons")
    op.drop_index("ix_persons_source_slug", table_name="persons")
    op.drop_table("persons")
    op.drop_table("scrape_runs")

