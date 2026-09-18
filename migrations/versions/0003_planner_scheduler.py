"""Planner/Scheduler/Accountability: jobs persistentes y estado de accountability.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- scheduled_jobs ---
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_scheduled_jobs_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_scheduled_jobs_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scheduled_jobs"),
        sa.UniqueConstraint("dedup_key", name="uq_scheduled_jobs_dedup_key"),
    )
    op.create_index("ix_scheduled_jobs_user_id", "scheduled_jobs", ["user_id"], unique=False)
    op.create_index("ix_scheduled_jobs_task_id", "scheduled_jobs", ["task_id"], unique=False)
    op.create_index(
        "ix_scheduled_jobs_status_scheduled", "scheduled_jobs", ["status", "scheduled_at"], unique=False
    )
    op.create_check_constraint(
        "ck_scheduled_jobs_kind",
        "scheduled_jobs",
        "kind IN ('start_reminder', 'due_reminder', 'nudge', 'evidence_request')",
    )
    op.create_check_constraint(
        "ck_scheduled_jobs_status",
        "scheduled_jobs",
        "status IN ('pending', 'claimed', 'sent', 'failed', 'cancelled')",
    )

    # --- accountability ---
    op.create_table(
        "accountability",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=50), server_default="pending_reminder", nullable=False),
        sa.Column("mode", sa.String(length=50), server_default="tryhard", nullable=False),
        sa.Column("reminder_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rescue_candidate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_accountability_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_accountability_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accountability"),
        sa.UniqueConstraint("task_id", name="uq_accountability_task_id"),
    )
    op.create_index("ix_accountability_user_id", "accountability", ["user_id"], unique=False)
    op.create_index("ix_accountability_task_id", "accountability", ["task_id"], unique=True)
    op.create_check_constraint(
        "ck_accountability_state",
        "accountability",
        "state IN ('pending_reminder', 'reminder_sent', 'awaiting_commitment', "
        "'committed', 'awaiting_evidence', 'completed')",
    )
    op.create_check_constraint(
        "ck_accountability_mode",
        "accountability",
        "mode IN ('tryhard', 'guerra', 'silencio')",
    )

    # --- notification_preferences ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=50), server_default="tryhard", nullable=False),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_hour_start", sa.Integer(), server_default="9", nullable=False),
        sa.Column("active_hour_end", sa.Integer(), server_default="21", nullable=False),
        sa.Column("max_reminders_per_day", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_notification_preferences_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_preferences"),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
    )
    op.create_index(
        "ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True
    )
    op.create_check_constraint(
        "ck_notification_preferences_mode",
        "notification_preferences",
        "mode IN ('tryhard', 'guerra', 'silencio')",
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("accountability")
    op.drop_table("scheduled_jobs")
