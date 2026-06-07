"""link an applied correction's primitive on the feedback row (close the loop)

Revision ID: 015
Revises: 014
Create Date: 2026-06-07

Phase F — the improvement flywheel closes the loop: an accepted
``primitive_correction`` / ``missing_data`` flag creates an org-private
``user_primitives`` row, and we record THAT row's id here so the resolved flag
points at the fix it produced. The column is nullable (most flags never produce a
primitive) and carries no FK across the RLS boundary — both tables are org-scoped
by ``app.org_id``, so the id is only ever meaningful within the same tenant.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feedback_events",
        sa.Column("resolved_primitive_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feedback_events", "resolved_primitive_id")
