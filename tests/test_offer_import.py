
from app.utils.time import utc_now
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import MarketOffer, Purchase, PurchaseItem
from app.price_search.manual_import.importer import import_offers_from_file


def _seed_purchase_item(session: Session) -> tuple[Purchase, PurchaseItem]:
    purchase = Purchase(
        source="mos_portal",
        external_id="MOS-1",
        title="Поставка картриджей",
        status="Прием предложений",
        region="Москва",
        parsed_at=utc_now(),
    )
    item = PurchaseItem(
        position_external_id="POS-1",
        position_hash="hash-1",
        item_name="Картридж HP 305A CE410A",
        quantity=Decimal("4"),
        unit="шт",
    )
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)
    return purchase, item


def test_import_offers_reads_xlsx(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    xlsx_file = tmp_path / "offers.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append([
        "purchase_external_id",
        "position_external_id",
        "item_name",
        "offer_title",
        "offer_url",
        "seller_name",
        "region",
        "unit_price",
        "available_quantity",
        "delivery_price",
        "delivery_days",
        "is_relevant",
        "relevance_score",
        "comment",
    ])
    ws.append([
        "MOS-1",
        "POS-1",
        "Картридж HP 305A CE410A",
        "Картридж HP 305A CE410A оригинал",
        "https://example.com/1",
        "Seller",
        "Москва",
        3500,
        10,
        300,
        2,
        True,
        0.95,
        "ok",
    ])
    wb.save(xlsx_file)

    with Session(engine) as session:
        _seed_purchase_item(session)
        result = import_offers_from_file(session, xlsx_file)

        assert result.imported_count == 1
        offers = session.scalars(select(MarketOffer)).all()
        assert len(offers) == 1
        assert offers[0].offer_title is not None


def test_import_offers_reads_csv(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    csv_file = tmp_path / "offers.csv"
    csv_file.write_text(
        "purchase_external_id,position_external_id,item_name,offer_title,offer_url,seller_name,region,unit_price,available_quantity,delivery_price,delivery_days,is_relevant,relevance_score,comment\n"
        "MOS-1,POS-1,Картридж HP 305A CE410A,Картридж HP 305A CE410A оригинал,https://example.com/1,Seller,Москва,3500,10,300,2,true,0.95,ok\n",
        encoding="utf-8",
    )

    with Session(engine) as session:
        _seed_purchase_item(session)
        result = import_offers_from_file(session, csv_file)

        assert result.imported_count == 1
        offers = session.scalars(select(MarketOffer)).all()
        assert len(offers) == 1
        assert offers[0].supplier_name == "Seller"
