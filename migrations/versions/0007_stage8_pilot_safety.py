"""stage8 pilot safety

Revision ID: 0007_stage8_pilot_safety
Revises: 0006_stage7_product_packaging
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_stage8_pilot_safety"
down_revision = "0006_stage7_product_packaging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchases", sa.Column("data_quality", sa.String(length=20), nullable=True, server_default="medium"))
    op.add_column("purchases", sa.Column("data_quality_warnings_json", sa.JSON(), nullable=True, server_default="[]"))
    op.add_column("purchases", sa.Column("source_version", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("purchases", sa.Column("source_history_json", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_purchases_data_quality"), "purchases", ["data_quality"], unique=False)

    op.add_column(
        "purchase_calculations",
        sa.Column("verification_status", sa.String(length=30), nullable=True, server_default="verified"),
    )
    op.add_column(
        "purchase_calculations",
        sa.Column("financial_check_status", sa.String(length=20), nullable=True, server_default="unknown"),
    )
    op.add_column(
        "purchase_calculations",
        sa.Column("financial_check_flags_json", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.create_index(op.f("ix_purchase_calculations_verification_status"), "purchase_calculations", ["verification_status"], unique=False)
    op.create_index(op.f("ix_purchase_calculations_financial_check_status"), "purchase_calculations", ["financial_check_status"], unique=False)

    op.add_column(
        "purchase_decision_scores",
        sa.Column("decision_status", sa.String(length=20), nullable=True, server_default="draft"),
    )
    op.add_column("purchase_decision_scores", sa.Column("explanation_json", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_purchase_decision_scores_decision_status"), "purchase_decision_scores", ["decision_status"], unique=False)

    op.execute(sa.text("UPDATE purchases SET data_quality = 'medium' WHERE data_quality IS NULL"))
    op.execute(sa.text("UPDATE purchases SET data_quality_warnings_json = '[]' WHERE data_quality_warnings_json IS NULL"))
    op.execute(sa.text("UPDATE purchases SET source_version = 1 WHERE source_version IS NULL"))
    op.execute(sa.text("UPDATE purchase_calculations SET verification_status = 'verified' WHERE verification_status IS NULL"))
    op.execute(sa.text("UPDATE purchase_calculations SET financial_check_status = 'unknown' WHERE financial_check_status IS NULL"))
    op.execute(sa.text("UPDATE purchase_calculations SET financial_check_flags_json = '[]' WHERE financial_check_flags_json IS NULL"))
    op.execute(sa.text("UPDATE purchase_decision_scores SET decision_status = 'draft' WHERE decision_status IS NULL"))

    op.alter_column("purchases", "data_quality", server_default=None)
    op.alter_column("purchases", "data_quality_warnings_json", server_default=None)
    op.alter_column("purchases", "source_version", server_default=None)
    op.alter_column("purchase_calculations", "verification_status", server_default=None)
    op.alter_column("purchase_calculations", "financial_check_status", server_default=None)
    op.alter_column("purchase_calculations", "financial_check_flags_json", server_default=None)
    op.alter_column("purchase_decision_scores", "decision_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_decision_scores_decision_status"), table_name="purchase_decision_scores")
    op.drop_column("purchase_decision_scores", "explanation_json")
    op.drop_column("purchase_decision_scores", "decision_status")

    op.drop_index(op.f("ix_purchase_calculations_financial_check_status"), table_name="purchase_calculations")
    op.drop_index(op.f("ix_purchase_calculations_verification_status"), table_name="purchase_calculations")
    op.drop_column("purchase_calculations", "financial_check_flags_json")
    op.drop_column("purchase_calculations", "financial_check_status")
    op.drop_column("purchase_calculations", "verification_status")

    op.drop_index(op.f("ix_purchases_data_quality"), table_name="purchases")
    op.drop_column("purchases", "source_history_json")
    op.drop_column("purchases", "source_version")
    op.drop_column("purchases", "data_quality_warnings_json")
    op.drop_column("purchases", "data_quality")
