"""substrate: api_keys, usage_events, and RLS tenant isolation

Revision ID: 003
Revises: 002
Create Date: 2026-05-30

Wave 3 (AC3.1/AC3.3/AC3.6): hashed API keys, persisted usage events, and a
Postgres row-level-security demonstration table (``tenant_data``) whose policy
isolates rows by ``current_setting('app.org_id')``. The session var is set from
the request Principal; ``FORCE ROW LEVEL SECURITY`` makes even the table owner
subject to the policy, so a cross-tenant read returns zero rows. Wave 5B's
private primitives reuse this exact org-scoped RLS pattern.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("scopes", sa.String(256), nullable=False, server_default="*"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("key_hash", name=op.f("pk_api_keys")),
    )
    op.create_index(op.f("ix_api_keys_org_id"), "api_keys", ["org_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("route", sa.String(256), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
    )
    op.create_index(op.f("ix_usage_events_org_id"), "usage_events", ["org_id"])

    # RLS demonstration / foundation table.
    op.create_table(
        "tenant_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.String(512), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_data")),
    )
    # Row-level security: a session sees only rows for its app.org_id, and may
    # only insert rows for it. FORCE so the table owner is subject too.
    # ``current_setting(..., true)`` returns NULL (not an error) when app.org_id
    # is unset; ``org_id = NULL`` is NULL → the row is invisible and inserts are
    # rejected. So an unset session var fails CLOSED (sees zero rows), not open.
    op.execute("ALTER TABLE tenant_data ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_data FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenant_data
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_data")
    op.drop_table("tenant_data")
    op.drop_index(op.f("ix_usage_events_org_id"), table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index(op.f("ix_api_keys_org_id"), table_name="api_keys")
    op.drop_table("api_keys")
