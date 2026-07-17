from __future__ import annotations

import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select

from app.db import make_engine, make_session_factory
from app.models import Person, ScrapeRun, utcnow
from scraper import PARSER_VERSION
from scraper.config import DEFAULT_SPEAKERS_URL, FetcherSettings, ImportSettings
from scraper.discovery import SpeakerDiscovery
from scraper.fetcher import FetchBlockedError, Fetcher
from scraper.normalizer import canonicalize_url
from scraper.parsers.speaker_profile import parse_speaker_profile
from scraper.reporter import format_report
from scraper.repository import Repository

app = typer.Typer(no_args_is_help=True)


def _empty_run(limit: int | None, dry_run: bool) -> ScrapeRun:
    return ScrapeRun(
        parser_version=PARSER_VERSION,
        requested_limit=limit,
        dry_run=dry_run,
        status="running",
        discovered_count=0,
        fetched_count=0,
        not_modified_count=0,
        parsed_count=0,
        created_count=0,
        updated_count=0,
        skipped_count=0,
        review_count=0,
        error_count=0,
        error_log=[],
    )


def _import_urls(
    urls: list[str],
    limit: int | None,
    dry_run: bool,
    debug: bool = False,
    discovered_count: int | None = None,
) -> ScrapeRun:
    fetcher = Fetcher(FetcherSettings(), save_raw=not dry_run)
    run = _empty_run(limit, dry_run)
    run.discovered_count = discovered_count if discovered_count is not None else len(urls)

    if dry_run:
        repo = None
        session = None
    else:
        session = make_session_factory(make_engine())()
        repo = Repository(session)
        run = repo.create_run(PARSER_VERSION, limit, dry_run=False)
        run.discovered_count = discovered_count if discovered_count is not None else len(urls)
        session.commit()

    try:
        for source_url in urls[: limit or len(urls)]:
            canonical_url = canonicalize_url(source_url)
            try:
                result = fetcher.fetch(canonical_url)
                if result.status_code == 304:
                    run.not_modified_count += 1
                    run.skipped_count += 1
                    continue
                if result.status_code == 404:
                    run.fetched_count += 1
                    if repo:
                        repo.mark_unavailable(canonical_url)
                        repo.save_source_document(result, PARSER_VERSION, "unavailable")
                        session.commit()
                    run.skipped_count += 1
                    continue
                if result.status_code != 200 or not result.text:
                    run.error_count += 1
                    run.error_log.append(_error_entry(canonical_url, "fetch", result.error or f"HTTP {result.status_code}", result.status_code))
                    if repo:
                        repo.save_source_document(result, PARSER_VERSION, "error", result.error)
                        session.commit()
                    continue

                run.fetched_count += 1
                profile = parse_speaker_profile(result.text, canonical_url, result.fetched_at, PARSER_VERSION)
                run.parsed_count += 1
                if repo:
                    repo.save_source_document(result, PARSER_VERSION, "parsed")
                    _, action, _ = repo.upsert_profile(profile)
                    if action == "created":
                        run.created_count += 1
                    else:
                        run.updated_count += 1
                    run.review_count = _count_open_reviews(repo)
                    session.commit()
                else:
                    run.created_count += 1
            except FetchBlockedError:
                raise
            except Exception as exc:
                run.error_count += 1
                run.error_log.append(
                    _error_entry(
                        canonical_url,
                        "parse",
                        str(exc),
                        None,
                        traceback.format_exc() if debug else None,
                    )
                )
                if repo:
                    session.commit()

        run.status = "completed" if run.error_count == 0 else "completed_with_errors"
        run.finished_at = utcnow()
        if repo:
            repo.finish_run(run, run.status)
            session.commit()
        return run
    except FetchBlockedError as exc:
        run.status = "blocked"
        run.error_count += 1
        run.error_log.append(_error_entry("batch", "fetch", str(exc), 403))
        run.finished_at = utcnow()
        if repo:
            repo.finish_run(run, "blocked")
            session.commit()
        return run
    finally:
        if session:
            session.close()


def _error_entry(
    url: str, stage: str, message: str, http_status: int | None, stack_trace: str | None = None
) -> dict:
    payload = {
        "url": url,
        "stage": stage,
        "type": "error",
        "http_status": http_status,
        "time": datetime.now(UTC).isoformat(),
        "attempt": None,
        "message": message,
    }
    if stack_trace:
        payload["stack_trace"] = stack_trace
    return payload


