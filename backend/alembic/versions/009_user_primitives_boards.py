"""user_primitives + boards + board_items (strict org-scoped RLS)

Revision ID: 009
Revises: 008
Create Date: 2026-06-06

PR 1 — multi-tenant workspace (U4). Three durable, org-scoped tables that back
the per-user workspace:

- ``user_primitives`` — a tenant's private primitive store (the AtomicPrimitive
  payload as JSONB). ``visibility`` defaults to ``private``; ``(org_id, slug)`` is
  unique so a tenant can't shadow its own slug, while two tenants may both own the
  same slug.
- ``boards`` — saved dashboard layouts.
- ``board_items`` — the entries placed on a board (kind + ref + position).

All three are NEVER world-readable — unlike migration 008's dual-purpose
``tam_outputs`` policy, they get the STRICT 006-style closed policy
(``org_id = current_setting('app.org_id', true)`` only, no ``IS NULL`` clause), so
an anonymous session (``app.org_id`` unset → NULL) sees zero rows. ``FORCE`` so
even the table owner is subject.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- user_primitives ----------------------------------------------------
    op.create_table(
        "user_primitives",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_primitives")),
    )
    op.create_index(op.f("ix_user_primitives_org_id"), "user_primitives", ["org_id"])
    # One row per (org, slug): a tenant can't shadow its own slug, but two tenants
    # may each own the same slug.
    op.create_index(
        "uq_user_primitives_org_slug", "user_primitives", ["org_id", "slug"], unique=True
    )
    _enable_strict_rls(
        table="user_primitives",
        policy="user_primitives_tenant_isolation",
    )

    # --- boards -------------------------------------------------------------
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("layout", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_boards")),
    )
    op.create_index(op.f("ix_boards_org_id"), "boards", ["org_id"])
    _enable_strict_rls(table="boards", policy="boards_tenant_isolation")

    # --- board_items --------------------------------------------------------
    op.create_table(
        "board_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref", sa.String(255), nullable=False),
        sa.Column("position", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_items")),
        sa.ForeignKeyConstraint(
            ["board_id"],
            ["boards.id"],
            name=op.f("fk_board_items_board_id_boards"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_board_items_org_id"), "board_items", ["org_id"])
    op.create_index(op.f("ix_board_items_board_id"), "board_items", ["board_id"])
    _enable_strict_rls(table="board_items", policy="board_items_tenant_isolation")


def _enable_strict_rls(*, table: str, policy: str) -> None:
    """STRICT 006-style closed RLS: a session sees only rows for its
    ``current_setting('app.org_id')``, failing CLOSED when the var is unset
    (``current_setting(..., true)`` → NULL). Never world-readable."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {policy} ON {table}
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS board_items_tenant_isolation ON board_items")
    op.drop_index(op.f("ix_board_items_board_id"), table_name="board_items")
    op.drop_index(op.f("ix_board_items_org_id"), table_name="board_items")
    op.drop_table("board_items")

    op.execute("DROP POLICY IF EXISTS boards_tenant_isolation ON boards")
    op.drop_index(op.f("ix_boards_org_id"), table_name="boards")
    op.drop_table("boards")

    op.execute("DROP POLICY IF EXISTS user_primitives_tenant_isolation ON user_primitives")
    op.drop_index("uq_user_primitives_org_slug", table_name="user_primitives")
    op.drop_index(op.f("ix_user_primitives_org_id"), table_name="user_primitives")
    op.drop_table("user_primitives")
