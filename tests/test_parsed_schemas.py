from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.connectors.base import ParsedPurchase, ParsedPurchaseItem


def test_parsed_purchase_validation_success() -> None:
    purchase = ParsedPurchase(
        source="mos_portal",
        external_id="123",
        title="Поставка бумаги",
        status="Прием предложений",
        region="Москва",
        items=[
            ParsedPurchaseItem(
                name="Бумага A4",
                quantity=Decimal("10"),
            )
        ],
    )

    assert purchase.external_id == "123"
    assert purchase.items[0].name == "Бумага A4"


def test_parsed_purchase_item_requires_name_and_quantity() -> None:
    with pytest.raises(ValidationError):
        ParsedPurchaseItem(name="", quantity=Decimal("1"))

    with pytest.raises(ValidationError):
        ParsedPurchaseItem(name="Товар", quantity=Decimal("0"))
