from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import MarketOffer, Purchase, PurchaseItem, PurchaseWatchlist
from app.services.calculation_service import calculate_purchase
from app.services.decision_service import DecisionService


def _seed_purchase(session: Session, external_id: str, max_total: str = "100000") -> tuple[Purchase, PurchaseItem]:
    purchase = Purchase(
        source="mos_portal",
        external_id=external_id,
        title="Поставка товара",
        status="Прием предложений",
        region="Москва",
        max_total_price=Decimal(max_total),
        submission_deadline=utc_now() + timedelta(hours=48),
        parsed_at=utc_now(),
    )
    item = PurchaseItem(
        position_hash=f"hash-{external_id}",
        item_name="Товар X",
        quantity=Decimal("2"),
        unit="шт",
    )
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)
    return purchase, item


def test_evaluate_purchase_creates_decision_score() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, item = _seed_purchase(session, "D-1")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                item_name=item.item_name,
                offer_title=item.item_name,
                seller_name="ООО Ромашка",
                supplier_name="ООО Ромашка",
                supplier_status="trusted",
                unit_price=Decimal("20000"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                relevance_score=Decimal("0.95"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()
        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)
        assert score.purchase_id == purchase.id
        assert score.decision is not None
        assert score.score_total is not None


def test_item_without_prices_gets_needs_manual_review() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, _ = _seed_purchase(session, "D-2")
        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)
        assert score.decision == "needs_manual_review"


def test_blocked_supplier_leads_reject_or_high_risk() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, item = _seed_purchase(session, "D-3")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                item_name=item.item_name,
                offer_title=item.item_name,
                seller_name="ИП Плохой",
                supplier_name="ИП Плохой",
                supplier_status="blocked",
                unit_price=Decimal("1000"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                relevance_score=Decimal("0.95"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()
        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)
        assert score.decision == "reject" or score.risk_level in {"high", "critical"}


def test_ignored_purchase_not_in_top_opportunities() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, item = _seed_purchase(session, "D-4")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                item_name=item.item_name,
                offer_title=item.item_name,
                seller_name="ООО Ромашка",
                supplier_name="ООО Ромашка",
                supplier_status="trusted",
                unit_price=Decimal("1000"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                relevance_score=Decimal("0.99"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()
        calculate_purchase(session, purchase.id)
        service = DecisionService(session)
        service.evaluate_purchase(purchase.id)

        session.add(PurchaseWatchlist(purchase_id=purchase.id, status="ignored", note="skip"))
        session.commit()

        ids = [row.purchase_id for row in service.get_top_opportunities(limit=20)]
        assert purchase.id not in ids
