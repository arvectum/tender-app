from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.catalog.normalizer import extract_item_attributes
from app.matching.explanations import format_match_reason
from app.matching.scoring import fuzzy_ratio, token_jaccard
from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate
from app.price_search.normalization import normalize_title


ARTICLE_RE = re.compile(r"\b[A-ZА-Я]{1,4}\d{2,}[A-ZА-Я0-9\-]*\b")
REJECT_COMPATIBLE = {"совместимый", "аналог", "неоригинальный", "replacement", "compatible"}
OFFER_CATEGORY_KEYWORDS = {
    "cartridges": {"картридж", "тонер", "барабан"},
    "paper": {"бумага", "a4", "а4"},
    "folders": {"папка"},
    "furniture": {"стул", "стол", "шкаф", "тумба"},
    "computer_equipment": {"монитор", "клавиатура", "мышь", "ноутбук", "принтер"},
}


@dataclass
class MatchResult:
    is_match: bool
    score: float
    hard_reject: bool
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)
    mismatched_fields: list[str] = field(default_factory=list)
    hard_reject_reason: str | None = None


def _extract_offer_article(title: str) -> str | None:
    match = ARTICLE_RE.search(title.upper())
    return match.group(0) if match else None


def _detect_offer_category(tokens: set[str]) -> str | None:
    for category, keywords in OFFER_CATEGORY_KEYWORDS.items():
        if any(token in keywords for token in tokens):
            return category
    return None


def match_offer_to_item(
    item: PurchaseItem,
    offer: MarketOfferCandidate,
    min_score: float = 0.78,
    supplier_status: str = "unknown",
) -> MatchResult:
    attrs = extract_item_attributes(item)
    offer_title = normalize_title(offer.title or "")
    offer_tokens = set(offer_title.split())
    item_tokens = set((attrs.normalized_name or "").split())

    matched_fields: list[str] = []
    mismatched_fields: list[str] = []
    risk_flags: list[str] = []
    hard_reject_reason: str | None = None

    offer_article = _extract_offer_article(offer.title or "")
    if attrs.article and offer_article and attrs.article.upper() != offer_article.upper():
        hard_reject_reason = "different_article"

    if attrs.original_required and any(word in offer_tokens for word in REJECT_COMPATIBLE):
        hard_reject_reason = "compatible_when_original_required"

    offer_category = _detect_offer_category(offer_tokens)
    if attrs.category and offer_category and attrs.category != offer_category:
        hard_reject_reason = "different_category"

    if hard_reject_reason:
        reasons = format_match_reason(matched_fields, mismatched_fields, hard_reject_reason=hard_reject_reason)
        return MatchResult(
            is_match=False,
            score=0.0,
            hard_reject=True,
            reasons=reasons,
            risk_flags=["hard_reject"],
            matched_fields=matched_fields,
            mismatched_fields=mismatched_fields,
            hard_reject_reason=hard_reject_reason,
        )

    score = 0.0

    if attrs.article and offer_article and attrs.article.upper() == offer_article.upper():
        score += 0.35
        matched_fields.append("article")
    elif attrs.article:
        mismatched_fields.append("article")

    if attrs.model and attrs.model.lower() in offer_tokens:
        score += 0.25
        matched_fields.append("model")
    elif attrs.model:
        mismatched_fields.append("model")

    if attrs.brand and attrs.brand.lower() in offer_tokens:
        score += 0.15
        matched_fields.append("brand")
    elif attrs.brand:
        mismatched_fields.append("brand")

    if attrs.category and attrs.category == offer_category:
        score += 0.15
        matched_fields.append("category")
    elif attrs.category and offer_category is not None:
        mismatched_fields.append("category")

    token_sim = token_jaccard(item_tokens, offer_tokens)
    score += min(0.10, token_sim * 0.10)

    if attrs.color and attrs.color in offer_tokens:
        score += 0.05
        matched_fields.append("color")
    elif attrs.color:
        mismatched_fields.append("color")

    fz = fuzzy_ratio(attrs.normalized_name, offer_title)
    score = min(1.0, score + fz * 0.05)

    if offer.delivery_price is None:
        score -= 0.05
        risk_flags.append("delivery_unknown")
    if offer.available_quantity is None:
        score -= 0.05
        risk_flags.append("quantity_unknown")
    if not offer.region:
        score -= 0.03
        risk_flags.append("region_unknown")

    if supplier_status == "trusted":
        score += 0.03
        matched_fields.append("trusted_supplier_bonus")
    elif supplier_status == "risky":
        score -= 0.03
        risk_flags.append("risky_supplier")

    score = max(0.0, min(1.0, score))
    is_match = score >= min_score
    if not is_match:
        risk_flags.append("low_relevance")

    reasons = format_match_reason(matched_fields, mismatched_fields)
    return MatchResult(
        is_match=is_match,
        score=round(score, 4),
        hard_reject=False,
        reasons=reasons,
        risk_flags=sorted(set(risk_flags)),
        matched_fields=matched_fields,
        mismatched_fields=mismatched_fields,
        hard_reject_reason=None,
    )
