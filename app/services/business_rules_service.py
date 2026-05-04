from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BusinessRule

T = TypeVar("T")


@dataclass
class BusinessRuleValue:
    key: str
    value: str
    source: str


class BusinessRulesService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def list_rules(self) -> list[BusinessRule]:
        return self.session.scalars(select(BusinessRule).order_by(BusinessRule.key.asc())).all()

    def get(self, key: str, default: str) -> BusinessRuleValue:
        row = self.session.scalar(select(BusinessRule).where(BusinessRule.key == key))
        if row is None:
            return BusinessRuleValue(key=key, value=str(default), source="env")
        return BusinessRuleValue(key=key, value=row.value, source="db")

    def get_typed(self, key: str, default: T, caster: Callable[[str], T]) -> T:
        value = self.get(key, str(default)).value
        try:
            return caster(value)
        except Exception:
            return default

    def set_rule(self, key: str, value: str, description: str | None = None) -> BusinessRule:
        row = self.session.scalar(select(BusinessRule).where(BusinessRule.key == key))
        if row is None:
            row = BusinessRule(key=key, value=value, description=description)
            self.session.add(row)
        else:
            row.value = value
            if description is not None:
                row.description = description
        self.session.commit()
        self.session.refresh(row)
        return row

    def defaults_map(self) -> dict[str, str]:
        s = self.settings
        return {
            "MIN_MARGIN_PERCENT": str(s.min_margin_percent),
            "MIN_OFFER_RELEVANCE_SCORE": str(s.min_offer_relevance_score),
            "DEFAULT_UNKNOWN_DELIVERY_COST": str(s.default_unknown_delivery_cost),
            "DELIVERY_MODE": getattr(s, "delivery_mode", "conservative"),
            "VAT_MODE": getattr(s, "vat_mode", "included"),
            "VAT_RATE": str(getattr(s, "vat_rate", 20.0)),
            "TAX_MODE": getattr(s, "tax_mode", "simplified_income_expense"),
            "PICKUP_ALLOWED": "true" if getattr(s, "pickup_allowed", True) else "false",
        }
