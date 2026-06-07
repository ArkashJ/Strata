"""create feedback_events table (assumption-flagging + feedback loop, Phase F)

Revision ID: 014
Revises: 013
Create Date: 2026-06-07

The improvement flywheel: a user / agent flags a bad assumption, a failed query,
a wrong primitive, or missing data, and the team triages it. Rows are org-scoped
and carry the strict closed RLS policy (mirrors migration 006 ``companies`` /
009 ``user_primitives``) — a session sees only its ``current_setting('app.org_id')``
rows, failing CLOSED when the var is unset. Indexes on (org_id, status) power the
triage queue; (target_type, target_id) powers "show all flags on this TAM".
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(256), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("suggested_value", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_events")),
    )
    op.create_index("ix_feedback_events_org_status", "feedback_events", ["org_id", "status"])
    op.create_index("ix_feedback_events_target", "feedback_events", ["target_type", "target_id"])

    # Row-level security — same closed pattern as migration 006/009. Fails CLOSED
    # when app.org_id is unset (current_setting(..., true) → NULL → no rows).
    op.execute("ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE feedback_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY feedback_events_tenant_isolation ON feedback_events
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS feedback_events_tenant_isolation ON feedback_events")
    op.drop_index("ix_feedback_events_target", table_name="feedback_events")
    op.drop_index("ix_feedback_events_org_status", table_name="feedback_events")
    op.drop_table("feedback_events")
