"""Evidencia y archivos: columnas para subida, estado y almacenamiento.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("resources", sa.Column("file_unique_id", sa.String(length=255), nullable=True))
    op.add_column("resources", sa.Column("storage_key", sa.String(length=255), nullable=True))
    op.add_column("resources", sa.Column("content_type", sa.String(length=127), nullable=True))
    op.add_column("resources", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("resources", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("resources", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # task_id deja de ser obligatorio (la evidencia puede quedar sin asociar).
    op.alter_column("resources", "task_id", existing_type=sa.Integer(), nullable=True)

    op.create_foreign_key(
        "fk_resources_user_id_users",
        "resources",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_resources_user_id", "resources", ["user_id"], unique=False)
    op.create_index(
        "uq_resources_file_unique_id",
        "resources",
        ["file_unique_id"],
        unique=True,
        postgresql_where="file_unique_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_resources_status",
        "resources",
        "status IN ('received', 'pending_analysis')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_resources_status", "resources", type_="check")
    op.drop_index("uq_resources_file_unique_id", table_name="resources")
    op.drop_index("ix_resources_user_id", table_name="resources")
    op.drop_constraint("fk_resources_user_id_users", "resources", type_="foreignkey")
    op.alter_column("resources", "task_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("resources", "metadata")
    op.drop_column("resources", "status")
    op.drop_column("resources", "size_bytes")
    op.drop_column("resources", "content_type")
    op.drop_column("resources", "storage_key")
    op.drop_column("resources", "file_unique_id")
    op.drop_column("resources", "user_id")
