from __future__ import annotations

from decimal import Decimal

from sqlalchemy import update, select
from sqlalchemy.orm import Session

from app.models import ParticipationStrategy


def create_default_strategies(session: Session) -> int:
    defaults = [
        {
            "name": "conservative",
            "description": "Высокие требования к марже и минимальным рискам.",
            "is_active": False,
            "min_margin_percent": Decimal("30"),
            "min_profit_amount": Decimal("20000"),
            "max_risk_level": "medium",
            "allow_unknown_delivery": False,
            "allow_unknown_supplier": False,
            "allow_manual_review_items": False,
        },
        {
            "name": "balanced",
            "description": "Баланс доходности и приемлемого риска.",
            "is_active": True,
            "min_margin_percent": Decimal("20"),
            "min_profit_amount": Decimal("10000"),
            "max_risk_level": "medium",
            "allow_unknown_delivery": True,
            "allow_unknown_supplier": True,
            "allow_manual_review_items": True,
        },
        {
            "name": "aggressive",
            "description": "Более рискованная стратегия с низким порогом входа.",
            "is_active": False,
            "min_margin_percent": Decimal("15"),
            "min_profit_amount": Decimal("5000"),
            "max_risk_level": "high",
            "allow_unknown_delivery": True,
            "allow_unknown_supplier": True,
            "allow_manual_review_items": True,
        },
    ]
    created = 0
    for payload in defaults:
        row = session.scalar(select(ParticipationStrategy).where(ParticipationStrategy.name == payload["name"]))
        if row is None:
            session.add(ParticipationStrategy(**payload))
            created += 1
    session.commit()
    return created


def list_strategies(session: Session) -> list[ParticipationStrategy]:
    return session.scalars(select(ParticipationStrategy).order_by(ParticipationStrategy.name.asc())).all()


def get_active_strategy(session: Session) -> ParticipationStrategy | None:
    row = session.scalar(select(ParticipationStrategy).where(ParticipationStrategy.is_active.is_(True)))
    if row is not None:
        return row
    create_default_strategies(session)
    return session.scalar(select(ParticipationStrategy).where(ParticipationStrategy.name == "balanced"))


def activate_strategy(session: Session, name: str) -> ParticipationStrategy:
    strategy = session.scalar(select(ParticipationStrategy).where(ParticipationStrategy.name == name))
    if strategy is None:
        raise ValueError(f"Strategy '{name}' not found")
    session.execute(update(ParticipationStrategy).values(is_active=False))
    strategy.is_active = True
    session.commit()
    session.refresh(strategy)
    return strategy
