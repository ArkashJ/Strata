"""OAuth 2.1 Authorization Server tables (hosted-MCP web connectors)

Revision ID: 013
Revises: 012
Create Date: 2026-06-07

Co-hosts an OAuth 2.1 AS with the existing Resource Server (``/mcp/``) so the
claude.ai web and ChatGPT "Add custom connector" UIs — which have no static
``Authorization`` header field and authenticate ONLY via OAuth — can connect in
one click. Identity reuses Clerk; the issued opaque access token maps to the
same ``org_id`` the API-key + RLS path uses.

Three tables, all deliberately **NOT under RLS** (mirror ``api_keys``, migration
003/012): the auth path looks a code/token up by *hash* before any ``app.org_id``
is known, so the rows must be readable outside any org scope. Org isolation is
enforced by (a) the token row carrying ``org_id``, (b) the resolved principal
then driving ``org_session_scope`` + RLS on the actual data tables, and (c) the
RFC 8707 audience check at the RS.

- ``oauth_clients``     — RFC 7591 DCR: client_id + declared redirect_uris.
- ``oauth_auth_codes``  — short-lived single-use codes (hashed), bound to
                          {code_challenge, redirect_uri, client_id, resource, org_id}.
- ``oauth_tokens``      — opaque access tokens (hashed) + rotating refresh.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column("redirect_uris", postgresql.JSONB(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "oauth_auth_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("code_challenge_method", sa.String(8), nullable=False, server_default="S256"),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("scope", sa.String(256), nullable=False, server_default="*"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_oauth_auth_codes_client_id", "oauth_auth_codes", ["client_id"])
    op.create_index("ix_oauth_auth_codes_org_id", "oauth_auth_codes", ["org_id"])

    op.create_table(
        "oauth_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("refresh_hash", sa.String(64), nullable=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("scope", sa.String(256), nullable=False, server_default="*"),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_oauth_tokens_org_id", "oauth_tokens", ["org_id"])
    # Partial unique: a non-NULL refresh_hash is unique (rotation), but many rows
    # may carry NULL (access tokens issued without a live refresh).
    op.create_index(
        "uq_oauth_tokens_refresh_hash",
        "oauth_tokens",
        ["refresh_hash"],
        unique=True,
        postgresql_where=sa.text("refresh_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_oauth_tokens_refresh_hash", table_name="oauth_tokens")
    op.drop_index("ix_oauth_tokens_org_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_index("ix_oauth_auth_codes_org_id", table_name="oauth_auth_codes")
    op.drop_index("ix_oauth_auth_codes_client_id", table_name="oauth_auth_codes")
    op.drop_table("oauth_auth_codes")
    op.drop_table("oauth_clients")
