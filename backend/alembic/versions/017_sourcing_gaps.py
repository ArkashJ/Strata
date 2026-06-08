"""create sourcing_gaps table (demand-ranked missing-data queue, Pillar B1)

Revision ID: 017
Revises: 016
Create Date: 2026-06-07

The supply-side twin of feedback_events: when a query / report question / claim
can't be answered from sourced data, a gap is recorded so the miss becomes a
ranked, fillable backlog instead of vanishing. De-duplicated on
(org_id, dedup_key) so a repeat miss bumps hit_count (demand) rather than
inserting a duplicate.

Same closed RLS as 014/009 (own-org only, fails CLOSED when app.org_id is unset)
PLUS the additive admin SELECT policy (migration 016 pattern) so the cross-org
admin queue can rank demand platform-wide.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sourcing_gaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("dedup_key", sa.String(512), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("concept_slug", sa.String(256), nullable=True),
        sa.Column("role", sa.String(128), nullable=True),
        sa.Column("lens", sa.String(64), nullable=True),
        sa.Column("unit_hint", sa.String(128), nullable=True),
        sa.Column("resource_target", sa.String(256), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("resolved_primitive_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sourcing_gaps")),
        sa.UniqueConstraint("org_id", "dedup_key", name="uq_sourcing_gaps_org_dedup"),
    )
    op.create_index("ix_sourcing_gaps_org_status", "sourcing_gaps", ["org_id", "status"])
    op.create_index("ix_sourcing_gaps_org_hits", "sourcing_gaps", ["org_id", "hit_count"])

    # Closed tenant RLS (fails CLOSED when app.org_id is unset) + additive admin
    # SELECT (migration 016 pattern) so the cross-org demand queue can rank.
    op.execute("ALTER TABLE sourcing_gaps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sourcing_gaps FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY sourcing_gaps_tenant_isolation ON sourcing_gaps
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )
    op.execute(
        """
        CREATE POLICY sourcing_gaps_admin_read ON sourcing_gaps
        FOR SELECT
        USING (current_setting('app.is_admin', true) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS sourcing_gaps_admin_read ON sourcing_gaps")
    op.execute("DROP POLICY IF EXISTS sourcing_gaps_tenant_isolation ON sourcing_gaps")
    op.drop_index("ix_sourcing_gaps_org_hits", table_name="sourcing_gaps")
    op.drop_index("ix_sourcing_gaps_org_status", table_name="sourcing_gaps")
    op.drop_table("sourcing_gaps")
