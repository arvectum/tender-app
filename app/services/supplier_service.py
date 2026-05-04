from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Supplier


_WS_RE = re.compile(r"\s+")


def normalize_supplier_name(name: str) -> str:
    return _WS_RE.sub(" ", (name or "").strip().lower())


class SupplierService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_supplier(self, name: str, status: str = "unknown", rating: Decimal | None = None, comment: str | None = None) -> Supplier:
        normalized = normalize_supplier_name(name)
        row = self.session.scalar(select(Supplier).where(Supplier.normalized_name == normalized))
        if row is None:
            row = Supplier(name=name.strip(), normalized_name=normalized, status=status, rating=rating, comment=comment)
            self.session.add(row)
        else:
            row.name = name.strip()
            row.status = status
            row.rating = rating
            row.comment = comment
        self.session.commit()
        self.session.refresh(row)
        return row

    def update_supplier(self, name: str, status: str, comment: str | None = None) -> Supplier:
        normalized = normalize_supplier_name(name)
        row = self.session.scalar(select(Supplier).where(Supplier.normalized_name == normalized))
        if row is None:
            raise ValueError(f"Supplier '{name}' not found")
        row.status = status
        if comment is not None:
            row.comment = comment
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_suppliers(self) -> list[Supplier]:
        return self.session.scalars(select(Supplier).order_by(Supplier.name.asc())).all()

    def resolve(self, seller_name: str | None) -> Supplier | None:
        if not seller_name:
            return None
        normalized = normalize_supplier_name(seller_name)
        return self.session.scalar(select(Supplier).where(Supplier.normalized_name == normalized))
