from __future__ import annotations

import time
from typing import Any, Callable

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class Fetcher:
    """Polite HTTP client: rate-limited, retrying, identifiable."""

    def __init__(
        self,
        *,
        min_interval: float = 2.5,
        max_retries: int = 3,
        user_agent: str = "DealFinderSA/0.1",
        sleep: Callable[[float], None] = time.sleep,
        client: httpx.Client | None = None,
    ) -> None:
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._sleep = sleep
        self._last_request_at = 0.0
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent}, timeout=30.0
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            self._sleep(wait)

    def _request(self, url: str, params: dict | None, headers: dict | None) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            self._last_request_at = time.monotonic()
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError:
                if attempt > self._max_retries:
                    raise
                self._sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code in RETRYABLE_STATUS and attempt <= self._max_retries:
                self._sleep(min(2 ** attempt, 30))
                continue
            resp.raise_for_status()
            return resp

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        return self._request(url, params, headers).json()

    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None) -> str:
        return self._request(url, params, headers).text

    def close(self) -> None:
        self._client.close()
