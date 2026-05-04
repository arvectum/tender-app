from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class ManualOfferRow:
    purchase_external_id: str | None
    position_external_id: str | None
    item_name: str
    offer_title: str
    offer_url: str | None
    seller_name: str | None
    region: str | None
    unit_price: Decimal
    available_quantity: Decimal
    delivery_price: Decimal | None
    delivery_days: int | None
    is_relevant: bool | None
    relevance_score: float | None
    comment: str | None
    raw_payload: dict[str, Any] | None = None


@dataclass
class OfferImportResult:
    file_path: str
    total_rows: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
