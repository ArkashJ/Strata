"""additive admin cross-org RLS policies (cross-tenant feedback governance)

Revision ID: 016
Revises: 015
Create Date: 2026-06-07

The closed tenant policies (migrations 014 ``feedback_events`` / 009
``user_primitives``) stay exactly as they are — a normal request still sees only
its ``app.org_id`` rows and still fails CLOSED when the var is unset. This adds a
SECOND *permissive* policy on each, gated on a separate ``app.is_admin = 'on'``
GUC. Postgres OR's permissive policies, so:

  - no GUC set            → tenant policy only  → own-org rows (unchanged)
  - app.is_admin = 'on'   → tenant OR admin     → every org's rows

The admin GUC is set only inside ``db.engine.admin_session_scope`` (transaction-
local, can't leak across pooled requests) and only after ``auth.is_admin`` has
gated the caller. This makes the cross-org bypass an explicit, opt-in, audited
GUC rather than a column-nullability accident that fails open (#99).

feedback_events gets admin SELECT (read every queue) + admin UPDATE (resolve a
flag cross-org). user_primitives gets admin SELECT only (read the org-private
primitive being promoted) — an admin never WRITES into another org's private
bank; promotion creates a SHARED-bank artifact instead.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # feedback_events: cross-org read + resolve for an admin session.
    op.execute(
        """
        CREATE POLICY feedback_events_admin_read ON feedback_events
        FOR SELECT
        USING (current_setting('app.is_admin', true) = 'on')
        """
    )
    op.execute(
        """
        CREATE POLICY feedback_events_admin_update ON feedback_events
        FOR UPDATE
        USING (current_setting('app.is_admin', true) = 'on')
        WITH CHECK (current_setting('app.is_admin', true) = 'on')
        """
    )
    # user_primitives: cross-org READ only (to read the correction being promoted).
    op.execute(
        """
        CREATE POLICY user_primitives_admin_read ON user_primitives
        FOR SELECT
        USING (current_setting('app.is_admin', true) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_primitives_admin_read ON user_primitives")
    op.execute("DROP POLICY IF EXISTS feedback_events_admin_update ON feedback_events")
    op.execute("DROP POLICY IF EXISTS feedback_events_admin_read ON feedback_events")
