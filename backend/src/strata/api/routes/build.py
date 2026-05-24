"""Build route — evaluate a concept into a TAM scenario tree."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from strata.api.deps import get_registry
from strata.evaluator.engine import EvaluatorError, size_concept
from strata.models import TAMOutput
from strata.registry import Registry

router = APIRouter(tags=["build"])

_REG = Depends(get_registry)


@router.get(
    "/build/{concept_slug}",
    response_model=TAMOutput,
    summary="Evaluate concept → TAM scenario tree",
)
async def build_tam(
    concept_slug: str,
    reg: Registry = _REG,
) -> TAMOutput:
    try:
        return size_concept(reg, concept_slug)
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get(
    "/tam/{state_hash}",
    response_model=TAMOutput,
    summary="Retrieve a frozen TAM by state hash",
)
async def get_tam(
    state_hash: str,
    reg: Registry = _REG,
) -> TAMOutput:
    if state_hash in reg.tam_outputs:
        return reg.tam_outputs[state_hash]
    raise HTTPException(404, f"tam {state_hash!r} not found")
