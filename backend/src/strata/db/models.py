"""SQLAlchemy ORM models — Postgres mirror of the YAML data bank.

Tables mirror the Pydantic schemas in strata.models but are optimized for
query performance with GIN indexes on JSONB columns and B-tree indexes on
slug lookups.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from strata.db.base import Base


class PrimitiveRow(Base):
    """Atomic primitive stored in Postgres.

    The ``unit``, ``geo``, and ``source`` fields are stored as JSONB
    to avoid over-normalizing the schema at this stage. GIN indexes
    make them queryable.
    """

    __tablename__ = "primitives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="atomic_primitive")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    concept_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[dict] = mapped_column(JSONB, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    geo: Mapped[dict] = mapped_column(JSONB, nullable=False)
    geo_perspective: Mapped[str] = mapped_column(String(32), nullable=False, default="supply")
    distribution_shape: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="n/a")
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_primitives_source_tier", source["tier"].as_string()),
        Index("ix_primitives_unit_gin", unit, postgresql_using="gin"),
        Index("ix_primitives_geo_gin", geo, postgresql_using="gin"),
        Index("ix_primitives_as_of", as_of),
    )


class SourceRow(Base):
    """Source registry record in Postgres."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    accessed: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConceptRow(Base):
    """Concept record in Postgres."""

    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_lens: Mapped[dict] = mapped_column(JSONB, nullable=False)
    modifiers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    measurements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    competing_concepts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FrameworkRow(Base):
    """Framework record in Postgres."""

    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    method_family: Mapped[str] = mapped_column(String(64), nullable=False)
    lens: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    inputs: Mapped[list] = mapped_column(JSONB, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    output_unit: Mapped[dict] = mapped_column(JSONB, nullable=False)
    applicable_to: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    variants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
