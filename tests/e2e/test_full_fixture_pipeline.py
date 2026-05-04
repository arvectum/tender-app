from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import PurchaseDecisionScore
from app.services.calculation_service import calculate_all_purchases
from app.services.decision_service import DecisionService
from app.services.excel_export_service import export_to_excel
from app.services.fixture_loader import load_fixtures
from app.services.item_attribute_service import ItemAttributeService
from app.services.price_search_service import PriceSearchService


def test_full_fixture_pipeline(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_fixtures(
            session,
            purchases_path=Path("fixtures/sample_purchases.json"),
            offers_path=Path("fixtures/sample_market_offers.json"),
            reset=True,
        )
        ItemAttributeService(session).extract_for_all_missing()
        PriceSearchService(session).search_prices(mode="stub", limit=20, purchase_id=None, item_id=None)
        calculate_all_purchases(session)
        DecisionService(session).evaluate_all()
        output = export_to_excel(session, output_path=tmp_path / "pipeline.xlsx")
        assert output.exists()
        assert session.scalar(select(PurchaseDecisionScore.id).limit(1)) is not None
