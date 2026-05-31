"""Signal routes — read-only prediction-market signals (T1).

These are the ``prediction_market`` primitives quarantined to ``data/signals/``
(Q20). They are **never** consumed by a framework and never feed a TAM — they are
a separate, honestly-labelled surface: live event probabilities (Kalshi) that a
partner can read alongside a sized market. ``registry.signals`` already holds
them; this exposes them read-only. No write path, no evaluation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.models import AtomicPrimitive
from strata.registry import Registry

router = APIRouter(prefix="/signals", tags=["signals"])

_REG = Depends(get_registry)


class SignalSummary(BaseModel):
    slug: str
    name: str
    concept_slug: str
    value: float
    unit_dimension: str
    as_of: str
    source_url: str
    source_tier: str
    snapshot_sha256: str
    uncertainty_low: float | None
    uncertainty_high: float | None
    uncertainty_basis: str | None


def _summary(s: AtomicPrimitive) -> SignalSummary:
    unc = s.uncertainty
    return SignalSummary(
        slug=s.slug,
        name=s.name,
        concept_slug=s.concept_slug,
        value=s.value,
        unit_dimension=s.unit.dimension.value,
        as_of=s.as_of.isoformat(),
        source_url=s.source.url,
        source_tier=s.source.tier.value,
        snapshot_sha256=s.source.snapshot_sha256,
        uncertainty_low=unc.range[0] if unc else None,
        uncertainty_high=unc.range[1] if unc else None,
        uncertainty_basis=unc.basis if unc else None,
    )


@router.get(
    "",
    response_model=list[SignalSummary],
    summary="List prediction-market signals",
    description=(
        "Return all read-only prediction-market signals (Kalshi event probabilities "
        "and contract volumes). Each carries a source URL + tier + SHA256 snapshot pin. "
        "Signals never feed a TAM (Q20) — they are a separate, honestly-labelled surface."
    ),
)
async def list_signals(reg: Registry = _REG) -> list[SignalSummary]:
    return [_summary(s) for s in reg.signals.values()]


@router.get(
    "/{slug}",
    response_model=AtomicPrimitive,
    summary="Signal detail",
    description="Full signal primitive: value, unit, geo, source with SHA256 pin, uncertainty.",
)
async def get_signal(slug: str, reg: Registry = _REG) -> AtomicPrimitive:
    signal = reg.signals.get(slug)
    if signal is None:
        raise HTTPException(404, f"signal {slug!r} not found")
    return signal
