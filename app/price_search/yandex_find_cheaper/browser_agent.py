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

_DDG_CONTAINER_SELECTORS: tuple[str, ...] = (
    ".result",
    ".results_links",
)

_DDG_TITLE_SELECTORS: tuple[str, ...] = (
    "a.result__a",
    "h2.result__title a",
)

_DDG_SNIPPET_SELECTORS: tuple[str, ...] = (
    ".result__snippet",
    ".result__body",
)

_DDG_LINK_SELECTORS: tuple[str, ...] = (
    "a.result__a[href]",
    "h2.result__title a[href]",
)

_BING_CONTAINER_SELECTORS: tuple[str, ...] = (
    "#b_results .b_algo",
    ".b_algo",
    "li.b_algo",
)

_BING_TITLE_SELECTORS: tuple[str, ...] = (
    "h2 a",
    "a",
)

_BING_SNIPPET_SELECTORS: tuple[str, ...] = (
    ".b_caption p",
    ".b_caption",
    ".b_snippet",
)

_BING_LINK_SELECTORS: tuple[str, ...] = (
    "h2 a[href]",
    "a[href]",
)

_TOKEN_SPLIT_RE = re.compile(r"[^a-zа-яё0-9]+", flags=re.IGNORECASE)
_RELEVANCE_STOPWORDS = {
    "и",
    "в",
    "на",
    "для",
    "по",
    "из",
    "под",
    "при",
    "с",
    "со",
    "к",
    "от",
    "до",
    "за",
    "о",
    "об",
    "товар",
    "купить",
    "цена",
    "москва",
}

_JUNK_URL_PATTERNS: tuple[str, ...] = (
    "yabs.yandex",
    "yandex.ru/clck",
    "yandex.ru/images",
    "yandex.ru/video",
    "utm_source=yandex",
)

_BLOCK_MARKERS: tuple[str, ...] = (
    "капча",
    "captcha",
    "доступ ограничен",
    "подозрительный трафик",
    "unusual traffic",
    "робот",
    "robot",
)

_CYR_LAT_CONFUSABLES = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "н",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
    }
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


def _extract_price_from_offer_page(
    context: Any,
    offer_url: str,
    *,
    timeout_ms: int,
    max_chars: int = 20000,
) -> Decimal | None:
    page = None
    try:
        page = context.new_page()
        page.goto(offer_url, wait_until="domcontentloaded", timeout=max(1000, int(timeout_ms)))
        body_text = str(page.inner_text("body") or "")
        if max_chars > 0:
            body_text = body_text[:max_chars]
        return parse_ruble_price_from_snippet(body_text)
    except Exception:
        return None
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass


def _open_browser_context(playwright_ctx: Any, *, settings: Any, proxy_router: Any, url: str, warnings: list[str]) -> tuple[Any, Any]:
    if settings.yandex_browser_use_chrome_profile and settings.yandex_cdp_url:
        try:
            browser = playwright_ctx.chromium.connect_over_cdp(settings.yandex_cdp_url, timeout=max(1000, int(settings.connector_request_timeout_seconds * 1000)))
            context = browser.contexts[0] if browser.contexts else browser.new_context(user_agent=settings.connector_user_agent)
            warnings.append("session_connected:cdp")
            return context, browser
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"auth_or_session_missing:cdp:{exc.__class__.__name__}")

    decision = proxy_router.decide(url)
    launch_kwargs: dict[str, Any] = {"headless": settings.playwright_headless}
    if decision.use_proxy and decision.proxy_url:
        launch_kwargs["proxy"] = {"server": decision.proxy_url}

    if settings.yandex_browser_use_chrome_profile:
        try:
            launch_kwargs_profile = dict(launch_kwargs)
            launch_kwargs_profile["channel"] = "chrome"
            launch_kwargs_profile["headless"] = False
            context = playwright_ctx.chromium.launch_persistent_context(
                user_data_dir=str(settings.yandex_chrome_user_data_dir),
                args=[f"--profile-directory={settings.yandex_chrome_profile_directory}"],
                **launch_kwargs_profile,
            )
            warnings.append("session_connected:chrome_profile")
            return context, context
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"auth_or_session_missing:chrome_profile:{exc.__class__.__name__}")

    browser = playwright_ctx.chromium.launch(**launch_kwargs)
    context = browser.new_context(user_agent=settings.connector_user_agent)
    return context, browser


class YandexBrowserAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.proxy_router = ProxyRouter.from_settings(self.settings)

    def search(self, query: str, limit: int = 8) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        query_terms = _extract_query_core_terms(query)
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"playwright unavailable: {exc}")
            return [], warnings

        endpoint_plan = _build_yandex_endpoint_plan(query)
        fallback_plan = _build_fallback_endpoint_plan(query)

        try:
            with sync_playwright() as p:
                for endpoint_name, url in (*endpoint_plan, *fallback_plan):
                    context = None
                    browser_or_context = None
                    page = None
                    try:
                        context, browser_or_context = _open_browser_context(
                            p,
                            settings=self.settings,
                            proxy_router=self.proxy_router,
                            url=url,
                            warnings=warnings,
                        )
                        page = context.new_page()
                        page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=int(self.settings.connector_request_timeout_seconds * 1000),
                        )
                        page_text = (page.inner_text("body") or "").lower()
                        if endpoint_name.startswith("ddg") and _is_ddg_rate_limited_or_blocked(page_text):
                            warnings.append(f"captcha_or_blocked:{endpoint_name}")
                            continue
                        if _is_blocked_response(page_text):
                            warnings.append(f"captcha_or_blocked:{endpoint_name}")
                            continue

                        rows = _extract_serp_rows(page, endpoint_name=endpoint_name)
                        if not rows:
                            warnings.append(f"empty_serp:{endpoint_name}")
                            continue

                        records: list[dict[str, Any]] = []
                        for row in rows:
                            title = str((row or {}).get("title") or "").strip()
                            offer_url = str((row or {}).get("url") or "").strip()
                            snippet = str((row or {}).get("snippet") or "").strip()
                            if not title or not offer_url:
                                continue
                            if _is_junk_offer_url(offer_url):
                                continue
                            if not _has_relevance_signal(query_terms, title, snippet):
                                continue

                            price = parse_ruble_price_from_title_and_snippet(title, snippet)
                            if price is None and endpoint_name == "ddg_html":
                                page_timeout_ms = int(self.settings.connector_request_timeout_seconds * 1000)
                                offer_timeout_ms = max(1000, min(page_timeout_ms, 5000))
                                offer_page_price = _extract_price_from_offer_page(
                                    context,
                                    offer_url,
                                    timeout_ms=offer_timeout_ms,
                                )
                                if offer_page_price is not None:
                                    price = offer_page_price
                                    warnings.append("price_from_offer_page:ddg_html")
                            relevance_score = _calculate_relevance_score(query_terms, title, snippet)

                            records.append(
                                {
                                    "title": title,
                                    "url": offer_url,
                                    "snippet": snippet,
                                    "unit_price": price,
                                    "_relevance_score": relevance_score,
                                }
                            )

                        records.sort(key=lambda r: (float(r.get("_relevance_score") or 0.0), 1 if r.get("unit_price") else 0), reverse=True)
                        records = records[: max(0, int(limit))]
                        for record in records:
                            record.pop("_relevance_score", None)

                        if records:
                            if _is_fallback_endpoint(endpoint_name):
                                warnings.append(f"fallback_success:{endpoint_name}")
                            return records, warnings
                        if _is_fallback_endpoint(endpoint_name):
                            warnings.append(f"fallback_empty:{endpoint_name}")
                        warnings.append(f"no_relevant_rows:{endpoint_name}")
                        warnings.append(f"parse_empty:{endpoint_name}")
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(f"yandex_search_failed:{endpoint_name}: {exc}")
                    finally:
                        if page is not None:
                            try:
                                page.close()
                            except Exception:
                                pass
                        if browser_or_context is not None:
                            try:
                                browser_or_context.close()
                            except Exception:
                                pass

                rescue_records = _run_non_serp_rescue(
                    p,
                    query=query,
                    query_terms=query_terms,
                    limit=limit,
                    warnings=warnings,
                    settings=self.settings,
                    proxy_router=self.proxy_router,
                )
                if rescue_records:
                    return rescue_records, warnings
                warnings.append("non_serp_rescue_exhausted")
                return [], warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"yandex_search_failed: {exc}")
            return [], warnings


def _build_yandex_endpoint_plan(query: str) -> tuple[tuple[str, str], ...]:
    normalized_query = quote_plus(str(query or "").strip())
    return (
        ("desktop", f"https://yandex.ru/search/?text={normalized_query}"),
        ("touch", f"https://yandex.ru/search/touch/?text={normalized_query}"),
    )


def _build_fallback_endpoint_plan(query: str) -> tuple[tuple[str, str], ...]:
    normalized_query = quote_plus(str(query or "").strip())
    return (
        ("ddg_html", f"https://html.duckduckgo.com/html/?q={normalized_query}"),
        ("bing_html", f"https://www.bing.com/search?q={normalized_query}&setlang=ru-ru"),
    )


def _build_marketplace_rescue_plan(query: str) -> tuple[tuple[str, str], ...]:
    normalized_query = quote_plus(str(query or "").strip())
    return (
        ("wb_direct", f"https://www.wildberries.ru/catalog/0/search.aspx?search={normalized_query}"),
        ("ozon_direct", f"https://www.ozon.ru/search/?text={normalized_query}"),
        ("ym_direct", f"https://market.yandex.ru/search?text={normalized_query}"),
    )


