from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests

from app.config import Settings, get_settings
from app.utils.logging import get_file_logger
from app.utils.proxy import ProxyRouter
from app.utils.retry import retry_call


connectors_logger = get_file_logger("connectors.eat", "connectors.log")


class EatApiClient:
    def __init__(self, settings: Settings | None = None, proxy_router: ProxyRouter | None = None) -> None:
        self.settings = settings or get_settings()
        self.proxy_router = proxy_router or ProxyRouter.from_settings(self.settings)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.settings.connector_user_agent,
                "Accept": "application/json, text/plain, */*",
            }
        )

    def fetch_purchases(self, status: str, limit: int | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []
        purchases: list[dict[str, Any]] = []

        for base_url in self.settings.eat_api_base_urls:
            base_unreachable = False
            for candidate in _candidate_requests(status=status, limit=limit):
                url = self._build_url(base_url, candidate["path"])
                try:
                    data = self._request_json(
                        method=candidate["method"],
                        url=url,
                        params=candidate.get("params"),
                        json_body=candidate.get("json"),
                    )
                    records = _extract_records(data)
                    if records:
                        purchases.extend(records)
                        connectors_logger.info("eat api success | url=%s records=%s", url, len(records))
                        if limit is not None and len(purchases) >= limit:
                            return purchases[:limit], warnings, errors
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"eat api request failed: {url} ({exc})")
                    if _is_unreachable_error(exc):
                        base_unreachable = True
                        break

            if base_unreachable:
                continue

        if not purchases:
            errors.append("eat api returned no purchases")

        return purchases[:limit] if limit is not None else purchases, warnings, errors

    def _request_json(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        proxies = self.proxy_router.requests_proxies_for(url)
        def _call():
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=self.settings.http_timeout_seconds,
                proxies=proxies,
            )
            response.raise_for_status()
            return response.json()

        return retry_call(_call)

    @staticmethod
    def _build_url(base_url: str, path: str) -> str:
        if base_url.endswith("/"):
            base = base_url
        else:
            base = f"{base_url}/"
        return urljoin(base, path.lstrip("/"))


def _candidate_requests(status: str, limit: int | None) -> list[dict[str, Any]]:
    safe_limit = limit or 100
    return [
        {
            "method": "GET",
            "path": "/purchases",
            "params": {"status": status, "limit": safe_limit},
        },
        {
            "method": "GET",
            "path": "/purchaseSessions",
            "params": {"status": status, "limit": safe_limit},
        },
        {
            "method": "POST",
            "path": "/purchases/search",
            "json": {"status": status, "limit": safe_limit, "page": 1},
        },
        {
            "method": "POST",
            "path": "/purchaseSessions/search",
            "json": {"status": status, "limit": safe_limit, "page": 1},
        },
    ]


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("data", "result", "items", "rows", "purchases", "sessions"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested

    return []


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
