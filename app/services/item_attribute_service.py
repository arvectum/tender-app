from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.catalog import extract_item_attributes
from app.models import ItemAttributes, Purchase, PurchaseItem


class ItemAttributeService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def extract_for_item(self, item: PurchaseItem) -> ItemAttributes:
        extracted = extract_item_attributes(item)
        row = self.session.scalar(select(ItemAttributes).where(ItemAttributes.purchase_item_id == item.id))
        if row is None:
            row = ItemAttributes(purchase_item_id=item.id)
            self.session.add(row)

        row.normalized_name = extracted.normalized_name
        row.category = extracted.category
        row.brand = extracted.brand
        row.model = extracted.model
        row.article = extracted.article
        row.color = extracted.color
        row.size = extracted.size
        row.volume = extracted.volume
        row.weight = extracted.weight
        row.material = extracted.material
        row.package_quantity = extracted.package_quantity
        row.original_required = extracted.original_required
        row.compatible_allowed = extracted.compatible_allowed
        row.keywords_json = extracted.keywords
        row.stopwords_removed_json = extracted.stopwords_removed
        row.numbers_json = extracted.numbers
        row.units_json = extracted.units
        row.confidence_score = Decimal(str(extracted.confidence_score))
        row.risk_flags_json = extracted.risk_flags
        self.session.flush()
        return row

    def extract_for_purchase(self, purchase_id: int) -> int:
        purchase = self.session.scalar(
            select(Purchase).where(Purchase.id == purchase_id).options(selectinload(Purchase.items))
        )
        if purchase is None:
            raise ValueError(f"Purchase id={purchase_id} not found")

        count = 0
        for item in purchase.items:
            self.extract_for_item(item)
            count += 1
        self.session.commit()
        return count

    def extract_for_all_missing(self) -> int:
        stmt = (
            select(PurchaseItem)
            .outerjoin(ItemAttributes, ItemAttributes.purchase_item_id == PurchaseItem.id)
            .where(ItemAttributes.id.is_(None))
        )
        items = self.session.scalars(stmt).all()
        for item in items:
            self.extract_for_item(item)
        self.session.commit()
        return len(items)

    def refresh_attributes(self, item_id: int) -> ItemAttributes:
        item = self.session.scalar(select(PurchaseItem).where(PurchaseItem.id == item_id))
        if item is None:
            raise ValueError(f"PurchaseItem id={item_id} not found")
        row = self.extract_for_item(item)
        self.session.commit()
        self.session.refresh(row)
        return row
