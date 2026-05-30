"""create audit_events table

Revision ID: 002
Revises: 001
Create Date: 2026-05-30

Strata Live Track C: append-only audit log of user-visible actions
(resolve / recompute / promote) feeding GET /audit and the dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(256), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_ts"), "audit_events", ["ts"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_ts"), table_name="audit_events")
    op.drop_table("audit_events")
