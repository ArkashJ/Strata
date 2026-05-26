"""create primitives sources concepts frameworks tables

Revision ID: 001
Revises:
Create Date: 2026-05-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "primitives",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="atomic_primitive"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("concept_slug", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", postgresql.JSONB(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("geo", postgresql.JSONB(), nullable=False),
        sa.Column("geo_perspective", sa.String(32), nullable=False, server_default="supply"),
        sa.Column("distribution_shape", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("delivery_mode", sa.String(32), nullable=False, server_default="n/a"),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_primitives")),
        sa.UniqueConstraint("slug", name=op.f("uq_primitives_slug")),
    )
    op.create_index(op.f("ix_primitives_concept_slug"), "primitives", ["concept_slug"])
    op.create_index(op.f("ix_primitives_as_of"), "primitives", ["as_of"])
    op.create_index("ix_primitives_unit_gin", "primitives", ["unit"], postgresql_using="gin")
    op.create_index("ix_primitives_geo_gin", "primitives", ["geo"], postgresql_using="gin")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("accessed", sa.Date(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint("slug", name=op.f("uq_sources_slug")),
    )
    op.create_index(op.f("ix_sources_snapshot_sha256"), "sources", ["snapshot_sha256"])

    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("analysis_lens", postgresql.JSONB(), nullable=False),
        sa.Column("modifiers", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("measurements", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("competing_concepts", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concepts")),
        sa.UniqueConstraint("slug", name=op.f("uq_concepts_slug")),
    )

    op.create_table(
        "frameworks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("method_family", sa.String(64), nullable=False),
        sa.Column("lens", sa.String(32), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("output_unit", postgresql.JSONB(), nullable=False),
        sa.Column("applicable_to", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("variants", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_frameworks")),
        sa.UniqueConstraint("slug", name=op.f("uq_frameworks_slug")),
    )
    op.create_index(op.f("ix_frameworks_lens"), "frameworks", ["lens"])


def downgrade() -> None:
    op.drop_table("frameworks")
    op.drop_table("concepts")
    op.drop_table("sources")
    op.drop_table("primitives")
