from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.catalog.classifiers import classify_category
from app.catalog.dictionaries import load_dictionaries
from app.catalog.extractors import (
    extract_article,
    extract_brand,
    extract_color,
    extract_model,
    extract_numbers,
    extract_tokens,
    extract_units,
)
from app.catalog.rules import COMPATIBLE_KEYWORDS, ORIGINAL_KEYWORDS
from app.models import PurchaseItem
from app.price_search.normalization import normalize_title


@dataclass
class ItemAttributesExtracted:
    normalized_name: str
    category: str | None
    brand: str | None
    model: str | None
    article: str | None
    color: str | None
    size: str | None = None
    volume: str | None = None
    weight: str | None = None
    material: str | None = None
    package_quantity: int | None = None
    original_required: bool = False
    compatible_allowed: bool = True
    keywords: list[str] = field(default_factory=list)
    stopwords_removed: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    risk_flags: list[str] = field(default_factory=list)


def extract_item_attributes(item: PurchaseItem) -> ItemAttributesExtracted:
    dictionaries = load_dictionaries()
    raw_text = f"{item.item_name} {item.description or ''}".strip()
    normalized = normalize_title(raw_text)
    tokens = extract_tokens(normalized)
    stopwords_removed = [t for t in tokens if t not in set(dictionaries.stopwords)]

    normalized_upper = raw_text.upper()
    article = extract_article(normalized_upper)
    model = extract_model(normalized_upper, article=article)
    brand = extract_brand(tokens, dictionaries)
    color = extract_color(tokens)
    numbers = extract_numbers(normalized)
    units = extract_units(tokens, dictionaries.units)

    category, category_conf = classify_category(stopwords_removed, dictionaries)

    low_tokens = set(stopwords_removed)
    original_required = any(k in low_tokens for k in ORIGINAL_KEYWORDS)
    has_compatible_word = any(k in low_tokens for k in COMPATIBLE_KEYWORDS)
    compatible_allowed = not original_required
    if has_compatible_word and original_required:
        compatible_allowed = False

    package_quantity = None
    for idx, token in enumerate(stopwords_removed):
        if token.isdigit() and idx + 1 < len(stopwords_removed) and stopwords_removed[idx + 1] in {"уп", "упаковка"}:
            package_quantity = int(token)
            break
    if package_quantity is None:
        package_quantity = 1

    confidence = 0.35
    confidence += 0.18 if category else 0
    confidence += 0.12 if brand else 0
    confidence += 0.12 if model else 0
    confidence += 0.16 if article else 0
    confidence += 0.07 if color else 0
    confidence = min(1.0, confidence + category_conf * 0.15)

    risk_flags: list[str] = []
    if category is None:
        risk_flags.append("category_unknown")
    if article is None and model is None:
        risk_flags.append("model_article_unknown")

    return ItemAttributesExtracted(
        normalized_name=" ".join(stopwords_removed),
        category=category,
        brand=brand,
        model=model,
        article=article,
        color=color,
        package_quantity=package_quantity,
        original_required=original_required,
        compatible_allowed=compatible_allowed,
        keywords=stopwords_removed[:20],
        stopwords_removed=stopwords_removed,
        numbers=numbers,
        units=units,
        confidence_score=float(Decimal(str(round(confidence, 4)))),
        risk_flags=sorted(set(risk_flags)),
    )
