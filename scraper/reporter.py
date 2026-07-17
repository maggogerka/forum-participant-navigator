from __future__ import annotations

from datetime import datetime

from app.models import ScrapeRun


def format_report(run: ScrapeRun) -> str:
    finished = run.finished_at or datetime.utcnow()
    duration = int((finished - run.started_at).total_seconds()) if run.started_at else 0
    return "\n".join(
        [
            f"Scrape run: {run.id}",
            f"Status: {run.status}",
            "",
            f"Discovered:       {run.discovered_count}",
            f"Fetched:          {run.fetched_count}",
            f"Not modified:     {run.not_modified_count}",
            f"Parsed:           {run.parsed_count}",
            f"Created persons:  {run.created_count}",
            f"Updated persons:  {run.updated_count}",
            f"Skipped:          {run.skipped_count}",
            f"Needs review:     {run.review_count}",
            f"Errors:           {run.error_count}",
            f"Duration:         {duration}s",
        ]
    )

