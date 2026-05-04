from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import Settings, get_settings
from app.utils.logging import get_file_logger
from app.utils.proxy import ProxyRouter


connectors_logger = get_file_logger("connectors.eat.browser", "connectors.log")


class EatBrowserFallback:
    def __init__(self, settings: Settings | None = None, proxy_router: ProxyRouter | None = None) -> None:
        self.settings = settings or get_settings()
        self.proxy_router = proxy_router or ProxyRouter.from_settings(self.settings)

    def fetch_cards(self, status: str, limit: int | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []

        cards = self._fetch_with_playwright(status=status, limit=limit, warnings=warnings)
        if cards:
            return cards, warnings, errors

        cards_http = self._fetch_with_http(status=status, limit=limit, warnings=warnings)
        if cards_http:
            return cards_http, warnings, errors

        errors.append("eat fallback returned no purchases (possibly auth/captcha required)")
        return [], warnings, errors

    def _fetch_with_playwright(self, status: str, limit: int | None, warnings: list[str]) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright unavailable: {exc}")
            return []

        url = f"{self.settings.eat_base_url}/purchases"
        decision = self.proxy_router.decide(url)
        cards: list[dict[str, Any]] = []

        try:
            with sync_playwright() as p:
                launch_kwargs: dict[str, Any] = {"headless": True}
                if decision.use_proxy and decision.proxy_url:
                    launch_kwargs["proxy"] = {"server": decision.proxy_url}

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(user_agent=self.settings.connector_user_agent)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=int(self.settings.connector_request_timeout_seconds * 1000))

                links = page.eval_on_selector_all(
                    "a[href*='/purchases/announcement/']",
                    "elements => elements.map(e => ({href: e.href, text: (e.innerText || '').trim()}))",
                )
                for link in links:
                    href = (link or {}).get("href")
                    if not href:
                        continue
                    external_id = _extract_external_id(href)
                    if not external_id:
                        continue
                    cards.append(
                        {
                            "externalId": external_id,
                            "url": href,
                            "title": ((link or {}).get("text") or f"EAT {external_id}").strip(),
                            "status": status,
                            "items": [],
                        }
                    )

                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"eat playwright fallback failed: {exc}")
            connectors_logger.warning("eat playwright fallback failed: %s", exc)
            return []

        unique = _dedupe(cards)
        return unique[:limit] if limit is not None else unique

    def _fetch_with_http(self, status: str, limit: int | None, warnings: list[str]) -> list[dict[str, Any]]:
        url = f"{self.settings.eat_base_url}/purchases"
        proxies = self.proxy_router.requests_proxies_for(url)
        try:
            response = requests.get(
                url,
                timeout=self.settings.connector_request_timeout_seconds,
                headers={"User-Agent": self.settings.connector_user_agent},
                proxies=proxies,
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"eat http fallback failed: {exc}")
            return []

        hrefs = set(re.findall(r'href=["\']([^"\']+/purchases/announcement/[^"\']+)["\']', response.text))
        cards: list[dict[str, Any]] = []
        for href in hrefs:
            absolute = urljoin(self.settings.eat_base_url, href)
            external_id = _extract_external_id(absolute)
            if not external_id:
                continue
            cards.append(
                {
                    "externalId": external_id,
                    "url": absolute,
                    "title": f"EAT {external_id}",
                    "status": status,
                    "items": [],
                }
            )

        unique = _dedupe(cards)
        return unique[:limit] if limit is not None else unique


def _extract_external_id(url: str) -> str | None:
    match = re.search(r"/purchases/announcement/([A-Za-z0-9\-]+)", url)
    if match:
        return match.group(1)
    return None


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        external_id = str(record.get("externalId") or "").strip()
        if not external_id or external_id in seen:
            continue
        seen.add(external_id)
        output.append(record)
    return output
