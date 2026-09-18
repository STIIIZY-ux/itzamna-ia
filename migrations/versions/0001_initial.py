"""Esquema inicial de persistencia.

Revision ID: 0001
Revises:
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )

    # --- subjects ---
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
            ["user_id"], ["users.id"], name="fk_subjects_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
        sa.UniqueConstraint("user_id", "name", name="uq_subjects_user_name"),
    )
    op.create_index("ix_subjects_user_id", "subjects", ["user_id"], unique=False)

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.String(length=50), server_default="media", nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pendiente", nullable=False),
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
            ["user_id"], ["users.id"], name="fk_tasks_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name="fk_tasks_subject_id_subjects", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
        sa.UniqueConstraint("source", "source_event_id", name="uq_tasks_source_event"),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"], unique=False)
    op.create_index("ix_tasks_subject_id", "tasks", ["subject_id"], unique=False)
    op.create_index("ix_tasks_source_event_id", "tasks", ["source_event_id"], unique=False)

    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status IN ('pendiente', 'notificada', 'compromiso', 'iniciada', 'en_progreso', 'terminada', 'entregada', 'bloqueada')",
    )
    op.create_check_constraint(
        "ck_tasks_priority",
        "tasks",
        "priority IN ('baja', 'media', 'alta', 'urgente')",
    )
    op.create_check_constraint(
        "ck_tasks_source",
        "tasks",
        "source IN ('manual', 'google_calendar')",
    )

    # --- task_history ---
    op.create_table(
        "task_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("from_value", sa.String(length=255), nullable=True),
        sa.Column("to_value", sa.String(length=255), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_history_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_history"),
    )
    op.create_index("ix_task_history_task_id", "task_history", ["task_id"], unique=False)
    op.create_check_constraint(
        "ck_task_history_event_type",
        "task_history",
        "event_type IN ('creada', 'estado_cambiado', 'prioridad_cambiada', 'fecha_cambiada', 'actualizada', 'otro')",
    )

    # --- commitments ---
    op.create_table(
        "commitments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="activo", nullable=False),
        sa.Column(
            "committed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            ["task_id"], ["tasks.id"], name="fk_commitments_task_id_tasks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_commitments_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commitments"),
    )
    op.create_index("ix_commitments_task_id", "commitments", ["task_id"], unique=False)
    op.create_index("ix_commitments_user_id", "commitments", ["user_id"], unique=False)
    op.create_check_constraint(
        "ck_commitments_status",
        "commitments",
        "status IN ('activo', 'completado', 'cancelado')",
    )

    # --- resources ---
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("uri", sa.String(length=2048), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_resources_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resources"),
    )
    op.create_index("ix_resources_task_id", "resources", ["task_id"], unique=False)
    op.create_check_constraint(
        "ck_resources_resource_type",
        "resources",
        "resource_type IN ('pdf', 'documento', 'imagen', 'enlace', 'material', 'evidencia', 'entregable', 'otro')",
    )


def downgrade() -> None:
    op.drop_table("resources")
    op.drop_table("commitments")
    op.drop_table("task_history")
    op.drop_table("tasks")
    op.drop_table("subjects")
    op.drop_table("users")
