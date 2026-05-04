from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Purchase, PurchaseItem
from app.utils.logging import get_file_logger
from app.utils.time import utc_now


validation_logger = get_file_logger("validation.data", "validation.log")


@dataclass
class DataValidationSummary:
    checked_purchases: int = 0
    low_quality: int = 0
    medium_quality: int = 0
    high_quality: int = 0
    warnings_count: int = 0


class DataValidationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def validate(self, purchase_id: int | None = None) -> DataValidationSummary:
        stmt = select(Purchase).options(selectinload(Purchase.items))
        if purchase_id is not None:
            stmt = stmt.where(Purchase.id == purchase_id)

        purchases = self.session.scalars(stmt).all()
        summary = DataValidationSummary(checked_purchases=len(purchases))

        for purchase in purchases:
            quality, warnings = self._validate_purchase(purchase, purchase.items or [])
            purchase.data_quality = quality
            purchase.data_quality_warnings_json = warnings
            summary.warnings_count += len(warnings)

            if quality == "low":
                summary.low_quality += 1
            elif quality == "medium":
                summary.medium_quality += 1
            else:
                summary.high_quality += 1

            if warnings:
                validation_logger.warning(
                    "data validation warnings | purchase_id=%s external_id=%s quality=%s warnings=%s",
                    purchase.id,
                    purchase.external_id,
                    quality,
                    "; ".join(warnings),
                )

        self.session.commit()
        return summary

    def _validate_purchase(self, purchase: Purchase, items: list[PurchaseItem]) -> tuple[str, list[str]]:
        severe_count = 0
        warning_count = 0
        warnings: list[str] = []
        now = utc_now()

        if not (purchase.external_id and str(purchase.external_id).strip()):
            severe_count += 1
            warnings.append("external_id is missing")

        if purchase.submission_deadline is None:
            severe_count += 1
            warnings.append("deadline is missing")
        elif purchase.submission_deadline <= now:
            severe_count += 1
            warnings.append("deadline is expired")

        max_total_price = Decimal(str(purchase.max_total_price or 0))
        if max_total_price <= 0:
            severe_count += 1
            warnings.append("max_total_price must be > 0")

        for item in items:
            quantity = Decimal(str(item.quantity or 0))
            if quantity <= 0:
                severe_count += 1
                warnings.append(f"item#{item.id} quantity must be > 0")

            if item.max_unit_price is not None and Decimal(str(item.max_unit_price)) < 0:
                warning_count += 1
                warnings.append(f"item#{item.id} max_unit_price must be >= 0")

        if severe_count > 0:
            return "low", warnings
        if warning_count > 0:
            return "medium", warnings
        return "high", warnings
