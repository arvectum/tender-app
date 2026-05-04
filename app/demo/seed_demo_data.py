from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    CalculationOfferUsage,
    ItemCostCalculation,
    JobRun,
    MarketOffer,
    Purchase,
    PurchaseCalculation,
    PurchaseDecisionScore,
    PurchaseItem,
    PurchaseWatchlist,
    Supplier,
)
from app.scoring.strategy import create_default_strategies
from app.services.calculation_service import calculate_purchase
from app.services.decision_service import DecisionService
from app.services.user_service import UserService
from app.utils.logging import get_file_logger
from app.utils.time import utc_now


DEMO_DIR = Path(__file__).resolve().parent / "demo_fixtures"
logger = get_file_logger("demo.seed", "demo.log")


def seed_demo_data(session: Session) -> dict[str, int]:
    settings = get_settings()
    if settings.app_mode not in {"demo", "development"} and not settings.demo_data_enabled:
        raise ValueError("Demo data seeding is allowed only in demo/development mode")

    create_default_strategies(session)
    _seed_suppliers(session)
    purchases = _seed_purchases_and_items(session)
    _seed_offers(session, purchases)
    _reset_demo_calculations(session, purchases)

    for purchase in purchases:
        calculate_purchase(session, purchase.id)
    decision_service = DecisionService(session)
    decision_service.evaluate_all()

    for idx, purchase in enumerate(purchases[:5]):
        status = ["watch", "preparing", "submitted", "ignored", "rejected"][idx]
        session.merge(PurchaseWatchlist(purchase_id=purchase.id, status=status, note="demo watchlist"))
    session.add(
        JobRun(
            job_type="parse",
            source="mos_portal",
            status="failed",
            error_message="demo: parser timeout sample",
            created_at=utc_now(),
        )
    )
    session.commit()

    _seed_users(session)
    demo_offer_count = len(session.scalars(select(MarketOffer).where(MarketOffer.source == "demo")).all())
    return {
        "purchases": len(purchases),
        "offers": demo_offer_count,
    }


def reset_demo_data(session: Session, force_demo: bool = False) -> None:
    settings = get_settings()
    if settings.app_mode != "demo" and not force_demo:
        raise ValueError("reset-demo is allowed only in APP_MODE=demo (or with --force-demo)")

    demo_purchase_ids = session.scalars(select(Purchase.id).where(Purchase.source == "demo")).all()
    if demo_purchase_ids:
        session.execute(delete(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id.in_(demo_purchase_ids)))
        session.execute(delete(MarketOffer).where(MarketOffer.purchase_id.in_(demo_purchase_ids)))
        session.execute(delete(PurchaseItem).where(PurchaseItem.purchase_id.in_(demo_purchase_ids)))
        session.execute(delete(Purchase).where(Purchase.id.in_(demo_purchase_ids)))
    session.execute(delete(Supplier).where(Supplier.comment == "demo"))
    session.execute(delete(JobRun).where(JobRun.error_message.like("demo:%")))
    session.commit()
    seed_demo_data(session)


def _seed_suppliers(session: Session) -> None:
    suppliers_payload = _load_json("suppliers.json")
    for row in suppliers_payload:
        existing = session.scalar(select(Supplier).where(Supplier.normalized_name == row["normalized_name"]))
        if existing is None:
            session.add(
                Supplier(
                    name=row["name"],
                    normalized_name=row["normalized_name"],
                    status=row["status"],
                    rating=safe_decimal(row.get("rating"), default=None, field_name="supplier.rating"),
                    comment="demo",
                )
            )
    session.commit()


def _seed_purchases_and_items(session: Session) -> list[Purchase]:
    purchases_payload = _load_json("purchases.json")
    result: list[Purchase] = []
    for idx, row in enumerate(purchases_payload):
        external_id = row["external_id"]
        existing = session.scalar(select(Purchase).where(Purchase.source == "demo", Purchase.external_id == external_id))
        if existing is not None:
            result.append(existing)
            continue
        purchase = Purchase(
            source="demo",
            external_id=external_id,
            title=row["title"],
            status="Прием предложений",
            region=row.get("region", "Москва"),
            max_total_price=safe_decimal(row.get("max_total_price"), default=Decimal("100000"), field_name="purchase.max_total_price"),
            submission_deadline=utc_now() + timedelta(hours=12 + idx * 3),
            parsed_at=utc_now(),
            risk_flags=[],
        )
        for item_idx, item_row in enumerate(row.get("items", [])):
            purchase.items.append(
                PurchaseItem(
                    position_external_id=f"{external_id}-POS-{item_idx+1}",
                    position_hash=f"demo-{external_id}-{item_idx+1}",
                    item_name=item_row["name"],
                    description=item_row.get("description"),
                    quantity=safe_decimal(item_row.get("quantity"), default=Decimal("1"), field_name="item.quantity"),
                    unit=item_row.get("unit", "шт"),
                    max_total_price=safe_decimal(
                        item_row.get("max_total_price"),
                        default=Decimal("10000"),
                        field_name="item.max_total_price",
                    ),
                )
            )
        session.add(purchase)
        session.flush()
        result.append(purchase)
    session.commit()
    return result


