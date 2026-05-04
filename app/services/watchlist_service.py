from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PurchaseWatchlist


class WatchlistService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, purchase_id: int, note: str | None = None, status: str = "watch") -> PurchaseWatchlist:
        row = self.session.scalar(select(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id == purchase_id))
        if row is None:
            row = PurchaseWatchlist(purchase_id=purchase_id, status=status, note=note)
            self.session.add(row)
        else:
            row.status = status
            if note is not None:
                row.note = note
        self.session.commit()
        self.session.refresh(row)
        return row

    def update(self, purchase_id: int, status: str, note: str | None = None) -> PurchaseWatchlist:
        row = self.session.scalar(select(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id == purchase_id))
        if row is None:
            row = PurchaseWatchlist(purchase_id=purchase_id, status=status, note=note)
            self.session.add(row)
        else:
            row.status = status
            if note is not None:
                row.note = note
        self.session.commit()
        self.session.refresh(row)
        return row

    def remove(self, purchase_id: int) -> bool:
        row = self.session.scalar(select(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id == purchase_id))
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def list(self) -> list[PurchaseWatchlist]:
        return self.session.scalars(select(PurchaseWatchlist).order_by(PurchaseWatchlist.updated_at.desc())).all()
