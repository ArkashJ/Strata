"""org-scope tam_outputs (dual-purpose RLS) + audit_events (strict RLS)

Revision ID: 008
Revises: 007
Create Date: 2026-06-06

PR 1 — multi-tenant workspace (KTD-1/KTD-2). ``tam_outputs`` serves two masters:
anonymous content-addressed permalinks (``org_id IS NULL``, world-readable) and
tenant saves (``org_id = <tenant>``, isolated). Its policy therefore admits BOTH
via ``org_id IS NULL OR org_id = current_setting('app.org_id', true)`` — the
``OR org_id IS NULL`` clause is the permalink-preserving difference from migration
006's closed policy and is the single load-bearing line in the PR.

``UNIQUE(state_hash)`` is replaced by two partial unique indexes so the same
content hash can exist once as a global permalink AND once per tenant-save.

``audit_events`` is never world-readable: it gets the STRICT 006-style closed
policy (``org_id = current_setting('app.org_id', true)`` only, no IS NULL clause),
so an anonymous session sees zero rows (fails closed).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tam_outputs: new org columns ---------------------------------------
    op.add_column("tam_outputs", sa.Column("org_id", sa.String(128), nullable=True))
    op.add_column("tam_outputs", sa.Column("created_by", sa.String(128), nullable=True))
    op.add_column("tam_outputs", sa.Column("title", sa.Text(), nullable=True))
    op.add_column(
        "tam_outputs",
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_tam_outputs_org_id"), "tam_outputs", ["org_id"])

    # --- tam_outputs: split the single UNIQUE(state_hash) into partial indexes
    # KTD-2: one global permalink per hash, plus one save per (org, hash).
    op.drop_constraint("uq_tam_outputs_state_hash", "tam_outputs", type_="unique")
    op.create_index(
        "uq_tam_outputs_state_hash_public",
        "tam_outputs",
        ["state_hash"],
        unique=True,
        postgresql_where=sa.text("org_id IS NULL"),
    )
    op.create_index(
        "uq_tam_outputs_state_hash_org",
        "tam_outputs",
        ["org_id", "state_hash"],
        unique=True,
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )

    # --- tam_outputs: dual-purpose RLS (KTD-1) ------------------------------
    # FORCE so even the table owner is subject. The ``OR org_id IS NULL`` clause
    # keeps anonymous content-addressed permalinks world-readable/writable while
    # a tenant session sees globals PLUS its own and never another tenant's.
    op.execute("ALTER TABLE tam_outputs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tam_outputs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tam_outputs_dual_purpose ON tam_outputs
        USING (org_id IS NULL OR org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id IS NULL OR org_id = current_setting('app.org_id', true))
        """
    )

    # --- audit_events: org_id + STRICT closed RLS (006-style) ---------------
    op.add_column("audit_events", sa.Column("org_id", sa.String(128), nullable=True))
    op.create_index(op.f("ix_audit_events_org_id"), "audit_events", ["org_id"])
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_isolation ON audit_events
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )


def downgrade() -> None:
    # --- audit_events -------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_audit_events_org_id"), table_name="audit_events")
    op.drop_column("audit_events", "org_id")

    # --- tam_outputs --------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS tam_outputs_dual_purpose ON tam_outputs")
    op.execute("ALTER TABLE tam_outputs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tam_outputs DISABLE ROW LEVEL SECURITY")

    op.drop_index("uq_tam_outputs_state_hash_org", table_name="tam_outputs")
    op.drop_index("uq_tam_outputs_state_hash_public", table_name="tam_outputs")
    op.create_unique_constraint("uq_tam_outputs_state_hash", "tam_outputs", ["state_hash"])

    op.drop_index(op.f("ix_tam_outputs_org_id"), table_name="tam_outputs")
    op.drop_column("tam_outputs", "is_saved")
    op.drop_column("tam_outputs", "title")
    op.drop_column("tam_outputs", "created_by")
    op.drop_column("tam_outputs", "org_id")
