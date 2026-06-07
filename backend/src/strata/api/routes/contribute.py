"""Community contribution intake (Wave 4 / AC4.3).

Accepts a PR-shaped proposed primitive or annotation, runs the validator
(Pydantic structural layer + tier gate), and returns accept / needs-review /
reject with reasons. Low-tier sources are NEVER auto-published — they land in
``needs_review`` for a human, honoring the "no LLM-projected primitives becoming
citable" rule.
"""

from __future__ import annotations

from threading import Lock
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import Principal, require_authenticated, require_principal
from strata.api.deps import get_registry
from strata.api.ratelimit import enforce_rate_limit
from strata.api.responses import (
    RATE_LIMITED,
    UNAUTHORIZED,
    error,
    format_validation_errors,
    merge,
)
from strata.db.contributions import Contribution, list_contributions, record_contribution_safe
from strata.db.engine import get_session
from strata.models import Annotation, AtomicPrimitive, Concept
from strata.registry import Registry

router = APIRouter(tags=["contribute"])

_PRINCIPAL = Depends(require_principal)
_SESSION = Depends(get_session)
_REGISTRY = Depends(get_registry)
# The review queue is operational data — require a real key.
_REVIEW_PRINCIPAL = Depends(require_authenticated)

# Tiers trustworthy enough to auto-accept; everything else needs human review.
_AUTO_ACCEPT_TIERS = frozenset({"regulator", "first_party"})

ContributionStatus = Literal["accepted", "needs_review", "rejected"]


class ContributionRequest(BaseModel):
    kind: Literal["atomic_primitive", "annotation", "concept"]
    payload: dict[str, Any]


class ContributionResponse(BaseModel):
    status: ContributionStatus
    reasons: list[str]
    contribution_id: int | None = None


class _ContributionStore:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._lock = Lock()

    def add(self, org_id: str, req: ContributionRequest, status: str) -> int:
        with self._lock:
            cid = len(self._items)
            self._items.append({"id": cid, "org_id": org_id, "kind": req.kind, "status": status})
            return cid

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()


_store = _ContributionStore()


def get_contribution_store() -> _ContributionStore:
    return _store


def _validate(req: ContributionRequest) -> tuple[ContributionStatus, list[str]]:
    """Structural (L1) validation + tier gate. Cross-record referential checks
    (concept_slug exists, slug uniqueness) run later at `strata promote` time —
    this intake never writes to the data bank, only routes the review queue."""
    if req.kind == "annotation":
        try:
            TypeAdapter(Annotation).validate_python(req.payload)
        except ValidationError as exc:
            return "rejected", format_validation_errors(exc)
        # Annotations are pure commentary (E1) — never auto-publish into math.
        return "needs_review", ["annotation queued for review (never auto-applied to math)"]

    if req.kind == "concept":
        try:
            Concept.model_validate(req.payload)
        except ValidationError as exc:
            return "rejected", format_validation_errors(exc)
        # A concept is a curated identity object, not a sourced number — there's
        # no tier to auto-accept on. Promotion to the public bank ALWAYS goes
        # through human review (flow 39: validator-gated, never a direct write).
        return "needs_review", ["concept queued for human review before public promotion"]

    try:
        prim = TypeAdapter(AtomicPrimitive).validate_python(req.payload)
    except ValidationError as exc:
        return "rejected", format_validation_errors(exc)

    # Read the tier from the VALIDATED object (a coerced enum), not the raw dict.
    tier = prim.source.tier.value
    if tier in _AUTO_ACCEPT_TIERS:
        return "accepted", [f"validated; {tier} tier auto-accepted"]
    return "needs_review", [f"{tier}-tier source requires human review before publish"]


