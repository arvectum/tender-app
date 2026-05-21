from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import Settings, get_settings
from app.utils.logging import get_file_logger
from app.utils.proxy import ProxyRouter


connectors_logger = get_file_logger("connectors.mos_portal.browser", "connectors.log")


class MosPortalBrowserFallback:
    def __init__(self, settings: Settings | None = None, proxy_router: ProxyRouter | None = None) -> None:
        self.settings = settings or get_settings()
        self.proxy_router = proxy_router or ProxyRouter.from_settings(self.settings)

    def fetch_cards(self, status: str, limit: int | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []

        cards = self._fetch_with_playwright(status=status, limit=limit, warnings=warnings)
        if cards:
            return cards, warnings, errors

        html_cards = self._fetch_with_http(status=status, limit=limit, warnings=warnings)
        if html_cards:
            return html_cards, warnings, errors

        errors.append("mos_portal browser fallback returned no purchases")
        return [], warnings, errors

    def _fetch_with_playwright(self, status: str, limit: int | None, warnings: list[str]) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright unavailable: {exc}")
            return []

        target_urls = [
            f"{self.settings.mos_portal_base_url}/purchase",
            f"{self.settings.mos_portal_base_url}/auction",
        ]
        proxy_cfg = self.proxy_router.decide(target_urls[0])
        collected: list[dict[str, Any]] = []

        try:
            with sync_playwright() as playwright:
                launch_kwargs: dict[str, Any] = {"headless": True}
                if proxy_cfg.use_proxy and proxy_cfg.proxy_url:
                    launch_kwargs["proxy"] = {"server": proxy_cfg.proxy_url}

                browser = playwright.chromium.launch(**launch_kwargs)
                context_kwargs: dict[str, Any] = {"user_agent": self.settings.connector_user_agent}
                if self.settings.mos_portal_storage_state.exists():
                    context_kwargs["storage_state"] = str(self.settings.mos_portal_storage_state)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()

                for target_url in target_urls:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=int(self.settings.connector_request_timeout_seconds * 1000))

                    page.wait_for_timeout(2000)
                    links = page.eval_on_selector_all(
                        "a[href*='/auction/'], a[href*='/purchase/']",
                        "elements => elements.map(e => ({href: e.href, text: (e.innerText || '').trim()}))",
                    )

                    for link in links:
                        href = (link or {}).get("href")
                        if not href:
                            continue
                        ext = _extract_external_id_from_url(href)
                        if not ext:
                            continue
                        collected.append(
                            {
                                "externalId": ext,
                                "url": href,
                                "title": ((link or {}).get("text") or f"Закупка {ext}").strip(),
                                "status": status,
                                "items": [],
                            }
                        )

                    html = page.content()
                    for match in re.finditer(r'https?://[^"\'\s]+/(?:auction|purchase)/[A-Za-z0-9\-]+', html, flags=re.IGNORECASE):
                        href = match.group(0)
                        ext = _extract_external_id_from_url(href)
                        if not ext:
                            continue
                        collected.append(
                            {
                                "externalId": ext,
                                "url": href,
                                "title": f"Закупка {ext}",
                                "status": status,
                                "items": [],
                            }
                        )

                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright fallback failed: {exc}")
            connectors_logger.warning("mos_portal playwright fallback failed: %s", exc)
            return []

        unique = _deduplicate_by_external_id(collected)
        return unique[:limit] if limit is not None else unique

    def _fetch_with_http(self, status: str, limit: int | None, warnings: list[str]) -> list[dict[str, Any]]:
        list_urls = [
            f"{self.settings.mos_portal_base_url}/purchase",
            f"{self.settings.mos_portal_base_url}/auction",
        ]
        hrefs: set[str] = set()
        for list_url in list_urls:
            proxies = self.proxy_router.requests_proxies_for(list_url)
            try:
                response = requests.get(
                    list_url,
                    headers={"User-Agent": self.settings.connector_user_agent},
                    timeout=self.settings.connector_request_timeout_seconds,
                    proxies=proxies,
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"http fallback failed for {list_url}: {exc}")
                continue

            hrefs.update(set(re.findall(r'href=["\']([^"\']+/(?:auction|purchase)/[^"\']+)["\']', response.text, flags=re.IGNORECASE)))
            hrefs.update(set(re.findall(r'https?://[^"\'\s]+/(?:auction|purchase)/[^"\'\s]+', response.text, flags=re.IGNORECASE)))

        if not hrefs:
            return []

        cards: list[dict[str, Any]] = []
        for href in hrefs:
            absolute_url = urljoin(self.settings.mos_portal_base_url, href)
            ext = _extract_external_id_from_url(absolute_url)
            if not ext:
                continue
            cards.append(
                {
                    "externalId": ext,
                    "url": absolute_url,
                    "title": f"Закупка {ext}",
                    "status": status,
                    "items": [],
                }
            )

        unique = _deduplicate_by_external_id(cards)
        return unique[:limit] if limit is not None else unique


def _extract_external_id_from_url(url: str) -> str | None:
    match = re.search(r"/(?:auction|purchase)/([A-Za-z0-9\-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"id=([A-Za-z0-9\-]+)", url)
    if match:
        return match.group(1)
    return None


def _deduplicate_by_external_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        external_id = str(record.get("externalId") or "").strip()
        if not external_id or external_id in seen:
            continue
        seen.add(external_id)
        unique.append(record)
    return unique
