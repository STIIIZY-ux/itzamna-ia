"""Google Calendar: credenciales, mapeo de eventos y metadatos de sincronización.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Metadatos de sincronización en tasks ---
    op.add_column("tasks", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "tasks", sa.Column("removed_from_source_at", sa.DateTime(timezone=True), nullable=True)
    )

    # --- task_sources: mapeo tarea -> eventos externos (deduplicación) ---
    op.create_table(
        "task_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_sources_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_sources"),
        sa.UniqueConstraint("source", "source_event_id", name="uq_task_sources_source_event"),
    )
    op.create_index("ix_task_sources_task_id", "task_sources", ["task_id"], unique=False)

    # --- google_credentials: tokens OAuth cifrados ---
    op.create_table(
        "google_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
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
            ["user_id"], ["users.id"], name="fk_google_credentials_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_google_credentials"),
        sa.UniqueConstraint("user_id", name="uq_google_credentials_user_id"),
    )
    op.create_index(
        "ix_google_credentials_user_id", "google_credentials", ["user_id"], unique=True
    )

    # --- Ampliar CHECK de event_type en task_history ---
    op.drop_constraint("ck_task_history_event_type", "task_history", type_="check")
    op.create_check_constraint(
        "ck_task_history_event_type",
        "task_history",
        "event_type IN ('creada', 'estado_cambiado', 'prioridad_cambiada', 'fecha_cambiada', "
        "'actualizada', 'removida_de_fuente', 'duplicado_consolidado', 'otro')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_task_history_event_type", "task_history", type_="check")
    op.create_check_constraint(
        "ck_task_history_event_type",
        "task_history",
        "event_type IN ('creada', 'estado_cambiado', 'prioridad_cambiada', 'fecha_cambiada', "
        "'actualizada', 'otro')",
    )
    op.drop_table("google_credentials")
    op.drop_table("task_sources")
    op.drop_column("tasks", "removed_from_source_at")
    op.drop_column("tasks", "last_seen_at")
