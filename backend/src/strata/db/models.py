"""SQLAlchemy ORM models — Postgres mirror of the YAML data bank.

Tables mirror the Pydantic schemas in strata.models but are optimized for
query performance with GIN indexes on JSONB columns and B-tree indexes on
slug lookups.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

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
    unit: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    geo: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geo_perspective: Mapped[str] = mapped_column(String(32), nullable=False, default="supply")
    distribution_shape: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="n/a")
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    analysis_lens: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    modifiers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    measurements: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    competing_concepts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEventRow(Base):
    """Append-only audit log (Strata Live Track C).

    One row per user-visible action (resolve / recompute / promote). ``actor``
    is the Clerk user id or ``'anon'`` when unauthenticated; ``meta`` carries
    free-form JSON context (query text, hash, etc.).
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True, default="anon")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class FrameworkRow(Base):
    """Framework record in Postgres."""

    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    method_family: Mapped[str] = mapped_column(String(64), nullable=False)
    lens: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    inputs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    output_unit: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    applicable_to: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    variants: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContributionRow(Base):
    """Persisted community contribution proposal (Wave 4 / moat intake)."""

    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TamOutputRow(Base):
    """Persisted TAM artifact so ``GET /tam/<hash>`` survives a restart.

    The whole point of Strata is a *permanent, content-addressed* TAM you can
    paste into a memo — an in-process FIFO cache 404s after eviction/restart,
    which defeats the thesis. The full ``TAMOutput`` is stored as JSONB keyed by
    its ``state_hash`` (Q38); equivalent states collide, so a re-build upserts.
    """

    __tablename__ = "tam_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # unique=True already creates the lookup index — no separate index needed.
    state_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_promoted: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyRow(Base):
    """Org-scoped portfolio company — a cheap pointer at a shared MARKET concept.

    A company does not have a TAM; the market it competes in does (spec §3). So
    the expensive sourced work lives at the concept level and this row just links
    to it (``market_concept_slug``) plus caches the resolved ``tam_value``.
    Idempotent import is enforced by ``UNIQUE (org_id, domain)``. RLS mirrors
    migration 003 ``tenant_data`` — a session sees only its ``app.org_id``.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    vertical: Mapped[str | None] = mapped_column(String(128), nullable=True)
    market_concept_slug: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unsized", index=True)
    overrides: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tam_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_analyst_input: Mapped[bool] = mapped_column(default=False, nullable=False)
    sized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("uq_companies_org_domain", "org_id", "domain", unique=True),)
