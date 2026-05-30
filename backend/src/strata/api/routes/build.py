"""Build route — evaluate a concept into a TAM scenario tree."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.db.audit import record_audit_safe
from strata.evaluator.engine import (
    EvalOverrides,
    EvaluatorError,
    OverrideValue,
    size_concept,
    trajectory,
)
from strata.models import TAMOutput, TAMTrajectory, Unit
from strata.registry import Registry, RegistryError

router = APIRouter(tags=["build"])

_REG = Depends(get_registry)


class OverrideValueIn(BaseModel):
    value: float
    unit: Unit


class RecomputeRequest(BaseModel):
    concept_slug: str
    framework_assumptions: dict[str, dict[str, str]] | None = None
    primitive_overrides: dict[str, OverrideValueIn] | None = None


def _validate_override_units(reg: Registry, req: RecomputeRequest) -> None:
    """Each what-if override's unit must be compatible with the consuming
    framework input's ``unit_signature`` (HTTP 422 on mismatch). The consuming
    input is found by scanning the concept's applicable framework variants for
    the overridden primitive slug.
    """
    if not req.primitive_overrides:
        return
    # slug -> the input unit_signature(s) that consume it for this concept.
    signatures: dict[str, list[Unit]] = {}
    for fw in reg.iter_frameworks():
        variant = fw.variant_for(req.concept_slug)
        if variant is None:
            continue
        assumptions = (req.framework_assumptions or {}).get(fw.slug, {})
        for inp in fw.inputs:
            bound = assumptions.get(inp.name) or variant.default_inputs.get(inp.name)
            if bound is None:
                continue
            signatures.setdefault(bound, []).append(inp.unit_signature)

    for slug, ov in req.primitive_overrides.items():
        sigs = signatures.get(slug)
        if not sigs:
            continue
        if not any(ov.unit.is_compatible_with(sig) for sig in sigs):
            raise HTTPException(
                422,
                f"override unit for primitive {slug!r} is incompatible with the "
                f"consuming framework input signature",
            )


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


@router.post(
    "/build/recompute",
    response_model=TAMOutput,
    summary="Recompute a concept's TAM with what-if overrides / primitive swaps",
)
async def recompute_tam(
    req: RecomputeRequest,
    reg: Registry = _REG,
) -> TAMOutput:
    try:
        reg.get_concept(req.concept_slug)
    except RegistryError as exc:
        raise HTTPException(404, f"concept {req.concept_slug!r} not found") from exc

    _validate_override_units(reg, req)

    overrides = EvalOverrides(
        primitive_overrides={
            slug: OverrideValue(value=ov.value, unit=ov.unit)
            for slug, ov in (req.primitive_overrides or {}).items()
        },
        framework_assumptions=req.framework_assumptions or {},
    )
    try:
        out = size_concept(reg, req.concept_slug, overrides=overrides)
    except ValueError as exc:
        # Unknown re-pointed primitive in framework_assumptions.
        raise HTTPException(422, str(exc)) from exc
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc

    await record_audit_safe(
        actor=None,
        action="recompute",
        target=req.concept_slug,
        meta={
            "state_hash": out.state_hash,
            "has_overrides": bool(req.primitive_overrides),
            "has_assumptions": bool(req.framework_assumptions),
        },
    )
    return out


@router.get(
    "/build/{concept_slug}/trajectory",
    response_model=TAMTrajectory,
    summary="TAM-over-time series derived from primitive as_of dates",
)
async def build_trajectory(
    concept_slug: str,
    reg: Registry = _REG,
) -> TAMTrajectory:
    try:
        return trajectory(reg, concept_slug)
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
