from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.config import get_settings
from app.utils.proxy import ProxyRouter


@contextmanager
def open_playwright_browser(headless: bool | None = None):
    settings = get_settings()
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Playwright is not available: {exc}") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings.playwright_headless if headless is None else headless,
            slow_mo=settings.playwright_slow_mo_ms,
        )
        try:
            yield browser
        finally:
            browser.close()


def build_context_kwargs(target_url: str) -> dict[str, Any]:
    settings = get_settings()
    router = ProxyRouter.from_settings(settings)
    decision = router.decide(target_url)

    kwargs: dict[str, Any] = {
        "user_agent": settings.connector_user_agent,
    }

    if decision.use_proxy and decision.proxy_url:
        kwargs["proxy"] = {"server": decision.proxy_url}

    return kwargs
