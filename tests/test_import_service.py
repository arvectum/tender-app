from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.connectors.base import ParsedPurchase, ParsedPurchaseItem
from app.db import Base
from app.models import Purchase, PurchaseItem
from app.services.import_service import ImportService, build_position_hash


def _make_purchase(title: str = "Поставка бумаги", quantity: Decimal = Decimal("10")) -> ParsedPurchase:
    return ParsedPurchase(
        source="mos_portal",
        external_id="A-100",
        title=title,
        url="https://zakupki.mos.ru/auction/A-100",
        status="Прием предложений",
        region="Москва",
        customer_name="Заказчик",
        max_total_price=Decimal("10000"),
        items=[
            ParsedPurchaseItem(
                position_external_id=None,
                name="Бумага A4",
                quantity=quantity,
                max_total_price=Decimal("5000"),
            )
        ],
    )


def test_upsert_does_not_create_duplicates_and_updates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = ImportService(session=session, save_raw=True)
        result1 = service.import_purchases(source="mos_portal", parsed_purchases=[_make_purchase()], dry_run=False)
        assert result1.created_count == 1

        result2 = service.import_purchases(
            source="mos_portal",
            parsed_purchases=[_make_purchase(title="Поставка бумаги (обновлено)", quantity=Decimal("12"))],
            dry_run=False,
        )
        assert result2.updated_count == 1

        purchases = session.scalars(select(Purchase)).all()
        items = session.scalars(select(PurchaseItem)).all()

        assert len(purchases) == 1
        assert len(items) == 1
        assert purchases[0].title == "Поставка бумаги (обновлено)"
        assert float(items[0].quantity) == 12.0


def test_position_hash_is_stable_without_external_id() -> None:
    item = ParsedPurchaseItem(
        position_external_id=None,
        name="Картридж",
        quantity=Decimal("5"),
        max_total_price=Decimal("2500"),
    )

    first = build_position_hash(item)
    second = build_position_hash(item)

    assert first == second
