"""api_keys lifecycle columns (mintable, revocable, attributable)

Revision ID: 012
Revises: 011
Create Date: 2026-06-07

Migration 003 created ``api_keys`` (key_hash PK, org_id, scopes, created_at) as
forward scaffolding — the in-process store seeded from an env var was the active
path and keys could not be minted from the product. This makes the table the
real source of truth for a self-serve key, so a VC can generate a key on the
website and connect Strata to Claude over the hosted ``/mcp`` connector.

Added columns (all nullable so the few env-seeded rows tolerate the upgrade):
- ``key_id``     — public, non-secret identifier the UI/API references a key by
                   (the raw secret is shown ONCE at mint and never stored).
- ``label``      — human name ("Claude Desktop", "research laptop").
- ``prefix``     — masked display fragment ("strata_sk_live_a1b…z9k0").
- ``created_by`` — the Clerk subject that minted it (attribution).
- ``last_used_at``— best-effort last authentication, for staleness review.
- ``revoked_at`` — set on revoke; a revoked key never resolves a principal.

The table is deliberately NOT under RLS: the auth path looks a key up by hash
*before* an org is known, so it must be readable outside any ``app.org_id``
scope. Management routes filter by ``org_id`` in SQL instead.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("key_id", sa.String(40), nullable=True))
    op.add_column("api_keys", sa.Column("label", sa.Text(), nullable=True))
    op.add_column("api_keys", sa.Column("prefix", sa.String(48), nullable=True))
    op.add_column("api_keys", sa.Column("created_by", sa.String(128), nullable=True))
    op.add_column("api_keys", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_keys", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    # Partial unique: every minted key carries a key_id; legacy env-seeded rows
    # (key_id NULL) are exempt so the index can be created without backfill.
    op.create_index(
        "uq_api_keys_key_id",
        "api_keys",
        ["key_id"],
        unique=True,
        postgresql_where=sa.text("key_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_api_keys_key_id", table_name="api_keys")
    op.drop_column("api_keys", "revoked_at")
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "created_by")
    op.drop_column("api_keys", "prefix")
    op.drop_column("api_keys", "label")
    op.drop_column("api_keys", "key_id")
