from __future__ import annotations

from dataclasses import dataclass, field

from app.catalog.dictionaries import load_dictionaries
from app.connectors.base import ParsedPurchase
from app.config import get_settings


SERVICE_WORK_KEYWORDS = [
    "услуга",
    "оказание услуг",
    "выполнение работ",
    "ремонт",
    "монтаж",
    "обслуживание",
    "сопровождение",
    "разработка",
    "настройка",
    "аренда",
    "обучение",
]

PRODUCT_KEYWORDS = [
    "поставка",
    "товар",
    "оборудование",
    "комплект",
    "изделие",
    "расходные материалы",
    "картридж",
    "бумага",
    "мебель",
    "техника",
    "запасные части",
]

MOSCOW_REGION_MARKERS = [
    "москва",
    "московская область",
    "77",
    "50",
]


@dataclass
class FilterDecision:
    include: bool
    reason: str
    risk_flags: list[str] = field(default_factory=list)


def filter_purchase(
    purchase: ParsedPurchase,
    required_status: str = "Прием предложений",
) -> FilterDecision:
    status_value = (purchase.status or "").strip().lower()
    required_status_value = (required_status or "").strip().lower()
    if required_status_value and status_value != required_status_value:
        return FilterDecision(include=False, reason="status_mismatch")

    if not purchase.items:
        return FilterDecision(include=False, reason="no_items")

    if _is_outside_target_regions(purchase):
        return FilterDecision(include=False, reason="outside_target_region")

    type_decision = _evaluate_type(purchase)
    if type_decision == "service_or_work":
        return FilterDecision(include=False, reason="service_or_work")

    if type_decision == "uncertain":
        return FilterDecision(include=True, reason="uncertain_type", risk_flags=["needs_manual_type_review"])

    return FilterDecision(include=True, reason="ok")


def _evaluate_type(purchase: ParsedPurchase) -> str:
    dictionaries = load_dictionaries()
    category_keywords: list[str] = []
    for payload in dictionaries.categories.values():
        category_keywords.extend([str(x).lower() for x in (payload or {}).get("keywords", [])])
    service_work_keywords = sorted(set(SERVICE_WORK_KEYWORDS + dictionaries.service_keywords + dictionaries.work_keywords))
    product_keywords = sorted(set(PRODUCT_KEYWORDS + category_keywords))

    title_text = (purchase.raw_payload or {}).get("title") if purchase.raw_payload else None
    base_text = " ".join(
        [
            purchase.external_id,
            purchase.title or "",
            purchase.status or "",
            purchase.region or "",
            purchase.customer_name or "",
            str(title_text or ""),
        ]
    ).lower()

    item_text = " ".join(
        f"{item.name} {item.description or ''} {item.okpd2 or ''}".lower() for item in purchase.items
    )
    joined = f"{base_text} {item_text}".strip()

    has_service_words = any(keyword in joined for keyword in service_work_keywords)
    has_product_words = any(keyword in joined for keyword in product_keywords)

    if has_service_words and not has_product_words:
        return "service_or_work"

    if has_product_words:
        return "goods"

    # Heuristic fallback: if most items have unit and quantity but no service markers,
    # treat as uncertain instead of excluding.
    return "uncertain"


def _is_outside_target_regions(purchase: ParsedPurchase) -> bool:
    settings = get_settings()
    if not settings.target_region_codes:
        return False

    region_text = (purchase.region or "").lower().strip()
    if not region_text:
        return False

    if any(marker in region_text for marker in MOSCOW_REGION_MARKERS):
        return False

    for code in settings.target_region_codes:
        normalized = code.strip().lower()
        if normalized and normalized in region_text:
            return False

    return True
