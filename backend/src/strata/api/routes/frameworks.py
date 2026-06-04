"""Framework routes — list and detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.api.responses import error
from strata.models import Framework
from strata.registry import Registry, RegistryError

router = APIRouter(prefix="/f", tags=["frameworks"])

_REG = Depends(get_registry)


class FrameworkSummary(BaseModel):
    slug: str
    name: str
    method_family: str
    lens: str
    input_count: int


@router.get(
    "",
    response_model=list[FrameworkSummary],
    summary="List frameworks",
    description="Return all frameworks with method family and input count.",
)
async def list_frameworks(
    reg: Registry = _REG,
) -> list[FrameworkSummary]:
    return [
        FrameworkSummary(
            slug=f.slug,
            name=f.name,
            method_family=f.method_family.value,
            lens=f.lens.value,
            input_count=len(f.inputs),
        )
        for f in reg.frameworks.values()
    ]


@router.get(
    "/{slug}",
    response_model=Framework,
    summary="Framework detail",
    description="Return full framework model including method family, unit signature, and inputs.",
    responses=error(404, "Framework not found."),
)
async def get_framework(
    slug: str,
    reg: Registry = _REG,
) -> Framework:
    try:
        return reg.get_framework(slug)
    except RegistryError as exc:
        raise HTTPException(404, f"framework {slug!r} not found") from exc
