"""Concept routes — list and detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.models import Concept
from strata.registry import Registry, RegistryError

router = APIRouter(prefix="/c", tags=["concepts"])

_REG = Depends(get_registry)


class ConceptSummary(BaseModel):
    slug: str
    name: str
    definition: str
    primary_lens: str
    measurement_count: int


@router.get(
    "",
    response_model=list[ConceptSummary],
    summary="List concepts",
    description="Return all concepts in the registry with their primary analysis lens and measurement count.",
)
async def list_concepts(
    reg: Registry = _REG,
) -> list[ConceptSummary]:
    return [
        ConceptSummary(
            slug=c.slug,
            name=c.name,
            definition=c.definition,
            primary_lens=c.analysis_lens.primary.value,
            measurement_count=len(c.measurements),
        )
        for c in reg.concepts.values()
    ]


@router.get(
    "/{slug}",
    response_model=Concept,
    summary="Concept detail",
    description="Return full concept model including analysis lens, modifiers, measurements, and competing concepts.",
)
async def get_concept(
    slug: str,
    reg: Registry = _REG,
) -> Concept:
    try:
        return reg.get_concept(slug)
    except RegistryError as exc:
        raise HTTPException(404, f"concept {slug!r} not found") from exc
