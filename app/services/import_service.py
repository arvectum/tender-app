from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.connectors.base import ParsedPurchase, ParsedPurchaseItem
from app.models import ImportJob, Purchase, PurchaseItem
from app.services.purchase_filter_service import filter_purchase
from app.utils.logging import get_file_logger
from app.utils.time import utc_now


import_logger = get_file_logger("import", "import.log")


@dataclass
class ImportResult:
    source: str
    found_count: int = 0
    filtered_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)


class ImportService:
    def __init__(self, session: Session, save_raw: bool = False) -> None:
        self.session = session
        self.save_raw = save_raw
        self.settings = get_settings()

    def upsert_purchase(self, parsed_purchase: ParsedPurchase) -> tuple[Purchase, bool]:
        purchase = self.session.scalar(
            select(Purchase).where(
                Purchase.source == parsed_purchase.source,
                Purchase.external_id == parsed_purchase.external_id,
            )
        )

        is_created = purchase is None
        if is_created:
            purchase = Purchase(
                source=parsed_purchase.source,
                external_id=parsed_purchase.external_id,
                title=_safe_title(parsed_purchase),
                parsed_at=utc_now(),
                source_version=1,
            )
            self.session.add(purchase)
        elif self.settings.real_run_mode:
            self._save_source_version_snapshot(purchase)

        purchase.title = _safe_title(parsed_purchase)
        purchase.url = parsed_purchase.url
        purchase.status = parsed_purchase.status
        purchase.region = parsed_purchase.region
        purchase.region_code = _extract_region_code(parsed_purchase.region)
        purchase.customer_name = parsed_purchase.customer_name
        purchase.submission_deadline = parsed_purchase.submission_deadline
        purchase.commission_fee_amount = _quantize_money(parsed_purchase.commission_fee_amount)
        purchase.security_amount = _quantize_money(parsed_purchase.security_amount)
        purchase.max_total_price = _quantize_money(parsed_purchase.max_total_price)
        purchase.created_at_source = parsed_purchase.created_at_source
        purchase.parsed_at = utc_now()
        purchase.risk_flags = list(parsed_purchase.risk_flags)
        purchase.raw_payload = parsed_purchase.raw_payload if self.save_raw else None

        return purchase, is_created

    def _save_source_version_snapshot(self, purchase: Purchase) -> None:
        snapshot = {
            "source_version": purchase.source_version or 1,
            "saved_at": utc_now().isoformat(),
            "title": purchase.title,
            "status": purchase.status,
            "region": purchase.region,
            "submission_deadline": purchase.submission_deadline.isoformat() if purchase.submission_deadline else None,
            "max_total_price": str(purchase.max_total_price) if purchase.max_total_price is not None else None,
        }
        history = list(purchase.source_history_json or [])
        history.append(snapshot)
        purchase.source_history_json = history[-20:]
        purchase.source_version = int(purchase.source_version or 1) + 1

    def upsert_purchase_items(self, purchase: Purchase, items: list[ParsedPurchaseItem]) -> tuple[list[PurchaseItem], int, int]:
        existing_items = {
            item.position_hash: item
            for item in self.session.scalars(
                select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id)
            ).all()
        }

        upserted: list[PurchaseItem] = []
        created = 0
        updated = 0

        for parsed_item in items:
            position_hash = build_position_hash(parsed_item)
            existing = existing_items.get(position_hash)
            if existing is None and parsed_item.position_external_id is None:
                existing = self.session.scalar(
                    select(PurchaseItem).where(
                        PurchaseItem.purchase_id == purchase.id,
                        PurchaseItem.position_external_id.is_(None),
                        PurchaseItem.item_name == parsed_item.name,
                    )
                )
            if existing is None:
                existing = PurchaseItem(
                    purchase_id=purchase.id,
                    position_hash=position_hash,
                )
                self.session.add(existing)
                created += 1
            else:
                updated += 1

            existing.position_external_id = parsed_item.position_external_id
            existing.position_hash = position_hash
            existing.item_name = parsed_item.name
            existing.description = parsed_item.description
            existing.okpd2 = parsed_item.okpd2
            existing.quantity = parsed_item.quantity
            existing.unit = parsed_item.unit
            existing.max_unit_price = _quantize_money(parsed_item.max_unit_price)
            existing.max_total_price = _quantize_money(parsed_item.max_total_price)
            existing.delivery_region = parsed_item.delivery_region
            existing.delivery_address = parsed_item.delivery_address
            existing.delivery_terms = parsed_item.delivery_terms
            existing.raw_payload = parsed_item.raw_payload if self.save_raw else None

            upserted.append(existing)

        return upserted, created, updated

    def import_purchases(
        self,
        source: str,
        parsed_purchases: list[ParsedPurchase],
        dry_run: bool = False,
        required_status: str = "Прием предложений",
    ) -> ImportResult:
        result = ImportResult(source=source, found_count=len(parsed_purchases))
        import_logger.info(
            "Import started | source=%s status=%s dry_run=%s found=%s",
            source,
            required_status,
            dry_run,
            len(parsed_purchases),
        )

        for parsed_purchase in parsed_purchases:
            try:
                decision = filter_purchase(parsed_purchase, required_status=required_status)
                if not decision.include:
                    result.filtered_count += 1
                    continue

                existing_purchase = self.session.scalar(
                    select(Purchase.id).where(
                        Purchase.source == parsed_purchase.source,
                        Purchase.external_id == parsed_purchase.external_id,
                    )
                )

                if decision.risk_flags:
                    parsed_purchase.risk_flags = sorted(set(parsed_purchase.risk_flags + decision.risk_flags))

                purchase, is_created = self.upsert_purchase(parsed_purchase)
                self.session.flush()
                _items, item_created, item_updated = self.upsert_purchase_items(purchase, parsed_purchase.items)

                if existing_purchase is None and is_created:
                    result.created_count += 1
                else:
                    result.updated_count += 1

                # Item-level stats are recorded in logs; purchase-level counts are kept in result.
                import_logger.info(
                    "Purchase imported | source=%s external_id=%s created=%s items_created=%s items_updated=%s",
                    source,
                    parsed_purchase.external_id,
                    is_created,
                    item_created,
                    item_updated,
                )
            except Exception as exc:  # noqa: BLE001
                result.error_count += 1
                error_message = f"{parsed_purchase.source}:{parsed_purchase.external_id}: {exc}"
                result.errors.append(error_message)
                import_logger.exception("Purchase import error | %s", error_message)

        if dry_run:
            self.session.rollback()
        else:
            self.session.commit()

        self._persist_import_job(result=result, required_status=required_status, dry_run=dry_run)
        import_logger.info(
            "Import finished | source=%s found=%s filtered=%s created=%s updated=%s skipped=%s errors=%s",
            result.source,
            result.found_count,
            result.filtered_count,
            result.created_count,
            result.updated_count,
            result.skipped_count,
            result.error_count,
        )
        return result

    def _persist_import_job(self, result: ImportResult, required_status: str, dry_run: bool) -> None:
        self.session.add(
            ImportJob(
                source=result.source,
                status="completed" if result.error_count == 0 else "completed_with_errors",
                request_status=required_status,
                dry_run=dry_run,
                found_count=result.found_count,
                filtered_count=result.filtered_count,
                created_count=result.created_count,
                updated_count=result.updated_count,
                skipped_count=result.skipped_count,
                error_count=result.error_count,
                details={"errors": result.errors[:100]},
            )
        )
        if dry_run:
            self.session.rollback()
        else:
            self.session.commit()


def build_position_hash(item: ParsedPurchaseItem) -> str:
    if item.position_external_id:
        return hashlib.sha256(f"ext:{item.position_external_id}".encode("utf-8")).hexdigest()

    payload = "|".join(
        [
            item.name.strip().lower(),
            str(item.quantity),
            str(item.max_total_price) if item.max_total_price is not None else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _quantize_money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _safe_title(parsed_purchase: ParsedPurchase) -> str:
    if parsed_purchase.title and parsed_purchase.title.strip():
        return parsed_purchase.title.strip()

    if parsed_purchase.raw_payload:
        for key in ("title", "name", "subject", "purchaseName"):
            value = parsed_purchase.raw_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return f"{parsed_purchase.source}:{parsed_purchase.external_id}"


def _extract_region_code(region: str | None) -> str | None:
    if not region:
        return None

    lowered = region.lower()
    if "мос" in lowered or "москв" in lowered:
        if "обл" in lowered:
            return "50"
        return "77"

    return None
