from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import MarketOffer, Purchase, PurchaseItem
from app.scoring.strategy import activate_strategy, create_default_strategies
from app.services.calculation_service import calculate_purchase
from app.services.decision_service import DecisionService


def _seed_purchase_with_unknown_delivery_offer(session: Session, external_id: str) -> Purchase:
    purchase = Purchase(
        source="mos_portal",
        external_id=external_id,
        title="Поставка картриджа HP CE410A",
        status="Прием предложений",
        region="Москва",
        max_total_price=Decimal("50000"),
        submission_deadline=utc_now() + timedelta(hours=36),
        parsed_at=utc_now(),
    )
    item = PurchaseItem(
        position_hash=f"hash-{external_id}",
        item_name="Картридж HP CE410A оригинальный",
        quantity=Decimal("1"),
        unit="шт",
    )
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)

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
            unit_price=Decimal("10000"),
            available_quantity=5,
            delivery_price=None,
            delivery_unknown=True,
            relevance_score=Decimal("0.95"),
            is_relevant=True,
            risk_flags=["delivery_unknown"],
        )
    )
    session.commit()
    return purchase


def test_conservative_strategy_rejects_unknown_delivery() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        create_default_strategies(session)
        activate_strategy(session, "conservative")
        purchase = _seed_purchase_with_unknown_delivery_offer(session, "ST-1")
        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)
        assert score.decision == "needs_manual_review"
        assert "доставк" in (score.decision_reason or "").lower()


def test_balanced_strategy_allows_unknown_delivery() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        create_default_strategies(session)
        activate_strategy(session, "balanced")
        purchase = _seed_purchase_with_unknown_delivery_offer(session, "ST-2")
        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)
        assert score.decision in {"strong_recommend", "recommend", "watch"}
