"""Estimaciones adaptativas: columnas de estimación ajustada.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("adjusted_estimated_minutes", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("estimate_basis", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "estimate_basis")
    op.drop_column("tasks", "adjusted_estimated_minutes")
