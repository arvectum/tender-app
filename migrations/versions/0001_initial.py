"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-30 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("region_code", sa.String(length=20), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("submission_deadline", sa.DateTime(), nullable=True),
        sa.Column("commission_fee_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("security_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_total_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at_source", sa.DateTime(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_purchase_source_external_id"),
    )
    op.create_index("ix_purchases_source", "purchases", ["source"], unique=False)
    op.create_index("ix_purchases_external_id", "purchases", ["external_id"], unique=False)
    op.create_index("ix_purchases_status", "purchases", ["status"], unique=False)
    op.create_index("ix_purchases_region", "purchases", ["region"], unique=False)
    op.create_index("ix_purchases_region_code", "purchases", ["region_code"], unique=False)
    op.create_index("ix_purchases_parsed_at", "purchases", ["parsed_at"], unique=False)

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_external_id", sa.String(length=120), nullable=True),
        sa.Column("position_hash", sa.String(length=64), nullable=False),
        sa.Column("item_name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("okpd2", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("max_unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_total_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("delivery_region", sa.String(length=120), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("delivery_terms", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("purchase_id", "position_hash", name="uq_purchase_item_position_hash"),
    )
    op.create_index("ix_purchase_items_purchase_id", "purchase_items", ["purchase_id"], unique=False)
    op.create_index("ix_purchase_items_position_external_id", "purchase_items", ["position_external_id"], unique=False)
    op.create_index("ix_purchase_items_position_hash", "purchase_items", ["position_hash"], unique=False)
    op.create_index("ix_purchase_items_item_name", "purchase_items", ["item_name"], unique=False)
    op.create_index("ix_purchase_items_okpd2", "purchase_items", ["okpd2"], unique=False)

    op.create_table(
        "market_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_name", sa.String(length=500), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("delivery_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("region_code", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_offers_item_name", "market_offers", ["item_name"], unique=False)
    op.create_index("ix_market_offers_region_code", "market_offers", ["region_code"], unique=False)

    op.create_table(
        "purchase_calculations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("max_total_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("estimated_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("margin_percent", sa.Numeric(8, 2), nullable=False),
        sa.Column("cash_required", sa.Numeric(14, 2), nullable=False),
        sa.Column("recommendation_status", sa.String(length=60), nullable=False),
        sa.Column("problematic_items_count", sa.Integer(), nullable=False),
        sa.Column("unknown_delivery_items_count", sa.Integer(), nullable=False),
        sa.Column("attractiveness_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("purchase_id"),
    )
    op.create_index("ix_purchase_calculations_purchase_id", "purchase_calculations", ["purchase_id"], unique=True)
    op.create_index(
        "ix_purchase_calculations_recommendation_status", "purchase_calculations", ["recommendation_status"], unique=False
    )

    op.create_table(
        "item_cost_calculations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchase_item_id", sa.Integer(), sa.ForeignKey("purchase_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("required_quantity", sa.Integer(), nullable=False),
        sa.Column("covered_quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_item_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("unknown_delivery_used", sa.Boolean(), nullable=False),
        sa.Column("selected_offers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("purchase_id", "purchase_item_id", name="uq_item_calc_purchase_item"),
    )
    op.create_index("ix_item_cost_calculations_purchase_id", "item_cost_calculations", ["purchase_id"], unique=False)
    op.create_index("ix_item_cost_calculations_purchase_item_id", "item_cost_calculations", ["purchase_item_id"], unique=False)
    op.create_index("ix_item_cost_calculations_status", "item_cost_calculations", ["status"], unique=False)

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"], unique=False)

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("request_status", sa.String(length=100), nullable=True),
        sa.Column("limit", sa.Integer(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("found_count", sa.Integer(), nullable=False),
        sa.Column("filtered_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_import_jobs_source", "import_jobs", ["source"], unique=False)
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"], unique=False)
    op.create_index("ix_import_jobs_created_at", "import_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_jobs_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_source", table_name="import_jobs")
    op.drop_table("import_jobs")

    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index("ix_item_cost_calculations_status", table_name="item_cost_calculations")
    op.drop_index("ix_item_cost_calculations_purchase_item_id", table_name="item_cost_calculations")
    op.drop_index("ix_item_cost_calculations_purchase_id", table_name="item_cost_calculations")
    op.drop_table("item_cost_calculations")

    op.drop_index("ix_purchase_calculations_recommendation_status", table_name="purchase_calculations")
    op.drop_index("ix_purchase_calculations_purchase_id", table_name="purchase_calculations")
    op.drop_table("purchase_calculations")

    op.drop_index("ix_market_offers_region_code", table_name="market_offers")
    op.drop_index("ix_market_offers_item_name", table_name="market_offers")
    op.drop_table("market_offers")

    op.drop_index("ix_purchase_items_okpd2", table_name="purchase_items")
    op.drop_index("ix_purchase_items_item_name", table_name="purchase_items")
    op.drop_index("ix_purchase_items_position_hash", table_name="purchase_items")
    op.drop_index("ix_purchase_items_position_external_id", table_name="purchase_items")
    op.drop_index("ix_purchase_items_purchase_id", table_name="purchase_items")
    op.drop_table("purchase_items")

    op.drop_index("ix_purchases_parsed_at", table_name="purchases")
    op.drop_index("ix_purchases_region_code", table_name="purchases")
    op.drop_index("ix_purchases_region", table_name="purchases")
    op.drop_index("ix_purchases_status", table_name="purchases")
    op.drop_index("ix_purchases_external_id", table_name="purchases")
    op.drop_index("ix_purchases_source", table_name="purchases")
    op.drop_table("purchases")
