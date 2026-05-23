from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from app.config import get_settings


T = TypeVar("T")


class RetryableError(Exception):
    pass


def retry_call(
    fn: Callable[[], T],
    attempts: int | None = None,
    backoff_seconds: float | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
) -> T:
    settings = get_settings()
    max_attempts = attempts if attempts is not None else settings.http_retry_attempts
    backoff = backoff_seconds if backoff_seconds is not None else settings.http_retry_backoff_seconds

    if max_attempts < 1:
        max_attempts = 1

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            retry_allowed = should_retry(exc) if should_retry else _default_should_retry(exc)
            last_error = exc
            if not retry_allowed or attempt >= max_attempts:
                raise
            time.sleep(backoff * attempt)

    if last_error:
        raise last_error
    raise RuntimeError("retry_call reached unexpected state")


def _default_should_retry(exc: Exception) -> bool:
    text = str(exc).lower()
    non_retry_markers = [
        "captcha",
        "blocked",
        "403",
        "401",
        "forbidden",
        "404",
        "400",
        "not found",
        "bad request",
    ]
    if any(marker in text for marker in non_retry_markers):
        return False
    return True
