"""add scope columns to primitives and concepts (rigorous market definition, sub-project 1)

Revision ID: 007
Revises: 006
Create Date: 2026-05-31

A ``MarketScope`` is now first-class on both ``Concept`` (declared) and
``AtomicPrimitive`` (true scope). Stored as nullable JSONB so the PG-backed
registry (``Registry.from_db``) round-trips it; rows seeded before scope landed
carry NULL and reconstruct as an empty scope. No backfill here — re-seeding from
YAML (``strata db seed`` / STRATA_SEED_ON_BOOT) populates the columns via the
upsert.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("primitives", sa.Column("scope", postgresql.JSONB(), nullable=True))
    op.add_column("concepts", sa.Column("scope", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("concepts", "scope")
    op.drop_column("primitives", "scope")