@router.post(
    "/contribute",
    response_model=ContributionResponse,
    summary="Submit a primitive or annotation",
    description="Validate and queue a new primitive or annotation for review.",
    responses=merge(UNAUTHORIZED, RATE_LIMITED),
)
async def contribute(
    req: ContributionRequest, principal: Principal = _PRINCIPAL
) -> ContributionResponse:
    enforce_rate_limit(principal.org_id)
    status, reasons = _validate(req)
    cid: int | None = None
    if status != "rejected":
        cid = get_contribution_store().add(principal.org_id, req, status)
        # Persist to the durable review queue (best-effort; never breaks the
        # response). Falls back to the in-memory id when no DB is reachable.
        db_id = await record_contribution_safe(
            principal.org_id, req.kind, status, reasons, req.payload
        )
        if db_id is not None:
            cid = db_id
    return ContributionResponse(status=status, reasons=reasons, contribution_id=cid)


class ConceptPromoteRequest(BaseModel):
    """Promote a proposed concept into the public bank via review (flow 39)."""

    payload: dict[str, Any]


class IntersectionPromoteRequest(BaseModel):
    """Auto-draft + queue the intersection of two existing public concepts."""

    concept_a: str
    concept_b: str


@router.post(
    "/concepts/promote",
    response_model=ContributionResponse,
    summary="Promote a concept to the review queue",
    description=(
        "Validate a proposed concept and queue it for human review. A concept is "
        "NEVER auto-published — promotion to the public bank always goes through "
        "the review gate (flow 39). Concepts have no source tier to auto-accept on."
    ),
    responses=merge(UNAUTHORIZED, RATE_LIMITED),
)
async def promote_concept(
    req: ConceptPromoteRequest, principal: Principal = _PRINCIPAL
) -> ContributionResponse:
    enforce_rate_limit(principal.org_id)
    inner = ContributionRequest(kind="concept", payload=req.payload)
    status, reasons = _validate(inner)
    cid: int | None = None
    if status != "rejected":
        cid = get_contribution_store().add(principal.org_id, inner, status)
        db_id = await record_contribution_safe(
            principal.org_id, "concept", status, reasons, req.payload
        )
        if db_id is not None:
            cid = db_id
    return ContributionResponse(status=status, reasons=reasons, contribution_id=cid)


@router.post(
    "/concepts/intersect",
    response_model=ContributionResponse,
    summary="Auto-promote the intersection of two concepts (to review)",
    description=(
        "Detect the scope intersection of two EXISTING public concepts and queue "
        "the drafted intersection concept for human review. 'Auto' = auto-detect "
        "+ auto-draft; it still NEVER bypasses review (flow 39). 422 when the two "
        "concepts share no scope dimension (no defensible intersection)."
    ),
    responses=merge(UNAUTHORIZED, RATE_LIMITED, error(422, "No shared scope to intersect.")),
)
async def intersect_concepts(
    req: IntersectionPromoteRequest,
    principal: Principal = _PRINCIPAL,
    registry: Registry = _REGISTRY,
) -> ContributionResponse:
    enforce_rate_limit(principal.org_id)
    from strata.api.concept_promotion import intersection_candidate

    draft = intersection_candidate(registry, req.concept_a, req.concept_b)
    if draft is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{req.concept_a!r} and {req.concept_b!r} share no scope dimension "
                "(or one is unknown) — no defensible intersection to promote."
            ),
        )
    payload = draft.model_dump(mode="json")
    inner = ContributionRequest(kind="concept", payload=payload)
    status, reasons = _validate(inner)
    reasons = [f"auto-drafted intersection {draft.slug}", *reasons]
    cid: int | None = None
    if status != "rejected":
        cid = get_contribution_store().add(principal.org_id, inner, status)
        db_id = await record_contribution_safe(
            principal.org_id, "concept", status, reasons, payload
        )
        if db_id is not None:
            cid = db_id
    return ContributionResponse(status=status, reasons=reasons, contribution_id=cid)


@router.get(
    "/contributions",
    response_model=list[Contribution],
    summary="Review queue",
    description="List pending contributions queued for human review.",
    responses=UNAUTHORIZED,
)
async def list_contributions_route(
    status: ContributionStatus | None = None,
    session: AsyncSession = _SESSION,
    principal: Principal = _REVIEW_PRINCIPAL,
) -> list[Contribution]:
    return await list_contributions(session, status=status)
