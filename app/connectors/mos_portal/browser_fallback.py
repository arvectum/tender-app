from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin
from urllib.parse import urlparse

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
        captured_payloads: list[Any] = []

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

                def on_response(response: Any) -> None:
                    try:
                        if not _is_candidate_json_response(response.url, response.request.resource_type):
                            return
                        payload = response.json()
                        captured_payloads.append(payload)
                    except BaseException:
                        return

                page.on("response", on_response)

                for target_url in target_urls:
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
                    except Exception as page_exc:  # noqa: BLE001
                        warnings.append(f"playwright page load failed for {target_url}: {page_exc}")
                        continue

                    page.wait_for_timeout(3000)
                    try:
                        links = page.eval_on_selector_all(
                            "a[href*='/auction/'], a[href*='/purchase/']",
                            "elements => elements.map(e => ({href: e.href, text: (e.innerText || '').trim()}))",
                        )
                    except Exception:
                        links = []

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

                    page.wait_for_timeout(1500)

                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright fallback failed: {exc}")
            connectors_logger.warning("mos_portal playwright fallback failed: %s", exc)
            return []

        network_cards = _records_from_captured_payloads(captured_payloads, status=status)
        if network_cards:
            connectors_logger.info(
                "mos_portal playwright network capture success | payloads=%s cards=%s",
                len(captured_payloads),
                len(network_cards),
            )
            collected.extend(network_cards)
        else:
            connectors_logger.info(
                "mos_portal playwright network capture empty | payloads=%s",
                len(captured_payloads),
            )

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


def _is_candidate_json_response(url: str, resource_type: str | None) -> bool:
    url_lower = (url or "").lower()
    if not url_lower:
        return False
    if resource_type and resource_type not in {"xhr", "fetch"}:
        return False
    if "zakupki.mos.ru" not in url_lower:
        return False

    markers = ("/newapi/", "auction", "purchase", "tradingsession", "search", "filter")
    return any(marker in url_lower for marker in markers)


def _records_from_captured_payloads(payloads: list[Any], status: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for payload in payloads:
        for row in _flatten_record_candidates(payload):
            normalized = _normalize_network_record(row, status=status)
            if normalized is not None:
                records.append(normalized)
    return _deduplicate_by_external_id(records)


def _flatten_record_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("items", "rows", "content", "results", "data", "result", "auctions", "purchases", "sessions", "tradingSessions"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _flatten_record_candidates(value)
            if nested:
                return nested

    ext = _pick_string(payload, ["id", "externalId", "auctionId", "purchaseNumber", "number", "sessionId"])
    if ext:
        return [payload]
    return []


def _normalize_network_record(raw: dict[str, Any], status: str) -> dict[str, Any] | None:
    external_id = _pick_string(raw, ["externalId", "id", "auctionId", "purchaseNumber", "number", "sessionId"])
    if not external_id:
        return None

    url = _pick_string(raw, ["url", "href", "link"])
    if not url:
        url = f"https://zakupki.mos.ru/auction/{external_id}"
    elif url.startswith("/"):
        url = urljoin("https://zakupki.mos.ru", url)
    elif not urlparse(url).scheme:
        url = urljoin("https://zakupki.mos.ru", f"/{url.lstrip('/')}")

    title = _pick_string(raw, ["title", "name", "auctionName", "purchaseName", "subject", "displayName"]) or f"Закупка {external_id}"

    card: dict[str, Any] = dict(raw)
    card["externalId"] = external_id
    card["url"] = url
    card["title"] = title
    card["status"] = _pick_string(raw, ["status", "statusName", "state", "sessionState"]) or status
    if "items" not in card and "positions" in card and isinstance(card["positions"], list):
        card["items"] = card["positions"]
    if not _is_procurement_record(card):
        return None
    return card


def _is_procurement_record(card: dict[str, Any]) -> bool:
    title = str(card.get("title") or "").strip()
    title_lower = title.lower()
    if not title:
        return False

    # Явно отсекаем сервисный/контентный мусор из network-capture.
    blocked_title_markers = (
        "уважаемые пользователи",
        "чат взаимодействия",
        "новост",
        "инструкц",
        "поддержк",
        "техподдержк",
        "вебинар",
    )
    if any(marker in title_lower for marker in blocked_title_markers):
        return False

    external_id = str(card.get("externalId") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{3,}", external_id):
        return False

    url = str(card.get("url") or "").strip().lower()
    if not url or not any(path in url for path in ("/auction/", "/purchase/")):
        return False

    # Требуем набор procurement-признаков: минимум 2, где один должен быть "сильным".
    has_status = bool(_pick_string(card, ["status", "statusName", "state", "sessionState"]))
    has_amount = any(
        card.get(key) not in (None, "", 0, "0")
        for key in ("startPrice", "sum", "nmc", "initialPrice", "maxTotalPrice")
    )
    has_deadline = bool(_pick_string(card, ["submissionDeadline", "endDate", "bidsEndDate", "deadline"]))
    has_customer = bool(_pick_string(card, ["customerName", "customer", "organizationName", "buyerName"]))
    has_items = isinstance(card.get("items"), list) and len(card.get("items") or []) > 0

    strong_signals = [has_amount, has_deadline, has_items]
    weak_signals = [has_status, has_customer]

    if not any(strong_signals):
        return False
    if sum(1 for signal in (*strong_signals, *weak_signals) if signal) < 2:
        return False

    return True


def _pick_string(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
