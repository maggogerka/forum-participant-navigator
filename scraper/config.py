from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROSCONGRESS_BASE_URL = "https://roscongress.ru"
DEFAULT_SPEAKERS_URL = f"{ROSCONGRESS_BASE_URL}/speakers/"
RAW_DATA_DIR = Path("data/raw")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 "
    "ForumParticipantNavigator/0.2 "
    "(+https://github.com/maggogerka/forum-participant-navigator)"
)


@dataclass(frozen=True)
class FetcherSettings:
    connect_timeout: float = 10.0
    request_timeout: float = 30.0
    min_delay_seconds: float = 2.0
    max_retries: int = 3
    user_agent: str = DEFAULT_USER_AGENT


@dataclass(frozen=True)
class ImportSettings:
    max_parse_error_rate: float = 0.30
    parser_version: str = "0.2.0"
    source: str = "roscongress"
