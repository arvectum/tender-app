from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.utils.time import utc_now


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_purchase_source_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), default="fixture", index=True)
    external_id: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    region_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submission_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    commission_fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    security_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_total_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deadline_status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    data_quality: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    data_quality_warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    source_history_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    items: Mapped[list[PurchaseItem]] = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    calculation: Mapped[PurchaseCalculation | None] = relationship(
        "PurchaseCalculation", back_populates="purchase", uselist=False, cascade="all, delete-orphan"
    )
    item_calculations: Mapped[list[ItemCostCalculation]] = relationship(
        "ItemCostCalculation", back_populates="purchase", cascade="all, delete-orphan"
    )
    decision_score: Mapped[PurchaseDecisionScore | None] = relationship(
        "PurchaseDecisionScore",
        back_populates="purchase",
        uselist=False,
        cascade="all, delete-orphan",
    )
    watchlist_entry: Mapped[PurchaseWatchlist | None] = relationship(
        "PurchaseWatchlist",
        back_populates="purchase",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    __table_args__ = (UniqueConstraint("purchase_id", "position_hash", name="uq_purchase_item_position_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    position_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    position_hash: Mapped[str] = mapped_column(String(64), index=True)
    item_name: Mapped[str] = mapped_column(String(500), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    okpd2: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"))
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_total_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    delivery_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="items")
    calculations: Mapped[list[ItemCostCalculation]] = relationship("ItemCostCalculation", back_populates="purchase_item")
    market_offers: Mapped[list[MarketOffer]] = relationship("MarketOffer", back_populates="purchase_item")
    attributes: Mapped[ItemAttributes | None] = relationship(
        "ItemAttributes",
        back_populates="purchase_item",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MarketOffer(Base):
    __tablename__ = "market_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), default="stub", index=True)
    source: Mapped[str] = mapped_column(String(100), default="fixture", index=True)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchase_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    position_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    item_name: Mapped[str] = mapped_column(String(500), index=True)
    offer_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    offer_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(255), default="unknown")
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    available_quantity: Mapped[int] = mapped_column(Integer)
    delivery_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    is_relevant: Mapped[bool] = mapped_column(default=True, index=True)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    match_reasons_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    match_risk_flags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    matched_fields_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mismatched_fields_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    hard_reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delivery_price_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pickup_available: Mapped[bool | None] = mapped_column(nullable=True, default=None)
    delivery_unknown: Mapped[bool] = mapped_column(default=False)
    min_order_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    supplier_status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    manual_override_relevance: Mapped[bool | None] = mapped_column(nullable=True)
    manual_override_exclude: Mapped[bool] = mapped_column(default=False)
    manual_override_include: Mapped[bool] = mapped_column(default=False)
    manual_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_user_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    purchase_item: Mapped[PurchaseItem | None] = relationship("PurchaseItem", back_populates="market_offers")
    supplier: Mapped[Supplier | None] = relationship("Supplier", back_populates="offers")


class ItemCostCalculation(Base):
    __tablename__ = "item_cost_calculations"
    __table_args__ = (UniqueConstraint("purchase_id", "purchase_item_id", name="uq_item_calc_purchase_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    purchase_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_items.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(60), index=True)
    required_quantity: Mapped[int] = mapped_column(Integer)
    covered_quantity: Mapped[int] = mapped_column(Integer)
    estimated_item_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    unknown_delivery_used: Mapped[bool] = mapped_column(default=False)
    selected_offers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    calculation_details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="item_calculations")
    purchase_item: Mapped[PurchaseItem] = relationship("PurchaseItem", back_populates="calculations")
    offer_usages: Mapped[list[CalculationOfferUsage]] = relationship(
        "CalculationOfferUsage",
        back_populates="item_cost_calculation",
        cascade="all, delete-orphan",
    )


class CalculationOfferUsage(Base):
    __tablename__ = "calculation_offer_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_cost_calculation_id: Mapped[int] = mapped_column(
        ForeignKey("item_cost_calculations.id", ondelete="CASCADE"), index=True
    )
    market_offer_id: Mapped[int | None] = mapped_column(ForeignKey("market_offers.id", ondelete="SET NULL"), nullable=True, index=True)
    taken_quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    delivery_price_allocated: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)

    item_cost_calculation: Mapped[ItemCostCalculation] = relationship("ItemCostCalculation", back_populates="offer_usages")


class PurchaseCalculation(Base):
    __tablename__ = "purchase_calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), unique=True, index=True)
    max_total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    estimated_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    cash_required: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    recommendation_status: Mapped[str] = mapped_column(String(60), index=True)
    problematic_items_count: Mapped[int] = mapped_column(Integer, default=0)
    unknown_delivery_items_count: Mapped[int] = mapped_column(Integer, default=0)
    attractiveness_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    cost_before_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    cost_after_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    profit_after_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    margin_before_tax_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    margin_after_tax_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    explanation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="verified", index=True)
    financial_check_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    financial_check_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="calculation")