def _seed_offers(session: Session, purchases: list[Purchase]) -> None:
    offers_payload = _load_json("offers.json")
    purchase_by_external = {purchase.external_id: purchase for purchase in purchases}

    purchase_ids = [purchase.id for purchase in purchases]
    if purchase_ids:
        session.execute(
            delete(MarketOffer).where(
                MarketOffer.source == "demo",
                MarketOffer.purchase_id.in_(purchase_ids),
            )
        )
        session.commit()

    for row in offers_payload:
        purchase = purchase_by_external.get(row["purchase_external_id"])
        if purchase is None or not purchase.items:
            continue
        item = purchase.items[0]
        session.add(
            MarketOffer(
                provider="demo_seed",
                source="demo",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title=row["offer_title"],
                seller_name=row["seller_name"],
                supplier_name=row["seller_name"],
                supplier_status=row.get("supplier_status", "unknown"),
                region=row.get("region", "Москва"),
                unit_price=safe_decimal(row.get("unit_price"), default=Decimal("100"), field_name="offer.unit_price"),
                available_quantity=safe_int(row.get("available_quantity"), default=10, field_name="offer.available_quantity"),
                delivery_price=safe_decimal(row.get("delivery_price"), default=Decimal("0"), field_name="offer.delivery_price"),
                delivery_unknown=bool(row.get("delivery_unknown", False)),
                relevance_score=safe_decimal(
                    row.get("relevance_score"),
                    default=Decimal("0.95"),
                    field_name="offer.relevance_score",
                ),
                is_relevant=bool(row.get("is_relevant", True)),
                risk_flags=row.get("risk_flags", []),
            )
        )
    session.commit()


def _seed_users(session: Session) -> None:
    users_payload = _load_json("users.json")
    service = UserService(session)
    service.ensure_default_roles()
    existing_usernames = {user.username for user in service.list_users()}
    for row in users_payload:
        if row["username"] in existing_usernames:
            continue
        service.create_user(
            username=row["username"],
            email=row["email"],
            role=row["role"],
            password=row.get("password", "ChangeMe123!"),
        )


def _reset_demo_calculations(session: Session, purchases: list[Purchase]) -> None:
    purchase_ids = [row.id for row in purchases]
    if not purchase_ids:
        return

    calc_ids = session.scalars(
        select(ItemCostCalculation.id).where(ItemCostCalculation.purchase_id.in_(purchase_ids))
    ).all()
    if calc_ids:
        session.execute(delete(CalculationOfferUsage).where(CalculationOfferUsage.item_cost_calculation_id.in_(calc_ids)))
    session.execute(delete(ItemCostCalculation).where(ItemCostCalculation.purchase_id.in_(purchase_ids)))
    session.execute(delete(PurchaseCalculation).where(PurchaseCalculation.purchase_id.in_(purchase_ids)))
    session.execute(delete(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id.in_(purchase_ids)))
    session.execute(delete(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id.in_(purchase_ids)))
    session.commit()


def _load_json(filename: str) -> list[dict]:
    path = DEMO_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def safe_decimal(value, default: Decimal | None = None, field_name: str = "") -> Decimal | None:
    if value is None:
        return default
    text = _normalize_numeric_text(value)
    if text == "":
        return default
    try:
        return Decimal(text)
    except Exception:
        logger.warning("seed-demo numeric parse failed | field=%s value=%r default=%r", field_name, value, default)
        return default


def safe_int(value, default: int | None = None, field_name: str = "") -> int | None:
    if value is None:
        return default
    text = _normalize_numeric_text(value)
    if text == "":
        return default
    try:
        return int(Decimal(text))
    except Exception:
        logger.warning("seed-demo numeric parse failed | field=%s value=%r default=%r", field_name, value, default)
        return default


def safe_float(value, default: float | None = None, field_name: str = "") -> float | None:
    if value is None:
        return default
    text = _normalize_numeric_text(value)
    if text == "":
        return default
    try:
        return float(text)
    except Exception:
        logger.warning("seed-demo numeric parse failed | field=%s value=%r default=%r", field_name, value, default)
        return default


def _normalize_numeric_text(value) -> str:
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("\u00a0", "")
    text = re.sub(r"\s+", "", text)
    if "," in text and "." in text:
        text = text.replace(".", "")
    text = text.replace(",", ".")
    return text
