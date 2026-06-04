"""Build route — evaluate a concept into a TAM scenario tree."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from strata.api.auth import Principal, require_principal
from strata.api.deps import get_registry
from strata.api.ratelimit import enforce_rate_limit
from strata.api.responses import RATE_LIMITED, UNAUTHORIZED, error, merge
from strata.db.audit import record_audit_safe
from strata.db.tams import get_tam_from_db_safe, persist_tam_safe
from strata.evaluator.engine import (
    EvalOverrides,
    EvaluatorError,
    OverrideValue,
    size_concept,
    trajectory,
)
from strata.models import TAMOutput, TAMTrajectory, Unit
from strata.models.scope import MarketScope
from strata.registry import Registry, RegistryError

router = APIRouter(tags=["build"])

_REG = Depends(get_registry)
_PRINCIPAL = Depends(require_principal)


class OverrideValueIn(BaseModel):
    value: float
    unit: Unit


class RecomputeRequest(BaseModel):
    concept_slug: str
    framework_assumptions: dict[str, dict[str, str]] | None = None
    primitive_overrides: dict[str, OverrideValueIn] | None = None
    # The user-pinned market (sub-project 1.5). When non-empty it overrides the
    # concept's declared scope as the side the scope guard checks against, so the
    # ScopeReport reflects the market the user actually pinned. Optional + empty
    # by default → unchanged behaviour.
    scope: MarketScope | None = None


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
    responses=error(422, "Concept evaluation failed (missing inputs or invalid values)."),
)
async def build_tam(
    concept_slug: str,
    reg: Registry = _REG,
) -> TAMOutput:
    try:
        out = size_concept(reg, concept_slug)
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc
    reg.remember_tam(out)
    await persist_tam_safe(out)
    return out


@router.post(
    "/build/recompute",
    response_model=TAMOutput,
    summary="Recompute a concept's TAM with what-if overrides / primitive swaps",
    responses=merge(
        UNAUTHORIZED,
        RATE_LIMITED,
        error(404, "Concept not found."),
        error(
            422,
            "Override unit mismatch or invalid framework input / evaluation failed.",
        ),
    ),
)
async def recompute_tam(
    req: RecomputeRequest,
    reg: Registry = _REG,
    principal: Principal = _PRINCIPAL,
) -> TAMOutput:
    enforce_rate_limit(principal.org_id)
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
        out = size_concept(
            reg,
            req.concept_slug,
            overrides=overrides,
            declared_scope_override=req.scope,
        )
    except ValueError as exc:
        # Unknown re-pointed primitive in framework_assumptions.
        raise HTTPException(422, str(exc)) from exc
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc

    reg.remember_tam(out)
    await persist_tam_safe(out)
    await record_audit_safe(
        actor=None,
        action="recompute",
        target=req.concept_slug,
        meta={
            "state_hash": out.state_hash,
            "has_overrides": bool(req.primitive_overrides),
            "has_assumptions": bool(req.framework_assumptions),
            "has_scope": bool(req.scope and not req.scope.is_empty),
        },
    )
    return out


@router.get(
    "/build/{concept_slug}/trajectory",
    response_model=TAMTrajectory,
    summary="TAM-over-time series derived from primitive as_of dates",
    responses=error(422, "Concept evaluation failed (missing inputs or invalid values)."),
)
async def build_trajectory(
    concept_slug: str,
    reg: Registry = _REG,
) -> TAMTrajectory:
    try:
        return trajectory(reg, concept_slug)
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc


class SensitivityRow(BaseModel):
    primitive_slug: str
    name: str
    base: float
    low: float
    high: float
    impact: float


class SensitivityResponse(BaseModel):
    concept_slug: str
    base: float
    pct: float
    inputs: list[SensitivityRow]


def _tam_midpoint(tam: TAMOutput) -> float:
    """Mean of scenario values — the headline midpoint the UI shows."""
    values = [s.value for s in tam.scenarios]
    return sum(values) / len(values) if values else 0.0


@router.get(
    "/build/{concept_slug}/sensitivity",
    response_model=SensitivityResponse,
    summary="Per-input ±pct swing on the TAM (feeds the tornado chart)",
    responses=error(404, "Concept not found or not evaluable."),
)
async def build_sensitivity(
    concept_slug: str,
    reg: Registry = _REG,
    pct: float = Query(0.2, description="Sensitivity swing percentage (e.g., 0.2 for ±20%)."),
) -> SensitivityResponse:
    try:
        base_tam = size_concept(reg, concept_slug)
    except EvaluatorError as exc:
        raise HTTPException(404, str(exc)) from exc

    base_mid = _tam_midpoint(base_tam)
    # Unique consuming inputs across the scenario tree (slug -> name, value, unit).
    seen: dict[str, tuple[str, float, Unit]] = {}
    for sc in base_tam.scenarios:
        for iu in sc.inputs_used:
            if iu.unit is not None and iu.primitive_slug not in seen:
                seen[iu.primitive_slug] = (iu.name or iu.primitive_slug, iu.value or 0.0, iu.unit)

    rows: list[SensitivityRow] = []
    for slug, (name, value, unit) in seen.items():
        try:
            low = _tam_midpoint(
                size_concept(
                    reg,
                    concept_slug,
                    overrides=EvalOverrides(
                        primitive_overrides={slug: OverrideValue(value * (1 - pct), unit)}
                    ),
                )
            )
            high = _tam_midpoint(
                size_concept(
                    reg,
                    concept_slug,
                    overrides=EvalOverrides(
                        primitive_overrides={slug: OverrideValue(value * (1 + pct), unit)}
                    ),
                )
            )
        except (EvaluatorError, ValueError):
            continue
        rows.append(
            SensitivityRow(
                primitive_slug=slug,
                name=name,
                base=base_mid,
                low=low,
                high=high,
                impact=abs(high - low),
            )
        )

    rows.sort(key=lambda r: r.impact, reverse=True)
    return SensitivityResponse(concept_slug=concept_slug, base=base_mid, pct=pct, inputs=rows)


@router.post(
    "/build/{concept_slug}/promote",
    response_model=TAMOutput,
    summary="Build + promote a concept's TAM (appears in /browse + sitemap)",
    responses=merge(
        UNAUTHORIZED,
        RATE_LIMITED,
        error(422, "Concept evaluation failed (missing inputs or invalid values)."),
    ),
)
async def promote_tam(
    concept_slug: str, reg: Registry = _REG, principal: Principal = _PRINCIPAL
) -> TAMOutput:
    enforce_rate_limit(principal.org_id)
    try:
        out = size_concept(reg, concept_slug)
    except EvaluatorError as exc:
        raise HTTPException(422, str(exc)) from exc
    promoted = out.model_copy(update={"is_promoted": True})
    reg.remember_tam(promoted)
    await persist_tam_safe(promoted)
    return promoted


@router.get("/browse", response_model=list[TAMOutput], summary="List promoted TAMs")
async def browse(reg: Registry = _REG) -> list[TAMOutput]:
    return [t for t in reg.tam_outputs.values() if t.is_promoted]


@router.get(
    "/tam/{state_hash}",
    response_model=TAMOutput,
    summary="Retrieve a frozen TAM by state hash",
    responses=error(404, "TAM not found."),
)
async def get_tam(
    state_hash: str,
    reg: Registry = _REG,
) -> TAMOutput:
    if state_hash in reg.tam_outputs:
        return reg.tam_outputs[state_hash]
    # Fall back to durable storage: the in-memory cache is FIFO-capped and reset
    # on restart, but a shared permalink must keep resolving.
    persisted = await get_tam_from_db_safe(state_hash)
    if persisted is not None:
        reg.remember_tam(persisted)  # re-warm the cache
        return persisted
    raise HTTPException(404, f"tam {state_hash!r} not found")