class PurchaseDecisionScore(Base):
    __tablename__ = "purchase_decision_scores"
    __table_args__ = (UniqueConstraint("purchase_id", name="uq_purchase_decision_scores_purchase"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), unique=True, index=True)
    score_total: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_margin: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_profit: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_deadline: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_data_quality: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_supplier_quality: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_competition: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_cash_efficiency: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    score_risk: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    risk_level: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    decision: Mapped[str] = mapped_column(String(60), default="needs_manual_review", index=True)
    decision_status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cash_roi_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    deadline_status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    competition_level: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    competition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="decision_score")


class ParticipationStrategy(Base):
    __tablename__ = "participation_strategies"
    __table_args__ = (UniqueConstraint("name", name="uq_participation_strategies_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    min_margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("20"))
    min_profit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("10000"))
    max_cash_required: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    allow_unknown_delivery: Mapped[bool] = mapped_column(default=True)
    allow_unknown_supplier: Mapped[bool] = mapped_column(default=True)
    allow_manual_review_items: Mapped[bool] = mapped_column(default=True)
    preferred_categories_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    blocked_categories_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preferred_regions_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)


class PurchaseWatchlist(Base):
    __tablename__ = "purchase_watchlist"
    __table_args__ = (UniqueConstraint("purchase_id", name="uq_purchase_watchlist_purchase"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="watch", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="watchlist_entry")


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(60), default="pending", index=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(60), default="completed", index=True)
    request_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dry_run: Mapped[bool] = mapped_column(default=False)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    filtered_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    params_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)


class JobLock(Base):
    __tablename__ = "job_locks"
    __table_args__ = (UniqueConstraint("lock_name", name="uq_job_locks_lock_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lock_name: Mapped[str] = mapped_column(String(120), index=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    old_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    channel: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)


class DashboardNotification(Base):
    __tablename__ = "dashboard_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    users: Mapped[list[User]] = relationship("User", back_populates="role_ref")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    username: Mapped[str] = mapped_column(String(120), index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    role: Mapped[str] = mapped_column(String(40), default="viewer", index=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    role_ref: Mapped[Role | None] = relationship("Role", back_populates="users")


class ItemAttributes(Base):
    __tablename__ = "item_attributes"
    __table_args__ = (UniqueConstraint("purchase_item_id", name="uq_item_attributes_purchase_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_items.id", ondelete="CASCADE"), index=True)
    normalized_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    article: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size: Mapped[str | None] = mapped_column(String(120), nullable=True)
    volume: Mapped[str | None] = mapped_column(String(120), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(120), nullable=True)
    material: Mapped[str | None] = mapped_column(String(120), nullable=True)
    package_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_required: Mapped[bool] = mapped_column(default=False)
    compatible_allowed: Mapped[bool] = mapped_column(default=True)
    keywords_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    stopwords_removed_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    numbers_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    units_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    risk_flags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    purchase_item: Mapped[PurchaseItem] = relationship("PurchaseItem", back_populates="attributes")


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_suppliers_normalized_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)

    offers: Mapped[list[MarketOffer]] = relationship("MarketOffer", back_populates="supplier")


class BusinessRule(Base):
    __tablename__ = "business_rules"
    __table_args__ = (UniqueConstraint("key", name="uq_business_rules_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)
