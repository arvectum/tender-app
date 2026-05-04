from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.config import get_settings
from app.utils.proxy import ProxyRouter


class YandexBrowserAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.proxy_router = ProxyRouter.from_settings(self.settings)

    def search(self, query: str, limit: int = 8) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright unavailable: {exc}")
            return [], warnings

        url = f"https://yandex.ru/search/?text={query}"
        decision = self.proxy_router.decide(url)

        try:
            with sync_playwright() as p:
                launch_kwargs: dict[str, Any] = {"headless": True}
                if decision.use_proxy and decision.proxy_url:
                    launch_kwargs["proxy"] = {"server": decision.proxy_url}

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(user_agent=self.settings.connector_user_agent)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=int(self.settings.connector_request_timeout_seconds * 1000))

                page_text = (page.inner_text("body") or "").lower()
                if "капча" in page_text or "captcha" in page_text:
                    warnings.append("captcha_or_blocked")
                    context.close()
                    browser.close()
                    return [], warnings

                rows = page.eval_on_selector_all(
                    "li.serp-item",
                    "elements => elements.map(e => ({title: (e.querySelector('h2')?.innerText || '').trim(), url: e.querySelector('a')?.href || '', snippet: (e.innerText || '').trim()}))",
                )

                records: list[dict[str, Any]] = []
                for row in rows:
                    title = str((row or {}).get("title") or "").strip()
                    offer_url = str((row or {}).get("url") or "").strip()
                    snippet = str((row or {}).get("snippet") or "").strip()
                    if not title or not offer_url:
                        continue

                    price_match = re.search(r"(\d[\d\s]{1,12})\s?[₽рр.]", snippet)
                    price = None
                    if price_match:
                        try:
                            price = Decimal(price_match.group(1).replace(" ", ""))
                        except Exception:
                            price = None

                    records.append(
                        {
                            "title": title,
                            "url": offer_url,
                            "snippet": snippet,
                            "unit_price": price,
                        }
                    )
                    if len(records) >= limit:
                        break

                context.close()
                browser.close()
                return records, warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"yandex_search_failed: {exc}")
            return [], warnings
