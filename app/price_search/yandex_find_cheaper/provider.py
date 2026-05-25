from __future__ import annotations

import json
from urllib.parse import urlparse

from app.config import get_settings
from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate, PriceSearchProvider
from app.price_search.normalization import normalize_delivery_price, normalize_price, normalize_quantity, normalize_region, normalize_url
from app.price_search.query_builder import build_search_queries
from app.price_search.relevance import calculate_offer_relevance
from app.price_search.yandex_find_cheaper.browser_agent import YandexBrowserAgent


class YandexFindCheaperProvider(PriceSearchProvider):
    provider_name = "yandex"

    def __init__(self) -> None:
        self.agent = YandexBrowserAgent()
        self.settings = get_settings()
        self.last_stage_counters: dict[str, int | str] = {}
        self.last_warnings: list[str] = []

    def get_last_diagnostics(self) -> dict[str, object]:
        return {
            "stage_counters": dict(self.last_stage_counters),
            "warnings": list(self.last_warnings),
        }

    def search_offers(self, item: PurchaseItem) -> list[MarketOfferCandidate]:
        stage_counters: dict[str, int | str] = {
            "blocked_or_captcha": 0,
            "empty_serp": 0,
            "no_relevant_rows": 0,
            "invalid_or_junk_url": 0,
            "no_price_signal": 0,
            "strict_reject": "N/A",
        }
        queries = build_search_queries(item)
        warnings: list[str] = []
        rows: list[dict] = []
        seen_urls: set[str] = set()
        for query in queries:
            batch_rows, batch_warnings = self.agent.search(query=query, limit=10)
            warnings.extend(batch_warnings)
            for warning in batch_warnings:
                warning_text = str(warning)
                if warning_text.startswith("captcha_or_blocked"):
                    stage_counters["blocked_or_captcha"] = int(stage_counters["blocked_or_captcha"]) + 1
                if warning_text.startswith("empty_serp"):
                    stage_counters["empty_serp"] = int(stage_counters["empty_serp"]) + 1
                if warning_text.startswith("no_relevant_rows"):
                    stage_counters["no_relevant_rows"] = int(stage_counters["no_relevant_rows"]) + 1
            for row in batch_rows:
                norm_url = normalize_url(str(row.get("url") or ""))
                dedup_key = norm_url or f"{row.get('title') or ''}|{row.get('unit_price') or ''}"
                if dedup_key in seen_urls:
                    continue
                seen_urls.add(dedup_key)
                rows.append(row)

        candidates: list[MarketOfferCandidate] = []
        for row in rows:
            parsed_unit_price = normalize_price(row.get("unit_price"))
            if parsed_unit_price is None or parsed_unit_price <= 0:
                stage_counters["no_price_signal"] = int(stage_counters["no_price_signal"]) + 1
                continue
            offer_url = normalize_url(str(row.get("url") or ""))
            if not _is_valid_http_url(offer_url):
                stage_counters["invalid_or_junk_url"] = int(stage_counters["invalid_or_junk_url"]) + 1
                continue
            if _is_procurement_domain_url(offer_url):
                stage_counters["invalid_or_junk_url"] = int(stage_counters["invalid_or_junk_url"]) + 1
                continue

            quantity, quantity_flags = normalize_quantity(row.get("available_quantity"))
            delivery_price, delivery_flags = normalize_delivery_price(row.get("delivery_price"))
            region, region_flags = normalize_region(row.get("region") or self.settings.price_search_region)

            candidate = MarketOfferCandidate(
                provider=self.provider_name,
                purchase_item_id=item.id,
                title=str(row.get("title") or item.item_name),
                url=offer_url,
                seller_name=row.get("seller_name") or None,
                region=region,
                unit_price=parsed_unit_price,
                available_quantity=quantity,
                delivery_price=delivery_price,
                delivery_days=None,
                raw_payload={
                    **row,
                    "_diagnostics": {
                        "stage_counters": stage_counters,
                        "warnings": warnings,
                    },
                },
                risk_flags=sorted(set(quantity_flags + delivery_flags + region_flags)),
                item_name=item.item_name,
            )
            relevance = calculate_offer_relevance(item, candidate)
            candidate.is_relevant = relevance.is_relevant
            candidate.relevance_score = relevance.score
            candidate.risk_flags = sorted(set(candidate.risk_flags + relevance.risk_flags))
            candidates.append(candidate)

        warnings.append(f"diagnostics_stage_counters:{json.dumps(stage_counters, ensure_ascii=False, sort_keys=True)}")
        self.last_stage_counters = dict(stage_counters)
        self.last_warnings = list(warnings)

        # Fail closed: when search is blocked/captcha/no parsable rows,
        # return no candidates so caller marks item as needs_manual_price_search.
        # This avoids persisting synthetic zero-price offers that inflate margin.
        if warnings and not candidates:
            return []

        return candidates


def _is_procurement_domain_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        return False
    blocked = (
        "zakupki.mos.ru",
        "market.mosreg.ru",
        "business.roseltorg.ru",
        "roseltorg.ru",
        "rts-tender.ru",
        "sberbank-ast.ru",
        "etp-ets.ru",
        "tektorg.ru",
        "goszakupki.gov.ru",
        "zakupki.gov.ru",
        "zakupki360.ru",
        "zakupki360.com",
    )
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in blocked)


def _is_valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
