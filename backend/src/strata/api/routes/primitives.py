"""Primitive routes — list atomics/composites and detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.api.responses import error
from strata.models import AtomicPrimitive, CompositePrimitive
from strata.registry import Registry, RegistryError

router = APIRouter(prefix="/p", tags=["primitives"])

_REG = Depends(get_registry)


class PrimitiveSummary(BaseModel):
    slug: str
    name: str
    kind: str
    concept_slug: str
    value: float | None
    unit_label: str


@router.get(
    "",
    response_model=list[PrimitiveSummary],
    summary="List primitives",
    description="Return all atomic and composite primitives with value, unit, and concept linkage. Currently 307+ primitives from BLS, FRED, Census, EDGAR, and World Bank.",
)
async def list_primitives(
    reg: Registry = _REG,
) -> list[PrimitiveSummary]:
    out: list[PrimitiveSummary] = []
    for a in reg.atomic.values():
        out.append(
            PrimitiveSummary(
                slug=a.slug,
                name=a.name,
                kind="atomic_primitive",
                concept_slug=a.concept_slug,
                value=a.value,
                unit_label=f"{a.unit.dimension.value}",
            )
        )
    for c in reg.composite.values():
        out.append(
            PrimitiveSummary(
                slug=c.slug,
                name=c.name,
                kind="composite_primitive",
                concept_slug=c.concept_slug,
                value=None,
                unit_label=f"{c.unit.dimension.value}",
            )
        )
    return out


@router.get(
    "/{slug}",
    response_model=AtomicPrimitive | CompositePrimitive,
    summary="Primitive detail",
    description="Return full primitive model including value, unit, geo, source with SHA256 pin, and uncertainty.",
    responses=error(404, "Primitive not found."),
)
async def get_primitive(
    slug: str,
    reg: Registry = _REG,
) -> AtomicPrimitive | CompositePrimitive:
    try:
        return reg.primitive(slug)
    except RegistryError as exc:
        raise HTTPException(404, f"primitive {slug!r} not found") from exc
