"""create tam_outputs table

Revision ID: 005
Revises: 004
Create Date: 2026-05-30

Durable storage for evaluated TAM artifacts so GET /tam/<hash> survives a
restart — the in-process FIFO cache 404s after eviction/restart, defeating the
"permanent, content-addressed, shareable" thesis. The full TAMOutput is stored
as JSONB keyed by its state_hash (Q38); equivalent states upsert.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tam_outputs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False),
        sa.Column("is_promoted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tam_outputs")),
        # UNIQUE on state_hash already creates the lookup index for /tam/<hash>.
        sa.UniqueConstraint("state_hash", name=op.f("uq_tam_outputs_state_hash")),
    )
    op.create_index(op.f("ix_tam_outputs_is_promoted"), "tam_outputs", ["is_promoted"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tam_outputs_is_promoted"), table_name="tam_outputs")
    op.drop_table("tam_outputs")
