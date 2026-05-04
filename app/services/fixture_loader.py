from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import ImportJob, MarketOffer, Purchase, PurchaseItem
from app.utils.time import utc_now


def load_fixtures(session: Session, purchases_path: Path, offers_path: Path, reset: bool = True) -> None:
    purchases_payload = json.loads(purchases_path.read_text(encoding="utf-8"))
    offers_payload = json.loads(offers_path.read_text(encoding="utf-8"))

    if reset:
        session.execute(delete(PurchaseItem))
        session.execute(delete(Purchase))
        session.execute(delete(MarketOffer))
        session.commit()

    for purchase_data in purchases_payload:
        deadline_raw = purchase_data.get("submission_deadline")
        deadline = datetime.fromisoformat(deadline_raw) if deadline_raw else None

        purchase = Purchase(
            source="fixture",
            external_id=purchase_data["external_id"],
            title=purchase_data["title"],
            status="Прием предложений",
            region=str(purchase_data.get("region_code", "77")),
            region_code=str(purchase_data.get("region_code", "77")),
            customer_name=purchase_data.get("customer_name") or "Fixture customer",
            max_total_price=Decimal(str(purchase_data["max_total_price"])),
            submission_deadline=deadline,
            parsed_at=utc_now(),
            created_at_source=deadline,
            raw_payload=purchase_data,
        )

        for item_data in purchase_data.get("items", []):
            quantity = Decimal(str(item_data.get("quantity", 1)))
            position_hash = _fixture_item_hash(
                name=item_data["item_name"],
                quantity=quantity,
                max_total_price=Decimal(str(item_data.get("max_total_price", 0))),
            )
            purchase.items.append(
                PurchaseItem(
                    position_external_id=item_data.get("position_external_id"),
                    position_hash=position_hash,
                    item_name=item_data["item_name"],
                    description=item_data.get("description"),
                    quantity=quantity,
                    unit=item_data.get("unit", "pcs"),
                    max_unit_price=Decimal(str(item_data.get("max_unit_price"))) if item_data.get("max_unit_price") is not None else None,
                    max_total_price=Decimal(str(item_data.get("max_total_price"))) if item_data.get("max_total_price") is not None else None,
                    okpd2=item_data.get("okpd2"),
                    delivery_region=item_data.get("delivery_region"),
                    delivery_address=item_data.get("delivery_address"),
                    delivery_terms=item_data.get("delivery_terms"),
                    raw_payload=item_data,
                )
            )

        session.add(purchase)

    for offer_data in offers_payload:
        delivery_price_raw = offer_data.get("delivery_price")
        session.add(
            MarketOffer(
                provider=offer_data.get("provider", "stub"),
                item_name=offer_data["item_name"],
                offer_title=offer_data.get("offer_title") or offer_data["item_name"],
                offer_url=offer_data.get("offer_url"),
                seller_name=offer_data.get("seller_name") or offer_data.get("supplier_name"),
                supplier_name=offer_data["supplier_name"],
                unit_price=Decimal(str(offer_data["unit_price"])),
                available_quantity=int(offer_data["available_quantity"]),
                delivery_price=Decimal(str(delivery_price_raw)) if delivery_price_raw is not None else None,
                delivery_days=offer_data.get("delivery_days"),
                effective_unit_price=Decimal(str(offer_data["unit_price"])),
                relevance_score=Decimal(str(offer_data.get("relevance_score", 1.0))),
                risk_flags=list(offer_data.get("risk_flags", [])),
                comment=offer_data.get("comment"),
                raw_payload=offer_data,
                region_code=str(offer_data.get("region_code")) if offer_data.get("region_code") else None,
                region=offer_data.get("region"),
                source=offer_data.get("source", "fixture"),
                is_relevant=bool(offer_data.get("is_relevant", True)),
            )
        )

    session.add(
        ImportJob(
            source="fixture",
            status="completed",
            request_status="Прием предложений",
            dry_run=False,
            found_count=len(purchases_payload),
            filtered_count=0,
            created_count=len(purchases_payload),
            updated_count=0,
            skipped_count=0,
            error_count=0,
            details={"fixture": True},
        )
    )
    session.commit()


def _fixture_item_hash(name: str, quantity: Decimal, max_total_price: Decimal) -> str:
    payload = f"{name.strip().lower()}|{quantity}|{max_total_price}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
