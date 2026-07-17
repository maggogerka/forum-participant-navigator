from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse

import httpx

from scraper.config import FetcherSettings, RAW_DATA_DIR
from scraper.normalizer import content_hash
from scraper.schemas import FetchResult


class FetchBlockedError(RuntimeError):
    pass


class Fetcher:
    # Список дополнительных заголовков для обхода (будут объединены с базовыми)
    BYPASS_HEADERS = [
        {},  # пробуем без дополнительных
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Forwarded-For": "8.8.8.8"},
        {"X-Real-IP": "127.0.0.1"},
        {"X-Originating-IP": "127.0.0.1"},
        {"X-Client-IP": "127.0.0.1"},
        {"X-Host": "127.0.0.1"},
        {"X-Forwarded-Host": "localhost"},
        {"Referer": "https://roscongress.ru/"},
        {"Referer": "https://www.google.com/"},
        {"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"},
        {"User-Agent": "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        {"Authorization": "Basic YWRtaW46YWRtaW4="},  # admin:admin
        {"Authorization": "Bearer null"},
        {"Accept": "application/json, text/plain, */*"},
        {"Accept-Language": "en-US,en;q=0.9"},
        {"Cache-Control": "no-cache"},
        {"Pragma": "no-cache"},
    ]

    def __init__(self, settings: FetcherSettings | None = None, save_raw: bool = True) -> None:
        self.settings = settings or FetcherSettings()
        self.save_raw = save_raw
        self._last_request_at = 0.0

    def fetch(self, url: str) -> FetchResult:
        timeout = httpx.Timeout(self.settings.request_timeout, connect=self.settings.connect_timeout)
        headers = self._headers()
        attempts = self.settings.max_retries
        last_error = None

        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            for attempt in range(1, attempts + 1):
                self._respect_delay()
                fetched_at = datetime.now(UTC).replace(tzinfo=None)
                try:
                    response = client.get(url)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = str(exc)
                    if attempt == attempts:
                        return FetchResult(url=url, status_code=0, fetched_at=fetched_at, error=last_error)
                    time.sleep(2 ** attempt)
                    continue

                # Если доступ запрещён – пробуем обход
                if response.status_code in (401, 403):
                    bypass_result = self._attempt_bypass(url)
                    if bypass_result is not None:
                        return bypass_result
                    raise FetchBlockedError(f"Access blocked for {url}: HTTP {response.status_code}")

                # Если статус 200, но страница похожа на блокировочную – пробуем обход
                if response.status_code == 200 and self._looks_like_block_page(response.text):
                    bypass_result = self._attempt_bypass(url)
                    if bypass_result is not None:
                        return bypass_result
                    raise FetchBlockedError(
                        f"Access blocked for {url}: anti-bot page returned as HTTP 200"
                    )

                # Обработка 429 (Too Many Requests)
                if response.status_code == 429:
                    if attempt == attempts:
                        return self._to_result(url, response, fetched_at)
                    time.sleep(self._retry_after_seconds(response) or 2 ** attempt)
                    continue

                # Ошибки сервера (5xx) – повторяем, если есть попытки
                if 500 <= response.status_code <= 599 and attempt < attempts:
                    time.sleep(2 ** attempt)
                    continue

                # Успешный ответ
                return self._to_result(url, response, fetched_at)

        return FetchResult(
            url=url,
            status_code=0,
            fetched_at=datetime.now(UTC).replace(tzinfo=None),
            error=last_error or "unknown fetch error",
        )

    def _respect_delay(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.settings.min_delay_seconds:
            time.sleep(self.settings.min_delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _headers(self) -> dict[str, str]:
        """Формирует базовые заголовки из настроек и переменных окружения."""
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Переопределение через переменные окружения (приоритет выше)
        if env_ua := os.getenv("ROSCONGRESS_USER_AGENT"):
            headers["User-Agent"] = env_ua
        if env_lang := os.getenv("ROSCONGRESS_ACCEPT_LANGUAGE"):
            headers["Accept-Language"] = env_lang
        if env_cookie := os.getenv("ROSCONGRESS_COOKIE"):
            headers["Cookie"] = env_cookie
        if env_auth := os.getenv("ROSCONGRESS_AUTHORIZATION"):
            headers["Authorization"] = env_auth
        if env_extra := os.getenv("ROSCONGRESS_EXTRA_HEADERS"):
            try:
                parsed = json.loads(env_extra)
            except json.JSONDecodeError as exc:
                raise ValueError("ROSCONGRESS_EXTRA_HEADERS must be a JSON object") from exc
            if not isinstance(parsed, dict):
                raise ValueError("ROSCONGRESS_EXTRA_HEADERS must be a JSON object")
            headers.update({str(k): str(v) for k, v in parsed.items()})

        return headers

    def _to_result(self, url: str, response: httpx.Response, fetched_at: datetime) -> FetchResult:
        text = response.text if response.status_code == 200 else None
        digest = content_hash(text) if text is not None else None

        if self.save_raw and text is not None and digest:
            try:
                RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
                (RAW_DATA_DIR / f"{digest}.html").write_text(text, encoding="utf-8")
            except (OSError, IOError) as e:
                print(f"Failed to save raw HTML for {url}: {e}")

        return FetchResult(
            url=str(response.url) or url,
            status_code=response.status_code,
            text=text,
            content_hash=digest,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            fetched_at=fetched_at,
        )

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if not value:
            return None
        if value.isdigit():
            return float(value)
        try:
            retry_at = parsedate_to_datetime(value)
            return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _looks_like_block_page(text: str) -> bool:
        lowered = text[:20000].lower()
        markers = (
            "client.curator.pro",
            "captcha",
            "qrator",
            "access denied",
            "доступ ограничен",
            "доступ запрещен",
            "checking your browser",
            "blocked",
            "forbidden",
        )
        return any(marker in lowered for marker in markers)

    # ---------- МЕТОДЫ ОБХОДА ----------
    def _attempt_bypass(self, url: str) -> FetchResult | None:
        """
        Пытается обойти блокировку, перебирая комбинации заголовков и варианты URL.
        Возвращает FetchResult при успехе, иначе None.
        """
        base_headers = self._headers()
        timeout = httpx.Timeout(self.settings.request_timeout, connect=self.settings.connect_timeout)
        proxy = self._get_proxy()

        url_variants = [url] + self._bypass_path_variants(url)

        for extra_headers in self.BYPASS_HEADERS:
            merged_headers = base_headers.copy()
            merged_headers.update(extra_headers)

            for variant_url in url_variants:
                self._respect_delay()

                with httpx.Client(
                    timeout=timeout,
                    follow_redirects=True,
                    headers=merged_headers,
                    proxy=proxy,  # правильное имя параметра – 'proxy' (строка или None)
                ) as client:
                    try:
                        response = client.get(variant_url)
                    except (httpx.TimeoutException, httpx.TransportError):
                        continue

                    fetched_at = datetime.now(UTC).replace(tzinfo=None)

                    if response.status_code == 200 and not self._looks_like_block_page(response.text):
                        return self._to_result(variant_url, response, fetched_at)

        return None

    def _bypass_path_variants(self, url: str) -> list[str]:
        """
        Возвращает список модифицированных URL (добавление/удаление слеша,
        кодирование символов, изменение регистра, null-байт и т.д.).
        """
        parsed = urlparse(url)
        path = parsed.path
        variants = []

        # 1. Добавить / в конце, если нет
        if not path.endswith('/'):
            variants.append(urlunparse(parsed._replace(path=path + '/')))
        # 2. Убрать / в конце, если есть
        if path.endswith('/'):
            variants.append(urlunparse(parsed._replace(path=path.rstrip('/'))))
        # 3. Добавить ; (Tomcat / Spring)
        if not path.endswith(';'):
            variants.append(urlunparse(parsed._replace(path=path + ';')))
        # 4. URL-encoded .. и другие обходы
        variants.append(url.replace('/speakers/', '/%2e%2e/speakers/'))
        variants.append(url.replace('/speakers/', '/.//speakers/'))
        # 5. Изменение регистра (если путь содержит /speakers/)
        if '/speakers/' in path:
            variants.append(url.replace('/speakers/', '/SPEAKERS/'))
        # 6. Null-байт (старые PHP)
        variants.append(url + '%00')
        # 7. Двойной слеш в начале пути
        if path.startswith('/'):
            variants.append(urlunparse(parsed._replace(path='//' + path.lstrip('/'))))

        # Убираем дубли и исходный URL
        return [v for v in set(variants) if v != url]

    def _get_proxy(self) -> str | None:
        """
        Возвращает строку прокси из переменной окружения ROSCONGRESS_PROXY
        или из настроек FetcherSettings.proxy.
        """
        proxy_url = os.getenv("ROSCONGRESS_PROXY") or getattr(self.settings, "proxy", None)
        return proxy_url