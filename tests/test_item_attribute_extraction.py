from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Purchase, PurchaseItem
from app.services.item_attribute_service import ItemAttributeService


def test_extract_hp_article_from_item_text() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(source="fixture", external_id="P-1", title="t")
        item = PurchaseItem(
            position_hash="h1",
            item_name="Поставка картриджа HP 305A CE410A черный оригинальный, 2 шт.",
            quantity=Decimal("2"),
        )
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.refresh(item)

        row = ItemAttributeService(session).refresh_attributes(item.id)
        assert row.brand == "HP"
        assert row.article == "CE410A"
