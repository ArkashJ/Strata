"""create companies table (portfolio sizing, P1)

Revision ID: 006
Revises: 005
Create Date: 2026-05-31

Org-scoped portfolio company pointers (spec §4). Ships behind
``STRATA_PORTFOLIO_ENABLED`` (F6) — the table is created regardless (safe), but
write surfaces refuse until the flag is on. RLS mirrors migration 003
``tenant_data``: a session sees only rows for its ``current_setting('app.org_id')``,
failing CLOSED when the var is unset. The local/default-org CLI path runs
outside RLS (in-memory / JSON store), so this policy only governs the hosted
multi-tenant HTTP path.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, server_default=""),
        sa.Column("vertical", sa.String(128), nullable=True),
        sa.Column("market_concept_slug", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="unsized"),
        sa.Column("overrides", postgresql.JSONB(), nullable=True),
        sa.Column("tam_value", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("has_analyst_input", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index(op.f("ix_companies_org_id"), "companies", ["org_id"])
    op.create_index(op.f("ix_companies_status"), "companies", ["status"])
    op.create_index(op.f("ix_companies_market_concept_slug"), "companies", ["market_concept_slug"])
    # Import idempotency: one row per (org, domain).
    op.create_index("uq_companies_org_domain", "companies", ["org_id", "domain"], unique=True)

    # Row-level security — same pattern as migration 003 tenant_data. Fails
    # CLOSED when app.org_id is unset (current_setting(..., true) → NULL).
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY companies_tenant_isolation ON companies
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS companies_tenant_isolation ON companies")
    op.drop_index("uq_companies_org_domain", table_name="companies")
    op.drop_index(op.f("ix_companies_market_concept_slug"), table_name="companies")
    op.drop_index(op.f("ix_companies_status"), table_name="companies")
    op.drop_index(op.f("ix_companies_org_id"), table_name="companies")
    op.drop_table("companies")