def _run_non_serp_rescue(
    playwright_ctx: Any,
    *,
    query: str,
    query_terms: set[str],
    limit: int,
    warnings: list[str],
    settings: Any,
    proxy_router: Any,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for endpoint_name, url in _build_marketplace_rescue_plan(query):
        context = None
        browser_or_context = None
        page = None
        try:
            context, browser_or_context = _open_browser_context(
                playwright_ctx,
                settings=settings,
                proxy_router=proxy_router,
                url=url,
                warnings=warnings,
            )
            page = context.new_page()
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(settings.connector_request_timeout_seconds * 1000),
            )
            body_text = str(page.inner_text("body") or "")
            if _is_blocked_response(body_text.lower()):
                warnings.append(f"captcha_or_blocked:{endpoint_name}")
                continue

            compact_text = " ".join(body_text.split())[:20000]
            price = parse_ruble_price_from_snippet(compact_text)
            if price is None or price <= 0:
                warnings.append(f"non_serp_rescue_empty:{endpoint_name}")
                continue

            synthetic_title = f"{endpoint_name} search: {query}".strip()
            if not _has_relevance_signal(query_terms, synthetic_title, compact_text[:2000]):
                warnings.append(f"non_serp_rescue_no_relevance:{endpoint_name}")
                warnings.append(f"parse_empty:{endpoint_name}")
                continue

            records.append(
                {
                    "title": synthetic_title,
                    "url": url,
                    "snippet": compact_text[:500],
                    "unit_price": price,
                    "source": endpoint_name,
                    "offer_url": url,
                }
            )
            warnings.append(f"non_serp_rescue_success:{endpoint_name}")
            if len(records) >= max(1, int(limit)):
                break
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"non_serp_rescue_failed:{endpoint_name}:{exc}")
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if browser_or_context is not None:
                try:
                    browser_or_context.close()
                except Exception:
                    pass
    return records


def _is_blocked_response(page_text: str) -> bool:
    lowered = str(page_text or "").lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _is_ddg_rate_limited_or_blocked(page_text: str) -> bool:
    lowered = str(page_text or "").lower()
    if not lowered:
        return False
    ddg_markers = (
        "automated requests",
        "please complete the following challenge",
        "unusual traffic",
        "captcha",
    )
    return any(marker in lowered for marker in ddg_markers)


def _extract_serp_rows(page: Any, endpoint_name: str = "desktop") -> list[dict[str, Any]]:
    if endpoint_name.startswith("ddg"):
        selectors_js = {
            "containers": list(_DDG_CONTAINER_SELECTORS),
            "titles": list(_DDG_TITLE_SELECTORS),
            "snippets": list(_DDG_SNIPPET_SELECTORS),
            "links": list(_DDG_LINK_SELECTORS),
        }
    elif endpoint_name.startswith("bing"):
        selectors_js = {
            "containers": list(_BING_CONTAINER_SELECTORS),
            "titles": list(_BING_TITLE_SELECTORS),
            "snippets": list(_BING_SNIPPET_SELECTORS),
            "links": list(_BING_LINK_SELECTORS),
        }
    else:
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
    return [row for row in rows if isinstance(row, dict)]


def _extract_query_core_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for raw in _TOKEN_SPLIT_RE.split(str(query or "").lower()):
        token_variants = _expand_token_variants(raw)
        for token in token_variants:
            if len(token) <= 1:
                continue
            if token in _RELEVANCE_STOPWORDS:
                continue
            if token == "site":
                continue
            terms.add(token)
    return terms


def _expand_token_variants(raw: str) -> set[str]:
    token = str(raw or "").strip().lower()
    if not token:
        return set()
    variants: set[str] = {token}

    if "-" in token:
        variants.add(token.replace("-", ""))
        variants.update(part for part in token.split("-") if part)
    if "/" in token:
        variants.add(token.replace("/", ""))
        variants.update(part for part in token.split("/") if part)

    if re.search(r"[a-z].*[а-яё]|[а-яё].*[a-z]", token):
        variants.add(token.translate(_CYR_LAT_CONFUSABLES))
    for variant in list(variants):
        variants.update(_split_alnum_boundaries(variant))
    return {v for v in variants if v}


def _split_alnum_boundaries(token: str) -> set[str]:
    parts = re.findall(r"[a-zа-яё]+|\d+", token, flags=re.IGNORECASE)
    if len(parts) <= 1:
        return set()
    return {part.lower() for part in parts if part}


def _calculate_relevance_score(query_terms: set[str], title: str, snippet: str) -> float:
    if not query_terms:
        return 0.0
    haystack_terms = _extract_query_core_terms(f"{title} {snippet}")
    if not haystack_terms:
        return 0.0
    overlap = query_terms.intersection(haystack_terms)
    if not overlap:
        return 0.0
    return len(overlap) / max(len(query_terms), 1)


def _is_junk_offer_url(url: str) -> bool:
    lowered = str(url or "").strip().lower()
    if not lowered:
        return True
    return any(pattern in lowered for pattern in _JUNK_URL_PATTERNS)


def _has_relevance_signal(query_terms: set[str], title: str, snippet: str) -> bool:
    if not query_terms:
        return True
    return _calculate_relevance_score(query_terms, title, snippet) > 0


def _is_fallback_endpoint(endpoint_name: str) -> bool:
    lowered = str(endpoint_name or "").lower()
    return lowered.startswith("ddg") or lowered.startswith("bing")
