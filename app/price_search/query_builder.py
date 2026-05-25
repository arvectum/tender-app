from __future__ import annotations

import re

from app.catalog.normalizer import extract_item_attributes
from app.config import get_settings
from app.models import PurchaseItem
from app.price_search.normalization import normalize_title


NOISE_WORDS = {"поставка", "закупка", "закупки", "нмц", "для"}

PROCUREMENT_DOMAINS = (
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


def build_search_query(item: PurchaseItem) -> str:
    queries = build_search_queries(item)
    return queries[0] if queries else ""


def build_search_queries(item: PurchaseItem) -> list[str]:
    settings = get_settings()
    attrs = item.attributes if hasattr(item, "attributes") and item.attributes is not None else extract_item_attributes(item)

    base_parts: list[str] = []
    if attrs.brand:
        base_parts.append(attrs.brand)
    if attrs.article:
        base_parts.append(attrs.article)
    if attrs.model and attrs.model not in base_parts:
        base_parts.append(attrs.model)
    if attrs.original_required:
        base_parts.append("оригинальный")
    if attrs.category == "cartridges":
        base_parts.append("картридж")
    elif attrs.category == "paper":
        base_parts.append("бумага")
    elif attrs.category == "furniture":
        base_parts.append("мебель")

    if attrs.color:
        base_parts.append(attrs.color)

    tail_tokens = _fallback_tokens(item)
    base_parts.extend(tail_tokens)

    fallback_tokens = _fallback_tokens(item)
    head_tokens = [token for token in [attrs.brand, attrs.article, attrs.model, attrs.color] if token]
    category_token = _category_token(attrs.category)
    if category_token:
        head_tokens.append(category_token)

    extra_words = [word.strip() for word in settings.price_search_extra_words if word.strip()]
    exclusion_parts = [f"-site:{domain}" for domain in PROCUREMENT_DOMAINS]

    primary = _compose_query(base_parts, extra_words, settings.price_search_region, exclusion_parts)
    compact = _compose_query(head_tokens + fallback_tokens[:4], [], settings.price_search_region, exclusion_parts)
    fallback = _compose_query(fallback_tokens, [], settings.price_search_region, exclusion_parts)

    queries = [q for q in [primary, compact, fallback] if q]
    if settings.price_search_mode == "yandex":
        queries.append(_append_price_intent_if_needed(primary))
    return _unique_preserve([q for q in queries if q])


def _category_token(category: str | None) -> str | None:
    if category == "cartridges":
        return "картридж"
    if category == "paper":
        return "бумага"
    if category == "furniture":
        return "мебель"
    return None


def _compose_query(core_parts: list[str], extra_words: list[str], region: str, exclusion_parts: list[str]) -> str:
    parts = _unique_preserve([p for p in core_parts if p] + extra_words + [region] + exclusion_parts)
    query = " ".join(parts)
    return re.sub(r"\s+", " ", query).strip()


def _fallback_tokens(item: PurchaseItem) -> list[str]:
    text = normalize_title(f"{item.item_name} {item.description or ''}")
    tokens = text.split()
    filtered: list[str] = []
    skip_next_unit = False
    for i, token in enumerate(tokens):
        if token in NOISE_WORDS:
            continue
        if token.isdigit() and i + 1 < len(tokens) and tokens[i + 1] in {"шт", "штук"}:
            skip_next_unit = True
            continue
        if skip_next_unit and token in {"шт", "штук"}:
            skip_next_unit = False
            continue
        filtered.append(token)
    return filtered[:10]


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        norm = value.lower()
        if norm in seen:
            continue
        seen.add(norm)
        result.append(value)
    return result


def _append_price_intent_if_needed(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "цена" in lowered and "купить" in lowered:
        return text
    return f"{text} цена купить"
