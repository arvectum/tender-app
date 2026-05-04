"""stage6 decision support

Revision ID: 0005_stage6_decision_support
Revises: 0004_stage5_quality_rules
Create Date: 2026-04-30 22:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_stage6_decision_support"
down_revision = "0004_stage5_quality_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchases", sa.Column("deadline_status", sa.String(length=40), nullable=True))
    op.execute("UPDATE purchases SET deadline_status = 'active' WHERE deadline_status IS NULL")
    op.alter_column("purchases", "deadline_status", nullable=False)
    op.create_index("ix_purchases_deadline_status", "purchases", ["deadline_status"], unique=False)

    op.create_table(
        "participation_strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("min_margin_percent", sa.Numeric(8, 2), nullable=False),
        sa.Column("min_profit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("max_cash_required", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_risk_level", sa.String(length=40), nullable=False),
        sa.Column("allow_unknown_delivery", sa.Boolean(), nullable=False),
        sa.Column("allow_unknown_supplier", sa.Boolean(), nullable=False),
        sa.Column("allow_manual_review_items", sa.Boolean(), nullable=False),
        sa.Column("preferred_categories_json", sa.JSON(), nullable=True),
        sa.Column("blocked_categories_json", sa.JSON(), nullable=True),
        sa.Column("preferred_regions_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_participation_strategies_name"),
    )
    op.create_index("ix_participation_strategies_name", "participation_strategies", ["name"], unique=False)
    op.create_index("ix_participation_strategies_is_active", "participation_strategies", ["is_active"], unique=False)

    op.create_table(
        "purchase_decision_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("score_total", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_margin", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_profit", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_deadline", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_data_quality", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_supplier_quality", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_competition", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_cash_efficiency", sa.Numeric(8, 2), nullable=False),
        sa.Column("score_risk", sa.Numeric(8, 2), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=60), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("cash_roi_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("deadline_status", sa.String(length=40), nullable=False),
        sa.Column("competition_level", sa.String(length=40), nullable=False),
        sa.Column("competition_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("purchase_id", name="uq_purchase_decision_scores_purchase"),
    )
    op.create_index("ix_purchase_decision_scores_purchase_id", "purchase_decision_scores", ["purchase_id"], unique=True)
    op.create_index("ix_purchase_decision_scores_risk_level", "purchase_decision_scores", ["risk_level"], unique=False)
    op.create_index("ix_purchase_decision_scores_decision", "purchase_decision_scores", ["decision"], unique=False)
    op.create_index("ix_purchase_decision_scores_deadline_status", "purchase_decision_scores", ["deadline_status"], unique=False)
    op.create_index("ix_purchase_decision_scores_competition_level", "purchase_decision_scores", ["competition_level"], unique=False)

    op.create_table(
        "purchase_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("purchase_id", name="uq_purchase_watchlist_purchase"),
    )
    op.create_index("ix_purchase_watchlist_purchase_id", "purchase_watchlist", ["purchase_id"], unique=True)
    op.create_index("ix_purchase_watchlist_status", "purchase_watchlist", ["status"], unique=False)

    op.create_table(
        "dashboard_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dashboard_notifications_event_type", "dashboard_notifications", ["event_type"], unique=False)
    op.create_index("ix_dashboard_notifications_entity_type", "dashboard_notifications", ["entity_type"], unique=False)
    op.create_index("ix_dashboard_notifications_entity_id", "dashboard_notifications", ["entity_id"], unique=False)
    op.create_index("ix_dashboard_notifications_status", "dashboard_notifications", ["status"], unique=False)
    op.create_index("ix_dashboard_notifications_created_at", "dashboard_notifications", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dashboard_notifications_created_at", table_name="dashboard_notifications")
    op.drop_index("ix_dashboard_notifications_status", table_name="dashboard_notifications")
    op.drop_index("ix_dashboard_notifications_entity_id", table_name="dashboard_notifications")
    op.drop_index("ix_dashboard_notifications_entity_type", table_name="dashboard_notifications")
    op.drop_index("ix_dashboard_notifications_event_type", table_name="dashboard_notifications")
    op.drop_table("dashboard_notifications")

    op.drop_index("ix_purchase_watchlist_status", table_name="purchase_watchlist")
    op.drop_index("ix_purchase_watchlist_purchase_id", table_name="purchase_watchlist")
    op.drop_table("purchase_watchlist")

    op.drop_index("ix_purchase_decision_scores_competition_level", table_name="purchase_decision_scores")
    op.drop_index("ix_purchase_decision_scores_deadline_status", table_name="purchase_decision_scores")
    op.drop_index("ix_purchase_decision_scores_decision", table_name="purchase_decision_scores")
    op.drop_index("ix_purchase_decision_scores_risk_level", table_name="purchase_decision_scores")
    op.drop_index("ix_purchase_decision_scores_purchase_id", table_name="purchase_decision_scores")
    op.drop_table("purchase_decision_scores")

    op.drop_index("ix_participation_strategies_is_active", table_name="participation_strategies")
    op.drop_index("ix_participation_strategies_name", table_name="participation_strategies")
    op.drop_table("participation_strategies")

    op.drop_index("ix_purchases_deadline_status", table_name="purchases")
    op.drop_column("purchases", "deadline_status")
