"""stage4 ops schema

Revision ID: 0003_stage4_ops
Revises: 0002_stage3_price_search
Create Date: 2026-04-30 18:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_stage4_ops"
down_revision = "0002_stage3_price_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_offers", sa.Column("manual_override_relevance", sa.Boolean(), nullable=True))
    op.add_column("market_offers", sa.Column("manual_override_exclude", sa.Boolean(), nullable=True))
    op.add_column("market_offers", sa.Column("manual_override_include", sa.Boolean(), nullable=True))
    op.add_column("market_offers", sa.Column("manual_comment", sa.Text(), nullable=True))
    op.add_column("market_offers", sa.Column("updated_by_user_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE market_offers SET manual_override_exclude = false WHERE manual_override_exclude IS NULL")
    op.execute("UPDATE market_offers SET manual_override_include = false WHERE manual_override_include IS NULL")
    op.alter_column("market_offers", "manual_override_exclude", nullable=False)
    op.alter_column("market_offers", "manual_override_include", nullable=False)

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(12, 3), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_runs_job_type", "job_runs", ["job_type"], unique=False)
    op.create_index("ix_job_runs_source", "job_runs", ["source"], unique=False)
    op.create_index("ix_job_runs_status", "job_runs", ["status"], unique=False)
    op.create_index("ix_job_runs_created_at", "job_runs", ["created_at"], unique=False)

    op.create_table(
        "job_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lock_name", sa.String(length=120), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("lock_name", name="uq_job_locks_lock_name"),
    )
    op.create_index("ix_job_locks_lock_name", "job_locks", ["lock_name"], unique=False)
    op.create_index("ix_job_locks_expires_at", "job_locks", ["expires_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notification_logs_event_type", "notification_logs", ["event_type"], unique=False)
    op.create_index("ix_notification_logs_entity_type", "notification_logs", ["entity_type"], unique=False)
    op.create_index("ix_notification_logs_entity_id", "notification_logs", ["entity_id"], unique=False)
    op.create_index("ix_notification_logs_channel", "notification_logs", ["channel"], unique=False)
    op.create_index("ix_notification_logs_status", "notification_logs", ["status"], unique=False)
    op.create_index("ix_notification_logs_created_at", "notification_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_logs_created_at", table_name="notification_logs")
    op.drop_index("ix_notification_logs_status", table_name="notification_logs")
    op.drop_index("ix_notification_logs_channel", table_name="notification_logs")
    op.drop_index("ix_notification_logs_entity_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_entity_type", table_name="notification_logs")
    op.drop_index("ix_notification_logs_event_type", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_job_locks_expires_at", table_name="job_locks")
    op.drop_index("ix_job_locks_lock_name", table_name="job_locks")
    op.drop_table("job_locks")

    op.drop_index("ix_job_runs_created_at", table_name="job_runs")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_source", table_name="job_runs")
    op.drop_index("ix_job_runs_job_type", table_name="job_runs")
    op.drop_table("job_runs")

    op.drop_column("market_offers", "updated_by_user_at")
    op.drop_column("market_offers", "manual_comment")
    op.drop_column("market_offers", "manual_override_include")
    op.drop_column("market_offers", "manual_override_exclude")
    op.drop_column("market_offers", "manual_override_relevance")
