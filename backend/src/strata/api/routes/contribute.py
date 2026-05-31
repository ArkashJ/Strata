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

from fastapi import APIRouter, Depends
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import Principal, require_authenticated, require_principal
from strata.api.ratelimit import enforce_rate_limit
from strata.db.contributions import Contribution, list_contributions, record_contribution_safe
from strata.db.engine import get_session
from strata.models import Annotation, AtomicPrimitive

router = APIRouter(tags=["contribute"])

_PRINCIPAL = Depends(require_principal)
_SESSION = Depends(get_session)
# The review queue is operational data — require a real key.
_REVIEW_PRINCIPAL = Depends(require_authenticated)

# Tiers trustworthy enough to auto-accept; everything else needs human review.
_AUTO_ACCEPT_TIERS = frozenset({"regulator", "first_party"})

ContributionStatus = Literal["accepted", "needs_review", "rejected"]


class ContributionRequest(BaseModel):
    kind: Literal["atomic_primitive", "annotation"]
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
            return "rejected", [f"{e['loc']}: {e['msg']}" for e in exc.errors()][:8]
        # Annotations are pure commentary (E1) — never auto-publish into math.
        return "needs_review", ["annotation queued for review (never auto-applied to math)"]

    try:
        prim = TypeAdapter(AtomicPrimitive).validate_python(req.payload)
    except ValidationError as exc:
        return "rejected", [f"{e['loc']}: {e['msg']}" for e in exc.errors()][:8]

    # Read the tier from the VALIDATED object (a coerced enum), not the raw dict.
    tier = prim.source.tier.value
    if tier in _AUTO_ACCEPT_TIERS:
        return "accepted", [f"validated; {tier} tier auto-accepted"]
    return "needs_review", [f"{tier}-tier source requires human review before publish"]


@router.post("/contribute", response_model=ContributionResponse)
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


@router.get("/contributions", response_model=list[Contribution], summary="Review queue")
async def list_contributions_route(
    status: str | None = None,
    session: AsyncSession = _SESSION,
    principal: Principal = _REVIEW_PRINCIPAL,
) -> list[Contribution]:
    return await list_contributions(session, status=status)
