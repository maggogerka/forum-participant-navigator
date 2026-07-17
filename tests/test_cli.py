from scraper.cli import _import_urls, _read_urls_file
from scraper.fetcher import FetchBlockedError, Fetcher


def test_import_urls_returns_blocked_run_without_traceback(monkeypatch):
    def blocked_fetch(self, url):
        raise FetchBlockedError(f"Access blocked for {url}: HTTP 401")

    monkeypatch.setattr(Fetcher, "fetch", blocked_fetch)

    run = _import_urls(
        ["https://roscongress.ru/speakers/ivan-ivanov/"],
        limit=1,
        dry_run=True,
        discovered_count=1,
    )

    assert run.status == "blocked"
    assert run.error_count == 1
    assert "HTTP 401" in run.error_log[0]["message"]


def test_read_urls_file_skips_comments_and_blank_lines(tmp_path):
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(
        "\n# comment\nhttps://roscongress.ru/speakers/ivan-ivanov/\n\n",
        encoding="utf-8",
    )

    assert _read_urls_file(urls_file) == ["https://roscongress.ru/speakers/ivan-ivanov/"]
