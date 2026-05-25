from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus

from app.config import get_settings
from app.utils.proxy import ProxyRouter

_RUBLE_PRICE_RE = re.compile(
    r"(?<!\d)(?:от\s+)?"
    r"(?P<int>\d{1,3}(?:[\s\u00A0\u202F]\d{3})+|\d{1,9})"
    r"(?:[.,](?P<frac>\d{1,2}))?\s*"
    r"(?:₽|руб\.?|р\.?)(?=\D|$)",
    flags=re.IGNORECASE,
)

_SERP_CONTAINER_SELECTORS: tuple[str, ...] = (
    "li.serp-item",
    ".serp-item",
    ".Organic",
    "article",
)

_TITLE_SELECTORS: tuple[str, ...] = (
    "h1",
    "h2",
    "h3",
    "a.OrganicTitle-Link",
    "a.Link.Link_theme_normal.OrganicTitle-Link",
    "a.link.organic__url",
)

_SNIPPET_SELECTORS: tuple[str, ...] = (
    ".OrganicTextContentSpan",
    ".organic__text",
    ".TextContainer",
    ".ExtendedText-Short",
    ".ExtendedText",
)

_LINK_SELECTORS: tuple[str, ...] = (
    "a.OrganicTitle-Link[href]",
    "a.link.organic__url[href]",
    "a[href]",
)


def parse_ruble_price_from_snippet(snippet: str) -> Decimal | None:
    try:
        text = str(snippet or "")
        match = _RUBLE_PRICE_RE.search(text)
        if not match:
            return None

        int_part = re.sub(r"[\s\u00A0\u202F]", "", match.group("int") or "")
        if not int_part.isdigit():
            return None

        frac_part = match.group("frac")
        if frac_part:
            return Decimal(f"{int_part}.{frac_part}")
        return Decimal(int_part)
    except Exception:
        return None


def parse_ruble_price_from_title_and_snippet(title: str, snippet: str) -> Decimal | None:
    title_text = str(title or "").strip()
    snippet_text = str(snippet or "").strip()
    joined_text = "\n".join(part for part in [title_text, snippet_text] if part)
    return parse_ruble_price_from_snippet(joined_text)


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

        normalized_query = quote_plus(str(query or "").strip())
        url = f"https://yandex.ru/search/?text={normalized_query}"
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

                selectors_js = {
                    "containers": list(_SERP_CONTAINER_SELECTORS),
                    "titles": list(_TITLE_SELECTORS),
                    "snippets": list(_SNIPPET_SELECTORS),
                    "links": list(_LINK_SELECTORS),
                }
                rows = page.evaluate(
                    r"""
                    ({containers, titles, snippets, links}) => {
                      const findText = (root, selectors) => {
                        for (const sel of selectors) {
                          const el = root.querySelector(sel);
                          const text = (el?.innerText || el?.textContent || '').trim();
                          if (text) return text;
                        }
                        return '';
                      };

                      const findHref = (root, selectors) => {
                        for (const sel of selectors) {
                          const href = (root.querySelector(sel)?.href || '').trim();
                          if (href && /^https?:\/\//i.test(href)) return href;
                        }
                        return '';
                      };

                      const output = [];
                      for (const containerSel of containers) {
                        const nodes = Array.from(document.querySelectorAll(containerSel));
                        for (const node of nodes) {
                          const title = findText(node, titles);
                          const url = findHref(node, links);
                          const snippet = findText(node, snippets) || (node.innerText || '').trim();
                          output.push({title, url, snippet});
                        }
                        if (output.length) break;
                      }
                      return output;
                    }
                    """,
                    selectors_js,
                )

                records: list[dict[str, Any]] = []
                for row in rows:
                    title = str((row or {}).get("title") or "").strip()
                    offer_url = str((row or {}).get("url") or "").strip()
                    snippet = str((row or {}).get("snippet") or "").strip()
                    if not title or not offer_url:
                        continue

                    price = parse_ruble_price_from_title_and_snippet(title, snippet)

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
