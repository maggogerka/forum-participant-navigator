from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://fpn:fpn@localhost:5432/forum_participant_navigator"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_database_url(), future=True)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or make_engine(), expire_on_commit=False, future=True)


def session_scope(database_url: str | None = None) -> Iterator[Session]:
    factory = make_session_factory(make_engine(database_url))
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

