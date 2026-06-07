"""add framework taxonomy columns (6 shapes + subframeworks reframe)

Revision ID: 011
Revises: 010
Create Date: 2026-06-07

The 6-shapes + subframeworks taxonomy (docs/plans/2026-06-07-frameworks-taxonomy-
reframe.md) adds two fields to ``Framework``: ``parent_lens_shape`` (NULL for a
canonical lens shape, else its lens's canonical slug) and ``realism_modifiers``
(empty for a canonical, else how the subframework specializes the shape). Stored
so ``Registry.from_db`` (prod) sees the taxonomy — without these columns every
framework reconstructs as a canonical and the validator gate fires on wrong data.

Existing rows take NULL parent + ``[]`` modifiers (i.e. read as canonical) until
the next ``strata db seed`` / STRATA_SEED_ON_BOOT re-seeds from YAML via upsert,
which populates the real values. No backfill here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "frameworks",
        sa.Column("parent_lens_shape", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "frameworks",
        sa.Column(
            "realism_modifiers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("frameworks", "realism_modifiers")
    op.drop_column("frameworks", "parent_lens_shape")
