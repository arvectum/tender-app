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
)


def build_search_query(item: PurchaseItem) -> str:
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

    extra_words = [word.strip() for word in settings.price_search_extra_words if word.strip()]
    exclusion_parts = [f"-site:{domain}" for domain in PROCUREMENT_DOMAINS]
    parts = _unique_preserve([p for p in base_parts if p] + extra_words + [settings.price_search_region] + exclusion_parts)
    query = " ".join(parts)
    query = re.sub(r"\s+", " ", query).strip()
    return query


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
