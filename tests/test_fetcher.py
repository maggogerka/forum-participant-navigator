from scraper.fetcher import Fetcher
from scraper.fetcher import FetchBlockedError


def test_fetcher_uses_static_parser_headers():
    headers = Fetcher()._headers()

    assert "ForumParticipantNavigator/0.2" in headers["User-Agent"]
    assert headers["Accept"].startswith("text/html")
    assert headers["Accept-Language"].startswith("ru-RU")


def test_fetcher_detects_antibot_page_returned_as_http_200():
    html = '<html><body><iframe src="https://client.curator.pro/captcha.html"></iframe></body></html>'

    assert Fetcher._looks_like_block_page(html)


def test_fetcher_does_not_attempt_bypass_on_blocked_response(monkeypatch):
    class Response:
        status_code = 401
        text = ""
        headers = {}
        url = "https://roscongress.ru/speakers/"

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            return Response()

    def fail_bypass(self, url):
        raise AssertionError("bypass should not be called")

    monkeypatch.setattr("scraper.fetcher.httpx.Client", Client)
    monkeypatch.setattr(Fetcher, "_attempt_bypass", fail_bypass)

    try:
        Fetcher().fetch("https://roscongress.ru/speakers/")
    except FetchBlockedError as exc:
        assert "HTTP 401" in str(exc)
    else:
        raise AssertionError("blocked response should raise FetchBlockedError")
