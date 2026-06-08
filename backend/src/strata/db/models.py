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
    UniqueConstraint,
    func,
    text,
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
    # Taxonomy (2026-06-07): a canonical lens shape ⇒ NULL parent + empty
    # modifiers; a subframework ⇒ parent = its lens's canonical slug + ≥1
    # realism modifier. Persisted so Registry.from_db (prod) sees the taxonomy.
    parent_lens_shape: Mapped[str | None] = mapped_column(String(128), nullable=True)
    realism_modifiers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
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


class ApiKeyRow(Base):
    """A self-serve API key (migration 003 table; lifecycle columns in 012).

    Keys are stored **hashed** (sha256) — the raw secret is shown ONCE at mint and
    never persisted. ``key_id`` is the public, non-secret handle the UI/API use to
    list and revoke a key; ``prefix`` is a masked fragment for human recognition.
    A key authenticates the hosted ``/mcp`` connector (and the REST API) as its
    ``org_id``. NOT under RLS — the auth path looks a key up by hash before any
    ``app.org_id`` is known, so management routes filter by ``org_id`` in SQL.
    """

    __tablename__ = "api_keys"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scopes: Mapped[str] = mapped_column(String(256), nullable=False, default="*")
    key_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    prefix: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class FeedbackEventRow(Base):
    """A flag against the tool: a bad assumption, failed query, wrong primitive,
    missing data, or general note (migration 014, Phase F).

    Org-scoped with the strict closed 006-style RLS policy — a session sees only
    its ``app.org_id`` rows. ``suggested_value`` is advisory JSON (e.g. a proposed
    corrected number) and is NEVER auto-applied to the math (E1). All reads/writes
    run inside ``org_session_scope(org_id)`` so the policy actually isolates.
    """

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The org-private ``user_primitives`` row an accepted correction produced
    # (migration 015). Same tenant, so the id is only meaningful under this
    # row's ``org_id``; no cross-RLS FK. NULL for every flag that never applied.
    resolved_primitive_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_feedback_events_org_status", "org_id", "status"),
        Index("ix_feedback_events_target", "target_type", "target_id"),
    )


class SourcingGapRow(Base):
    """A demand signal that sourced data was missing (migration 017, Pillar B1).

    Org-scoped with the same strict closed RLS as ``feedback_events`` — a session
    sees only its ``app.org_id`` rows (admin sees all via the additive policy).
    De-duplicated on ``(org_id, dedup_key)``: a repeat miss bumps ``hit_count`` +
    ``last_seen_at`` instead of inserting again, so the queue counts demand. A gap
    is a supply-side signal, never a number — it never feeds the math (E1).
    """

    __tablename__ = "sourcing_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(512), nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    concept_slug: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lens: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolved_primitive_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # The de-dup target: one row per (org, normalized miss). The recorder
        # upserts onto this, bumping hit_count rather than inserting a duplicate.
        UniqueConstraint("org_id", "dedup_key", name="uq_sourcing_gaps_org_dedup"),
        Index("ix_sourcing_gaps_org_status", "org_id", "status"),
        # Demand ranking: most-requested open gaps first within an org.
        Index("ix_sourcing_gaps_org_hits", "org_id", "hit_count"),
    )


class OAuthClientRow(Base):
    """A dynamically-registered OAuth client (RFC 7591 DCR), migration 013.

    claude.ai / ChatGPT register once per connector instance and reuse the
    returned ``client_id``. ``redirect_uris`` is the JSON array the client
    declared; ``/oauth/authorize`` later requires the incoming ``redirect_uri``
    to exact-match one of these (and pass the trusted-host allowlist). Like
    ``api_keys``, this table is NOT under RLS — DCR is pre-auth, so no
    ``app.org_id`` exists when the row is read.
    """

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    redirect_uris: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OAuthAuthCodeRow(Base):
    """A short-lived, single-use authorization code, migration 013.

    Minted by ``/oauth/authorize`` after a verified Clerk consent and exchanged
    once at ``/oauth/token``. Stored **hashed** (the raw code is only ever in the
    redirect URL). ``consumed_at`` is the single-use marker — a second exchange
    of the same code is rejected. Bound to ``{code_challenge, redirect_uri,
    client_id, resource, org_id}`` so the token inherits the exact grant. NOT
    under RLS — looked up by hash before an org scope is established.
    """

    __tablename__ = "oauth_auth_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(8), nullable=False, default="S256")
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope: Mapped[str] = mapped_column(String(256), nullable=False, default="*")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OAuthTokenRow(Base):
    """An issued OAuth access token (+ rotating refresh), migration 013.

    Opaque tokens, stored **hashed** (mirror ``api_keys``) so the RS auth path
    stays a fast hash lookup. ``resource`` is the bound RFC 8707 audience — the
    RS rejects a token whose ``resource`` != its own MCP URL (audience-confusion
    defense). ``refresh_hash`` rotates: ``/oauth/token`` refresh issues a new
    pair and sets ``revoked_at`` on the old row, so a reused refresh is rejected.
    NOT under RLS — looked up by hash before an org scope is established; the
    carried ``org_id`` then drives ``org_session_scope`` + RLS on data tables.
    """

    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    refresh_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope: Mapped[str] = mapped_column(String(256), nullable=False, default="*")
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_oauth_tokens_refresh_hash",
            "refresh_hash",
            unique=True,
            postgresql_where=text("refresh_hash IS NOT NULL"),
        ),
    )
