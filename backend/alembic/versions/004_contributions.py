"""create contributions table

Revision ID: 004
Revises: 003
Create Date: 2026-05-30

Wave 4 / Risk-2 hardening: persist community contribution proposals (the moat
intake) instead of an ephemeral in-memory list, attributed to the contributing
``org_id`` and carrying the validator verdict for the human review queue.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contributions")),
    )
    op.create_index(op.f("ix_contributions_status"), "contributions", ["status"])
    op.create_index(op.f("ix_contributions_org_id"), "contributions", ["org_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_contributions_org_id"), table_name="contributions")
    op.drop_index(op.f("ix_contributions_status"), table_name="contributions")
    op.drop_table("contributions")