def _count_open_reviews(repo: Repository) -> int:
    from app.models import ReviewQueueItem

    return len(list(repo.session.scalars(select(ReviewQueueItem).where(ReviewQueueItem.status == "open"))))


@app.command("import-speakers")
def import_speakers(
    limit: Annotated[int, typer.Option(min=1, help="Maximum number of profiles to import.")] = 20,
    dry_run: Annotated[bool, typer.Option(help="Fetch and parse without database writes.")] = False,
    start_url: Annotated[str, typer.Option(help="Speaker catalog or event speakers URL.")] = DEFAULT_SPEAKERS_URL,
    urls_file: Annotated[
        Path | None,
        typer.Option(
            help="Optional text file with one speaker profile URL per line. Used when catalog discovery is blocked."
        ),
    ] = None,
) -> None:
    if urls_file:
        urls = _read_urls_file(urls_file)
        run = _import_urls(urls, limit=limit, dry_run=dry_run, discovered_count=min(len(urls), limit))
        typer.echo(format_report(run))
        return

    fetcher = Fetcher(FetcherSettings(), save_raw=not dry_run)
    try:
        items = SpeakerDiscovery(fetcher).discover(limit=limit, start_url=start_url)
    except FetchBlockedError as exc:
        run = _record_blocked_discovery(limit=limit, dry_run=dry_run, message=str(exc))
        typer.echo(
            "Roscongress returned HTTP 401/403 for the discovery page. "
            "The importer will not bypass authorization or access restrictions."
        )
        typer.echo(format_report(run))
        raise typer.Exit(code=2)
    urls = [item.source_url for item in items]
    run = _import_urls(urls, limit=limit, dry_run=dry_run, discovered_count=len(items))
    typer.echo(format_report(run))


def _read_urls_file(path: Path) -> list[str]:
    if not path.exists():
        raise typer.BadParameter(f"URL file does not exist: {path}")
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def _record_blocked_discovery(limit: int, dry_run: bool, message: str) -> ScrapeRun:
    run = _empty_run(limit, dry_run)
    run.status = "blocked"
    run.finished_at = utcnow()
    run.error_count = 1
    run.error_log.append(_error_entry(DEFAULT_SPEAKERS_URL, "discovery", message, 403))
    if dry_run:
        return run

    session = make_session_factory(make_engine())()
    try:
        repo = Repository(session)
        stored_run = repo.create_run(PARSER_VERSION, limit, dry_run=False)
        stored_run.status = run.status
        stored_run.finished_at = run.finished_at
        stored_run.error_count = run.error_count
        stored_run.error_log = run.error_log
        repo.finish_run(stored_run, "blocked")
        session.commit()
        return stored_run
    finally:
        session.close()


@app.command("import-profile")
def import_profile(
    url: Annotated[str, typer.Argument(help="Public Roscongress speaker profile URL.")],
    dry_run: Annotated[bool, typer.Option(help="Fetch and parse without database writes.")] = False,
    debug: Annotated[bool, typer.Option(help="Include stack traces in run errors.")] = False,
) -> None:
    run = _import_urls([url], limit=1, dry_run=dry_run, debug=debug, discovered_count=1)
    typer.echo(format_report(run))


@app.command("refresh")
def refresh(
    older_than: Annotated[str, typer.Option(help="Age threshold, for example 30d.")] = "30d",
    limit: Annotated[int, typer.Option(min=1)] = 50,
    dry_run: Annotated[bool, typer.Option(help="Fetch and parse without database writes.")] = False,
) -> None:
    days = int(older_than.rstrip("d"))
    cutoff = utcnow() - timedelta(days=days)
    session = make_session_factory(make_engine())()
    try:
        urls = list(
            session.scalars(
                select(Person.source_url)
                .where(Person.last_verified_at < cutoff)
                .order_by(Person.last_verified_at.asc())
                .limit(limit)
            )
        )
    finally:
        session.close()
    run = _import_urls(urls, limit=limit, dry_run=dry_run, discovered_count=len(urls))
    typer.echo(format_report(run))


@app.command("check")
def check() -> None:
    settings = ImportSettings()
    engine = make_engine()
    with engine.connect() as connection:
        connection.exec_driver_sql("select 1")
    typer.echo(f"Configuration OK. Parser version: {settings.parser_version}")

