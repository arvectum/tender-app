from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import Settings, get_settings
from app.utils.logging import get_file_logger
from app.utils.proxy import ProxyRouter
from app.utils.retry import retry_call


connectors_logger = get_file_logger("connectors.mos_portal", "connectors.log")


class MosPortalApiClient:
    def __init__(self, settings: Settings | None = None, proxy_router: ProxyRouter | None = None) -> None:
        self.settings = settings or get_settings()
        self.proxy_router = proxy_router or ProxyRouter.from_settings(self.settings)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.settings.connector_user_agent,
            "Accept": "application/json, text/plain, */*",
        })

    def fetch_purchases(self, status: str, limit: int | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []
        aggregated: list[dict[str, Any]] = []

        use_legacy_api = os.getenv("MOS_PORTAL_USE_LEGACY_API", "false").strip().lower() in {"1", "true", "yes", "on"}
        if not use_legacy_api:
            warnings.append("mos_portal legacy API probing disabled; using browser fallback")
            return [], warnings, errors

        for base_url in self.settings.mos_portal_api_base_urls:
            base_unreachable = False
            for candidate in _candidate_list_requests(status=status, limit=limit):
                url = self._build_url(base_url, candidate["path"])
                try:
                    payload = self._request_json(
                        method=candidate["method"],
                        url=url,
                        params=candidate.get("params"),
                        json_body=candidate.get("json"),
                    )
                    records = _extract_records(payload)
                    if records:
                        connectors_logger.info("mos_portal list endpoint success | url=%s records=%s", url, len(records))
                        aggregated.extend(records)
                        if limit is not None and len(aggregated) >= limit:
                            return aggregated[:limit], warnings, errors
                except Exception as exc:  # noqa: BLE001
                    message = f"list request failed: {url} ({exc})"
                    warnings.append(message)
                    connectors_logger.warning(message)
                    if _is_unreachable_error(exc):
                        base_unreachable = True
                        break

            if base_unreachable:
                continue

        if not aggregated:
            errors.append("mos_portal: API list endpoints returned no records")

        return aggregated[:limit] if limit is not None else aggregated, warnings, errors

    def enrich_with_details(self, raw_purchase: dict[str, Any]) -> dict[str, Any]:
        external_id = _pick_external_id(raw_purchase)
        if not external_id:
            return raw_purchase

        for base_url in self.settings.mos_portal_api_base_urls:
            for path in (
                f"/auctions/{external_id}",
                f"/auction/{external_id}",
                f"/purchases/{external_id}",
                f"/Auction/{external_id}",
            ):
                url = self._build_url(base_url, path)
                try:
                    payload = self._request_json("GET", url)
                    record = _extract_first_record(payload)
                    if record:
                        merged = dict(raw_purchase)
                        merged.update(record)
                        return merged
                except Exception:
                    continue

        # If API detail did not work, try parsing public page JSON blobs.
        url = _pick_first(raw_purchase, ["url", "link", "href"])
        if url:
            detail_from_page = self.fetch_detail_from_public_page(url)
            if detail_from_page:
                merged = dict(raw_purchase)
                merged.update(detail_from_page)
                return merged

        return raw_purchase

    def fetch_detail_from_public_page(self, url: str) -> dict[str, Any] | None:
        try:
            response = self._request("GET", url)
            html = response.text
        except Exception:
            return None

        initial_state = _extract_embedded_json(html)
        if isinstance(initial_state, dict):
            return initial_state

        return None

    def _request_json(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = self._request(method=method, url=url, params=params, json_body=json_body)
        return response.json()

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> requests.Response:
        proxies = self.proxy_router.requests_proxies_for(url)
        if proxies:
            connectors_logger.info("mos_portal request via proxy | url=%s", url)
        else:
            connectors_logger.info("mos_portal request direct (NO_PROXY/no proxy) | url=%s", url)

        def _call() -> requests.Response:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=self.settings.http_timeout_seconds,
                proxies=proxies,
            )
            response.raise_for_status()
            return response

        return retry_call(_call)

    @staticmethod
    def _build_url(base_url: str, path: str) -> str:
        if base_url.endswith("/"):
            base = base_url
        else:
            base = f"{base_url}/"
        return urljoin(base, path.lstrip("/"))


def _candidate_list_requests(status: str, limit: int | None) -> list[dict[str, Any]]:
    safe_limit = limit or 100
    return [
        {
            "method": "GET",
            "path": "/auctions",
            "params": {"status": status, "limit": safe_limit},
        },
        {
            "method": "GET",
            "path": "/purchases",
            "params": {"status": status, "limit": safe_limit},
        },
        {
            "method": "POST",
            "path": "/Auction/GetByFilter",
            "json": {"status": status, "limit": safe_limit, "page": 1},
        },
        {
            "method": "POST",
            "path": "/Purchase/GetByFilter",
            "json": {"status": status, "limit": safe_limit, "page": 1},
        },
        {
            "method": "POST",
            "path": "/TradingSession/GetByFilter",
            "json": {"status": status, "limit": safe_limit, "page": 1},
        },
    ]


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("data", "result", "items", "rows", "auctions", "purchases", "sessions"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested_list = _extract_records(value)
            if nested_list:
                return nested_list

    return []


def _extract_first_record(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        # If it's already a full record with id-like fields, return it.
        if _pick_external_id(payload):
            return payload

        for key in ("data", "result", "item", "purchase", "auction"):
            value = payload.get(key)
            if isinstance(value, dict):
                if _pick_external_id(value) or value.get("items") or value.get("positions"):
                    return value
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item

    return None


def _pick_external_id(raw: dict[str, Any]) -> str | None:
    return _pick_first(raw, ["externalId", "id", "purchaseNumber", "auctionId", "sessionId", "number"])


def _pick_first(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_embedded_json(html: str) -> dict[str, Any] | None:
    patterns = [
        r"__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
        r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.DOTALL)
        if not match:
            continue

        candidate = match.group(1)
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    return None


def _is_unreachable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "failed to resolve",
        "name resolution",
        "getaddrinfo failed",
        "nodename nor servname provided",
        "max retries exceeded",
    ]
    return any(marker in text for marker in markers)
