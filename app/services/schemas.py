from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class OfferSnapshot:
    offer_id: int | None
    item_name: str
    supplier_name: str
    unit_price: Decimal
    available_quantity: int
    delivery_price: Decimal | None


@dataclass
class SelectedOfferPortion:
    offer_id: int | None
    supplier_name: str
    used_quantity: int
    unit_price: Decimal
    delivery_price: Decimal
    delivery_price_was_default: bool


@dataclass
class ItemOptimizationResult:
    status: str
    required_quantity: int
    covered_quantity: int
    estimated_cost: Decimal | None
    unknown_delivery_used: bool
    selected_offers: list[SelectedOfferPortion]
