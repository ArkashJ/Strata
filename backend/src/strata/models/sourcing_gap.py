"""Sourcing-gap model (Pillar B1) — measure the misses so we can fill them.

When a query, a report question, or a claim can't be answered from sourced data,
the answer today either falls to an honest "unsourced" banner or vanishes. A
``SourcingGap`` records that miss: *this market / role was asked for and we had
nothing sourced*. De-duplicated per workspace and counted (``hit_count``), the
queue ranks the most-demanded missing numbers — that is the connector-build
backlog, ordered by real demand rather than guesswork.

A gap is a demand signal, never a number: it never feeds the math (like a flag,
E1). It is the supply-side twin of ``FeedbackEvent`` — feedback says "this number
is wrong", a gap says "there is no number here yet".

Stored org-scoped (RLS) in ``sourcing_gaps`` (migration 017); surfaced via the
``list_sourcing_gaps`` MCP tool and ``strata gaps`` CLI (admin sees every org).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GapSource(StrEnum):
    """Where the miss was observed — so we know which surface surfaced demand."""

    RESOLVE_MISS = "resolve_miss"  # resolve_market found no curated concept
    REPORT_GAP = "report_gap"  # a report question had no sourced answer
    UNVERIFIABLE_CLAIM = "unverifiable_claim"  # verify_market_claim couldn't check
    MANUAL = "manual"  # an operator / agent logged it directly


class GapStatus(StrEnum):
    """Lifecycle. New gaps are ``open``; sourcing one flips it to ``sourced``."""

    OPEN = "open"
    SOURCED = "sourced"
    WONTFIX = "wontfix"


class SourcingGap(BaseModel):
    """One persisted sourcing-gap row (read shape).

    ``dedup_key`` is the normalized identity (query text or resource_target) the
    recorder collapses repeats onto, bumping ``hit_count`` instead of inserting a
    duplicate — so the queue counts demand. ``resource_target`` (e.g.
    ``bls:displacement-by-occupation``) names the connector/method that would fill
    the gap, when known.

    A resolve-side and a verify-side phrasing of the same market can land two
    rows (the key is the normalized query text and the two surfaces see
    different strings) — acceptable: both still rank as demand for the same
    missing number."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    created_at: datetime
    last_seen_at: datetime
    source: GapSource
    dedup_key: str
    query_text: str | None = None
    concept_slug: str | None = None
    role: str | None = None
    lens: str | None = None
    unit_hint: str | None = None
    resource_target: str | None = None
    hit_count: int = 1
    status: GapStatus = GapStatus.OPEN
    resolved_primitive_id: int | None = None
    note: str | None = None
