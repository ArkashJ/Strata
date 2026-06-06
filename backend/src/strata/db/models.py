"""SQLAlchemy ORM models — Postgres mirror of the YAML data bank.

Tables mirror the Pydantic schemas in strata.models but are optimized for
query performance with GIN indexes on JSONB columns and B-tree indexes on
slug lookups.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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
    # Sub-project 1 — the primitive's MarketScope (nullable: rows seeded before
    # scope landed carry NULL → reconstructed as an empty scope).
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
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
    # Sub-project 1 — the concept's declared MarketScope (nullable: rows seeded
    # before scope landed carry NULL → reconstructed as an empty scope).
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEventRow(Base):
    """Append-only audit log (Strata Live Track C).

    One row per user-visible action (resolve / recompute / promote). ``actor``
    is the Clerk user id or ``'anon'`` when unauthenticated; ``meta`` carries
    free-form JSON context (query text, hash, etc.). ``org_id`` (migration 008,
    PR 1) is the tenant the event belongs to; the table's strict closed RLS
    policy keys on it, so an anonymous event has no persisted home.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
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

    PR 1 (migration 008) makes this table dual-purpose: ``org_id IS NULL`` rows
    are anonymous world-readable permalinks, ``org_id = <tenant>`` rows are a
    tenant's saved research (RLS-isolated). The old single ``UNIQUE(state_hash)``
    is replaced by two PARTIAL unique indexes (KTD-2) — one global per hash, one
    per ``(org_id, state_hash)`` — so the SAME content hash can exist once as a
    permalink AND once per tenant-save. Hence ``unique=True`` is dropped here.
    """

    __tablename__ = "tam_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Uniqueness is enforced by the two partial indexes in migration 008
    # (uq_tam_outputs_state_hash_public / _org), NOT a column-level constraint.
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # NULL → anonymous global permalink; set → a tenant's saved row (RLS-scoped).
    org_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_promoted: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserPrimitiveRow(Base):
    """A tenant's PRIVATE primitive store (migration 009, PR 1 / U6).

    The full ``AtomicPrimitive`` is stored as JSONB in ``payload`` so a tenant
    can keep its own numbers without touching the shared seed bank. ``org_id`` is
    NOT NULL and the table carries the STRICT 006-style closed RLS policy — never
    world-readable — so a session sees only its own ``app.org_id`` rows.
    ``(org_id, slug)`` is unique: a tenant can't shadow its own slug, while two
    tenants may each own the same slug. Server forces ``visibility='private'``;
    going public is only via the ``/contribute`` review queue, never a direct
    write here (honesty fence, KTD-5).
    """

    __tablename__ = "user_primitives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("uq_user_primitives_org_slug", "org_id", "slug", unique=True),)


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
