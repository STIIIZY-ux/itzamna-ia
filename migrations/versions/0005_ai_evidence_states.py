"""IA: estados de evidencia (veredictos) y job de análisis de evidencia.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_resources_status", "resources", type_="check")
    op.create_check_constraint(
        "ck_resources_status",
        "resources",
        "status IN ('received', 'pending_analysis', 'valid', 'invalid', 'uncertain')",
    )

    op.drop_constraint("ck_scheduled_jobs_kind", "scheduled_jobs", type_="check")
    op.create_check_constraint(
        "ck_scheduled_jobs_kind",
        "scheduled_jobs",
        "kind IN ('start_reminder', 'due_reminder', 'nudge', 'evidence_request', 'analyze_evidence')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_scheduled_jobs_kind", "scheduled_jobs", type_="check")
    op.create_check_constraint(
        "ck_scheduled_jobs_kind",
        "scheduled_jobs",
        "kind IN ('start_reminder', 'due_reminder', 'nudge', 'evidence_request')",
    )

    op.drop_constraint("ck_resources_status", "resources", type_="check")
    op.create_check_constraint(
        "ck_resources_status",
        "resources",
        "status IN ('received', 'pending_analysis')",
    )
