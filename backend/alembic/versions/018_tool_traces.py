"""create tool_traces and trace_sessions tables (MCP trace-capture substrate)

Revision ID: 018
Revises: 017
Create Date: 2026-06-08

Captures every MCP tool call that passes through ``_call_tool`` (fire-and-forget,
gated by ``STRATA_TRACE_CAPTURE``) and groups them into sessions so the replay
harness can detect silent regressions by re-running a captured sequence and
comparing ``result_sha256``.

Same closed RLS as 017 (own-org only, fails CLOSED when ``app.org_id`` is unset)
PLUS the additive admin SELECT policy (migration 016 pattern) so a cross-org
admin session can read traces for forensics / governance without relaxing tenant
isolation.  The feature is OFF by default (``trace_capture_enabled=False``) so
the tables exist silently until an operator opts in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── tool_traces ────────────────────────────────────────────────────────
    # One row per dispatched MCP tool call. ``session_id`` is nullable: a call
    # with no grouping header still lands here (an ungrouped call is better than
    # a dropped one). ``result_sha256`` is the replay regression signal.
    op.create_table(
        "tool_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("tool", sa.String(128), nullable=False),
        sa.Column("args", postgresql.JSONB(), nullable=False),
        sa.Column("args_truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("result_truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_traces")),
    )
    op.create_index(
        "ix_tool_traces_org_session_seq", "tool_traces", ["org_id", "session_id", "seq"]
    )
    op.create_index("ix_tool_traces_org_created_at", "tool_traces", ["org_id", "created_at"])
    op.create_index("ix_tool_traces_org_status", "tool_traces", ["org_id", "status"])

    # Closed tenant RLS + additive admin SELECT (017 pattern verbatim).
    op.execute("ALTER TABLE tool_traces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_traces FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tool_traces_tenant_isolation ON tool_traces
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )
    op.execute(
        """
        CREATE POLICY tool_traces_admin_read ON tool_traces
        FOR SELECT
        USING (current_setting('app.is_admin', true) = 'on')
        """
    )

    # ── trace_sessions ─────────────────────────────────────────────────────
    # One row per (org_id, session_id) pair. ``call_count`` is bumped atomically
    # by the recorder so replay has an accurate count. ``reasoning`` / ``outcome``
    # are agent-submitted — the structural context the server can't observe.
    op.create_table(
        "trace_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trace_sessions")),
        sa.UniqueConstraint("org_id", "session_id", name="uq_trace_sessions_org_session"),
    )
    op.create_index("ix_trace_sessions_org_last_seen", "trace_sessions", ["org_id", "last_seen_at"])

    # Closed tenant RLS + additive admin SELECT (017 pattern verbatim).
    op.execute("ALTER TABLE trace_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE trace_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY trace_sessions_tenant_isolation ON trace_sessions
        USING (org_id = current_setting('app.org_id', true))
        WITH CHECK (org_id = current_setting('app.org_id', true))
        """
    )
    op.execute(
        """
        CREATE POLICY trace_sessions_admin_read ON trace_sessions
        FOR SELECT
        USING (current_setting('app.is_admin', true) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS trace_sessions_admin_read ON trace_sessions")
    op.execute("DROP POLICY IF EXISTS trace_sessions_tenant_isolation ON trace_sessions")
    op.drop_index("ix_trace_sessions_org_last_seen", table_name="trace_sessions")
    op.drop_table("trace_sessions")

    op.execute("DROP POLICY IF EXISTS tool_traces_admin_read ON tool_traces")
    op.execute("DROP POLICY IF EXISTS tool_traces_tenant_isolation ON tool_traces")
    op.drop_index("ix_tool_traces_org_status", table_name="tool_traces")
    op.drop_index("ix_tool_traces_org_created_at", table_name="tool_traces")
    op.drop_index("ix_tool_traces_org_session_seq", table_name="tool_traces")
    op.drop_table("tool_traces")
