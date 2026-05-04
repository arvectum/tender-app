"""stage3 price search schema updates

Revision ID: 0002_stage3_price_search
Revises: 0001_initial
Create Date: 2026-04-30 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_stage3_price_search"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_offers", sa.Column("provider", sa.String(length=100), nullable=True))
    op.add_column("market_offers", sa.Column("purchase_id", sa.Integer(), nullable=True))
    op.add_column("market_offers", sa.Column("purchase_item_id", sa.Integer(), nullable=True))
    op.add_column("market_offers", sa.Column("purchase_external_id", sa.String(length=120), nullable=True))
    op.add_column("market_offers", sa.Column("position_external_id", sa.String(length=120), nullable=True))
    op.add_column("market_offers", sa.Column("offer_title", sa.String(length=500), nullable=True))
    op.add_column("market_offers", sa.Column("offer_url", sa.Text(), nullable=True))
    op.add_column("market_offers", sa.Column("seller_name", sa.String(length=255), nullable=True))
    op.add_column("market_offers", sa.Column("region", sa.String(length=120), nullable=True))
    op.add_column("market_offers", sa.Column("delivery_days", sa.Integer(), nullable=True))
    op.add_column("market_offers", sa.Column("effective_unit_price", sa.Numeric(14, 2), nullable=True))
    op.add_column("market_offers", sa.Column("relevance_score", sa.Numeric(8, 4), nullable=True))
    op.add_column("market_offers", sa.Column("risk_flags", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("market_offers", sa.Column("raw_payload", sa.JSON(), nullable=True))
    op.add_column("market_offers", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.create_index("ix_market_offers_provider", "market_offers", ["provider"], unique=False)
    op.create_index("ix_market_offers_source", "market_offers", ["source"], unique=False)
    op.create_index("ix_market_offers_purchase_id", "market_offers", ["purchase_id"], unique=False)
    op.create_index("ix_market_offers_purchase_item_id", "market_offers", ["purchase_item_id"], unique=False)
    op.create_index("ix_market_offers_purchase_external_id", "market_offers", ["purchase_external_id"], unique=False)
    op.create_index("ix_market_offers_position_external_id", "market_offers", ["position_external_id"], unique=False)
    op.create_index("ix_market_offers_is_relevant", "market_offers", ["is_relevant"], unique=False)

    op.create_foreign_key(
        "fk_market_offers_purchase_id",
        "market_offers",
        "purchases",
        ["purchase_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_market_offers_purchase_item_id",
        "market_offers",
        "purchase_items",
        ["purchase_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("item_cost_calculations", sa.Column("risk_flags", sa.JSON(), nullable=True))
    op.add_column("item_cost_calculations", sa.Column("calculation_details_json", sa.JSON(), nullable=True))

    op.create_table(
        "calculation_offer_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_cost_calculation_id",
            sa.Integer(),
            sa.ForeignKey("item_cost_calculations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("market_offer_id", sa.Integer(), sa.ForeignKey("market_offers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("taken_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("delivery_price_allocated", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_calculation_offer_usages_item_cost_calculation_id",
        "calculation_offer_usages",
        ["item_cost_calculation_id"],
        unique=False,
    )
    op.create_index("ix_calculation_offer_usages_market_offer_id", "calculation_offer_usages", ["market_offer_id"], unique=False)

    op.execute("UPDATE market_offers SET provider = COALESCE(source, 'stub')")
    op.execute("UPDATE market_offers SET seller_name = supplier_name WHERE seller_name IS NULL")
    op.execute("UPDATE market_offers SET risk_flags = '[]'::json WHERE risk_flags IS NULL")
    op.execute("UPDATE item_cost_calculations SET risk_flags = '[]'::json WHERE risk_flags IS NULL")

    op.alter_column("market_offers", "provider", nullable=False)
    op.alter_column("item_cost_calculations", "risk_flags", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_calculation_offer_usages_market_offer_id", table_name="calculation_offer_usages")
    op.drop_index("ix_calculation_offer_usages_item_cost_calculation_id", table_name="calculation_offer_usages")
    op.drop_table("calculation_offer_usages")

    op.drop_column("item_cost_calculations", "calculation_details_json")
    op.drop_column("item_cost_calculations", "risk_flags")

    op.drop_constraint("fk_market_offers_purchase_item_id", "market_offers", type_="foreignkey")
    op.drop_constraint("fk_market_offers_purchase_id", "market_offers", type_="foreignkey")

    op.drop_index("ix_market_offers_is_relevant", table_name="market_offers")
    op.drop_index("ix_market_offers_position_external_id", table_name="market_offers")
    op.drop_index("ix_market_offers_purchase_external_id", table_name="market_offers")
    op.drop_index("ix_market_offers_purchase_item_id", table_name="market_offers")
    op.drop_index("ix_market_offers_purchase_id", table_name="market_offers")
    op.drop_index("ix_market_offers_source", table_name="market_offers")
    op.drop_index("ix_market_offers_provider", table_name="market_offers")

    op.drop_column("market_offers", "updated_at")
    op.drop_column("market_offers", "raw_payload")
    op.drop_column("market_offers", "comment")
    op.drop_column("market_offers", "risk_flags")
    op.drop_column("market_offers", "relevance_score")
    op.drop_column("market_offers", "effective_unit_price")
    op.drop_column("market_offers", "delivery_days")
    op.drop_column("market_offers", "region")
    op.drop_column("market_offers", "seller_name")
    op.drop_column("market_offers", "offer_url")
    op.drop_column("market_offers", "offer_title")
    op.drop_column("market_offers", "position_external_id")
    op.drop_column("market_offers", "purchase_external_id")
    op.drop_column("market_offers", "purchase_item_id")
    op.drop_column("market_offers", "purchase_id")
    op.drop_column("market_offers", "provider")
