# Forum Participant Navigator

Source-aware parser for public Roscongress participant profiles. Version `0.2.0`
focuses on a reliable database and repeatable imports: the same public source can
be imported many times without creating duplicate persons or losing position
history.

## What Works In v0.2.0

- `python -m scraper import-speakers --limit 50`
- `python -m scraper import-profile "https://roscongress.ru/speakers/example/"`
- `--dry-run` mode without database writes
- PostgreSQL via Docker Compose
- Alembic migration from an empty database
- SQLAlchemy models for people, organizations, positions, events, source
  documents, scrape runs, review queue, tags and tag evidence
- polite HTTP fetching: one request at a time, delay, retries, `Retry-After`,
  no CAPTCHA/auth bypass
- local raw HTML cache in `data/raw/` ignored by Git
- local tests on HTML fixtures

## Quick Start

```powershell
python -m pip install -e .[dev]
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://fpn:fpn@localhost:5432/forum_participant_navigator"
python -m alembic upgrade head
python -m scraper check
```

Import a small batch first:

```powershell
python -m scraper import-speakers --limit 10 --dry-run
python -m scraper import-speakers --limit 50
```

If the public catalog page returns `401/403`, use a file with direct public
profile URLs:

```powershell
python -m scraper import-speakers --urls-file .\speaker_urls.txt --limit 50
```

The file format is one URL per line. Empty lines and lines starting with `#` are
ignored.

Do not use fuzzers or path tricks to bypass `401/403`; this importer supports
public sitemaps, public catalog pages and explicit public URL lists.

Import one profile for debugging:

```powershell
python -m scraper import-profile "https://roscongress.ru/speakers/example/" --debug
```

Refresh old records:

```powershell
python -m scraper refresh --older-than 30d --limit 50
```

Run tests:

```powershell
python -m pytest
```

## Safety Boundaries

The parser uses only public pages supplied by Roscongress. It does not invent
biographies, infer gender, age, citizenship, views, influence, private contacts,
or data from closed sources. Duplicate resolution is conservative: exact
`source_url` updates the same person; same-name candidates are sent to
`review_queue` instead of being merged automatically.

## Project Structure

```text
app/                 SQLAlchemy database models and session helpers
scraper/             CLI, discovery, fetcher, parsers, repository, reporter
scraper/parsers/     HTML parsers for speaker lists, profiles and event speakers
config/tag_rules.yaml
migrations/          Alembic migrations
tests/               fixture-based tests; no live website calls
data/raw/            local HTML cache, ignored by Git
```
