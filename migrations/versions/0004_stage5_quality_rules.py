"""stage5 quality rules schema

Revision ID: 0004_stage5_quality_rules
Revises: 0003_stage4_ops
Create Date: 2026-04-30 21:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_stage5_quality_rules"
down_revision = "0003_stage4_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Numeric(5, 2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_suppliers_normalized_name"),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"], unique=False)
    op.create_index("ix_suppliers_normalized_name", "suppliers", ["normalized_name"], unique=False)
    op.create_index("ix_suppliers_status", "suppliers", ["status"], unique=False)

    op.create_table(
        "business_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", name="uq_business_rules_key"),
    )
    op.create_index("ix_business_rules_key", "business_rules", ["key"], unique=False)

    op.create_table(
        "item_attributes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_item_id", sa.Integer(), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("article", sa.String(length=120), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=True),
        sa.Column("size", sa.String(length=120), nullable=True),
        sa.Column("volume", sa.String(length=120), nullable=True),
        sa.Column("weight", sa.String(length=120), nullable=True),
        sa.Column("material", sa.String(length=120), nullable=True),
        sa.Column("package_quantity", sa.Integer(), nullable=True),
        sa.Column("original_required", sa.Boolean(), nullable=False),
        sa.Column("compatible_allowed", sa.Boolean(), nullable=False),
        sa.Column("keywords_json", sa.JSON(), nullable=True),
        sa.Column("stopwords_removed_json", sa.JSON(), nullable=True),
        sa.Column("numbers_json", sa.JSON(), nullable=True),
        sa.Column("units_json", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("risk_flags_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_item_id"], ["purchase_items.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("purchase_item_id", name="uq_item_attributes_purchase_item"),
    )
    op.create_index("ix_item_attributes_purchase_item_id", "item_attributes", ["purchase_item_id"], unique=False)
    op.create_index("ix_item_attributes_category", "item_attributes", ["category"], unique=False)
    op.create_index("ix_item_attributes_brand", "item_attributes", ["brand"], unique=False)
    op.create_index("ix_item_attributes_article", "item_attributes", ["article"], unique=False)

    op.add_column("market_offers", sa.Column("match_score", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_offers", sa.Column("match_reasons_json", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("match_risk_flags_json", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("matched_fields_json", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("mismatched_fields_json", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("hard_reject_reason", sa.String(length=255), nullable=True))
    op.add_column("market_offers", sa.Column("delivery_type", sa.String(length=40), nullable=True))
    op.add_column("market_offers", sa.Column("delivery_price_type", sa.String(length=40), nullable=True))
    op.add_column("market_offers", sa.Column("pickup_available", sa.Boolean(), nullable=True))
    op.add_column("market_offers", sa.Column("delivery_unknown", sa.Boolean(), nullable=True))
    op.add_column("market_offers", sa.Column("min_order_quantity", sa.Integer(), nullable=True))
    op.add_column("market_offers", sa.Column("package_quantity", sa.Integer(), nullable=True))
    op.add_column("market_offers", sa.Column("seller_name_normalized", sa.String(length=255), nullable=True))
    op.add_column("market_offers", sa.Column("supplier_status", sa.String(length=40), nullable=True))
    op.add_column("market_offers", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_index("ix_market_offers_seller_name_normalized", "market_offers", ["seller_name_normalized"], unique=False)
    op.create_index("ix_market_offers_supplier_status", "market_offers", ["supplier_status"], unique=False)
    op.create_index("ix_market_offers_supplier_id", "market_offers", ["supplier_id"], unique=False)
    op.create_foreign_key(
        "fk_market_offers_supplier_id",
        "market_offers",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE market_offers SET delivery_unknown = false WHERE delivery_unknown IS NULL")
    op.execute("UPDATE market_offers SET supplier_status = 'unknown' WHERE supplier_status IS NULL")
    op.alter_column("market_offers", "delivery_unknown", nullable=False)
    op.alter_column("market_offers", "supplier_status", nullable=False)

    op.add_column("purchase_calculations", sa.Column("vat_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("cost_before_tax", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("cost_after_tax", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("profit_before_tax", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("profit_after_tax", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("margin_before_tax_percent", sa.Numeric(8, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("margin_after_tax_percent", sa.Numeric(8, 2), nullable=True))
    op.add_column("purchase_calculations", sa.Column("explanation_summary", sa.Text(), nullable=True))
    op.add_column("purchase_calculations", sa.Column("risk_level", sa.String(length=40), nullable=True))
    op.execute("UPDATE purchase_calculations SET vat_amount = 0 WHERE vat_amount IS NULL")
    op.execute("UPDATE purchase_calculations SET tax_amount = 0 WHERE tax_amount IS NULL")
    op.execute("UPDATE purchase_calculations SET cost_before_tax = estimated_cost WHERE cost_before_tax IS NULL")
    op.execute("UPDATE purchase_calculations SET cost_after_tax = estimated_cost WHERE cost_after_tax IS NULL")
    op.execute("UPDATE purchase_calculations SET profit_before_tax = estimated_profit WHERE profit_before_tax IS NULL")
    op.execute("UPDATE purchase_calculations SET profit_after_tax = estimated_profit WHERE profit_after_tax IS NULL")
    op.execute("UPDATE purchase_calculations SET margin_before_tax_percent = margin_percent WHERE margin_before_tax_percent IS NULL")
    op.execute("UPDATE purchase_calculations SET margin_after_tax_percent = margin_percent WHERE margin_after_tax_percent IS NULL")
    op.alter_column("purchase_calculations", "vat_amount", nullable=False)
    op.alter_column("purchase_calculations", "tax_amount", nullable=False)
    op.alter_column("purchase_calculations", "cost_before_tax", nullable=False)
    op.alter_column("purchase_calculations", "cost_after_tax", nullable=False)
    op.alter_column("purchase_calculations", "profit_before_tax", nullable=False)
    op.alter_column("purchase_calculations", "profit_after_tax", nullable=False)
    op.alter_column("purchase_calculations", "margin_before_tax_percent", nullable=False)
    op.alter_column("purchase_calculations", "margin_after_tax_percent", nullable=False)


def downgrade() -> None:
    op.drop_column("purchase_calculations", "risk_level")
    op.drop_column("purchase_calculations", "explanation_summary")
    op.drop_column("purchase_calculations", "margin_after_tax_percent")
    op.drop_column("purchase_calculations", "margin_before_tax_percent")
    op.drop_column("purchase_calculations", "profit_after_tax")
    op.drop_column("purchase_calculations", "profit_before_tax")
    op.drop_column("purchase_calculations", "cost_after_tax")
    op.drop_column("purchase_calculations", "cost_before_tax")
    op.drop_column("purchase_calculations", "tax_amount")
    op.drop_column("purchase_calculations", "vat_amount")

    op.drop_constraint("fk_market_offers_supplier_id", "market_offers", type_="foreignkey")
    op.drop_index("ix_market_offers_supplier_id", table_name="market_offers")
    op.drop_index("ix_market_offers_supplier_status", table_name="market_offers")
    op.drop_index("ix_market_offers_seller_name_normalized", table_name="market_offers")
    op.drop_column("market_offers", "supplier_id")
    op.drop_column("market_offers", "supplier_status")
    op.drop_column("market_offers", "seller_name_normalized")
    op.drop_column("market_offers", "package_quantity")
    op.drop_column("market_offers", "min_order_quantity")
    op.drop_column("market_offers", "delivery_unknown")
    op.drop_column("market_offers", "pickup_available")
    op.drop_column("market_offers", "delivery_price_type")
    op.drop_column("market_offers", "delivery_type")
    op.drop_column("market_offers", "hard_reject_reason")
    op.drop_column("market_offers", "mismatched_fields_json")
    op.drop_column("market_offers", "matched_fields_json")
    op.drop_column("market_offers", "match_risk_flags_json")
    op.drop_column("market_offers", "match_reasons_json")
    op.drop_column("market_offers", "match_score")

    op.drop_index("ix_item_attributes_article", table_name="item_attributes")
    op.drop_index("ix_item_attributes_brand", table_name="item_attributes")
    op.drop_index("ix_item_attributes_category", table_name="item_attributes")
    op.drop_index("ix_item_attributes_purchase_item_id", table_name="item_attributes")
    op.drop_table("item_attributes")

    op.drop_index("ix_business_rules_key", table_name="business_rules")
    op.drop_table("business_rules")

    op.drop_index("ix_suppliers_status", table_name="suppliers")
    op.drop_index("ix_suppliers_normalized_name", table_name="suppliers")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_table("suppliers")
