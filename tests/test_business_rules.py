from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import BusinessRule
from app.services.business_rules_service import BusinessRulesService


def test_business_rules_db_override_env_default() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = BusinessRulesService(session)
        session.add(BusinessRule(key="MIN_OFFER_RELEVANCE_SCORE", value="0.91"))
        session.commit()
        value = service.get_typed("MIN_OFFER_RELEVANCE_SCORE", 0.78, float)
        assert value == 0.91
