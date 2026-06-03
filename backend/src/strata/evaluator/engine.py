"""Framework → scenario tree.

For v0.2 the evaluator is intentionally narrow: every supported framework is
multiplicative across its declared inputs. Variants bind input names to
primitive slugs; the evaluator multiplies the bound primitive values and emits
a ``Scenario`` per applicable framework, pinned by primitive ``snapshot_sha256``.

Per Q1, the TAM is a scenario tree, never a scalar.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from statistics import median

from ..hashing import mint_state_hash
from ..models import (
    AnalysisLens,
    AnalystParaphraseSource,
    AtomicPrimitive,
    BannerKind,
    Concept,
    Convergence,
    Framework,
    FrameworkVariant,
    InputUsed,
    MethodFamily,
    Scenario,
    ScenarioBanner,
    SetOperation,
    SourceTier,
    TAMOutput,
    TAMTarget,
    TAMTrajectory,
    TrajectoryPoint,
    Unit,
    UnitBasis,
    UnitDimension,
    UnitKind,
)
from ..models.scope import MarketScope
from ..registry import Registry, RegistryError
from ..scope import build_scope_report


class EvaluatorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OverrideValue:
    """A transient what-if scalar the user typed in the `/build` UI (Strata
    Live). Never persisted as a primitive; carries the consuming unit so the
    route can validate it against the framework input signature."""

    value: float
    unit: Unit


@dataclass(frozen=True, slots=True)
class EvalOverrides:
    """Override-aware evaluation inputs (Strata Live Track A).

    - ``primitive_overrides`` substitutes a primitive's sourced value with a
      user what-if scalar at evaluation time → ``user_override`` banner +
      ``uses_synthetic_primitives``. The registry is NEVER mutated.
    - ``framework_assumptions`` re-points a named framework input to a
      different *existing* primitive slug before evaluation (schema-pure, no
      banner).
    """

    primitive_overrides: dict[str, OverrideValue] = field(default_factory=dict)
    framework_assumptions: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(slots=True)
class _ScenarioBuild:
    framework: Framework
    variant: FrameworkVariant
    lens: AnalysisLens
    value: float
    inputs_used: list[InputUsed]
    banners: list[ScenarioBanner]
    uses_synthetic: bool = False


def size_concept(
    registry: Registry,
    concept_slug: str,
    overrides: EvalOverrides | None = None,
    declared_scope_override: MarketScope | None = None,
) -> TAMOutput:
    try:
        concept = registry.get_concept(concept_slug)
    except RegistryError as exc:
        raise EvaluatorError(f"concept {concept_slug!r} not found") from exc
    builds = list(_iter_scenario_builds(registry, concept, overrides))
    if not builds:
        raise EvaluatorError(f"concept {concept_slug!r} has no applicable framework variants")
    # A what-if override on a slug that no applicable framework input binds would
    # otherwise be silently dropped (200 + base TAM, no banner) — the inverse of
    # an unknown swap, which already raises. Reject it so the API can't claim a
    # recompute happened when the override changed nothing.
    if overrides is not None and overrides.primitive_overrides:
        consumed = {
            iu.primitive_slug
            for b in builds
            for iu in b.inputs_used
            if iu.primitive_slug in overrides.primitive_overrides
        }
        unconsumed = sorted(set(overrides.primitive_overrides) - consumed)
        if unconsumed:
            raise EvaluatorError(
                f"primitive_overrides {unconsumed} are not consumed by any applicable "
                f"framework input for concept {concept.slug!r}"
            )
    scenarios = tuple(_build_to_scenario(b) for b in builds)
    method_families = sorted({b.framework.method_family for b in builds}, key=lambda m: m.value)
    payload: dict[str, object] = {
        "concept": concept.slug,
        "scenarios": [
            {
                "framework": b.framework.slug,
                "variant": b.variant.scope,
                "value": b.value,
                "inputs": [
                    {
                        "name": iu.role_name,
                        "primitive": iu.primitive_slug,
                        "hash": iu.snapshot_sha256,
                    }
                    for iu in b.inputs_used
                ],
            }
            for b in builds
        ],
    }
    if overrides is not None:
        # Fold the override knobs into the hashed payload so equivalent
        # override states collide and distinct ones mint a fresh hash (Q38).
        payload["overrides"] = {
            "primitive_overrides": {
                slug: {"value": ov.value, "unit": ov.unit.model_dump(mode="json")}
                for slug, ov in sorted(overrides.primitive_overrides.items())
            },
            "framework_assumptions": {
                fw: dict(sorted(binds.items()))
                for fw, binds in sorted(overrides.framework_assumptions.items())
            },
        }
    # A user-pinned market is a real input: when present it overrides the
    # concept's declared scope as the side the guard checks each primitive
    # against, and folds into the hash so a different market mints a different
    # /build/<hash>. Empty/absent override = the concept's own declared scope.
    declared_scope = (
        declared_scope_override
        if declared_scope_override is not None and not declared_scope_override.is_empty
        else concept.scope
    )
    if declared_scope_override is not None and not declared_scope_override.is_empty:
        payload["declared_scope"] = declared_scope.model_dump(mode="json")
    tam_hash = mint_state_hash(payload)
    uses_synthetic = any(b.uses_synthetic for b in builds)
    return TAMOutput(
        kind="tam_output",
        state_hash=tam_hash,
        schema_version=1,
        created_by="strata-evaluator",
        created_at=datetime.now(tz=UTC),
        target=TAMTarget(concept=concept.slug, concept_name=concept.name),
        scenarios=scenarios,
        method_families_used=tuple(method_families),
        convergence=_convergence(builds),
        independence_score=_independence(builds),
        uses_synthetic_primitives=uses_synthetic,
        uses_modeled_composites=False,
        scope=build_scope_report(registry, declared_scope, scenarios),
    )


def _iter_scenario_builds(
    registry: Registry,
    concept: Concept,
    overrides: EvalOverrides | None = None,
) -> Iterator[_ScenarioBuild]:
    """Yield one build per framework whose variant scope == concept.slug AND
    whose lens matches the concept's primary or secondary lens.
    """
    lens_allowed = {concept.analysis_lens.primary}
    if concept.analysis_lens.secondary is not None:
        lens_allowed.add(concept.analysis_lens.secondary)

    for fw in registry.iter_frameworks():
        if fw.applicable_to and concept.slug not in fw.applicable_to:
            continue
        if fw.lens not in lens_allowed:
            continue
        variant = fw.variant_for(concept.slug)
        if variant is None:
            continue
        yield _build_scenario(registry, fw, variant, fw.lens, overrides)


@dataclass(slots=True)
class _ResolvedInput:
    value: float
    snapshot_sha256: str
    name: str
    unit: Unit
    banners: list[ScenarioBanner]
    # Source tier of the underlying primitive, surfaced so the TAM artifact can
    # show a per-input provenance mix. A composite reports its members' shared
    # tier, or "mixed" when they differ (it has no single source of its own).
    source_tier: str | None = None
    # The atomic's source URL (number-level provenance). None for composites —
    # a union of members links its members, not one invented URL.
    source_url: str | None = None


def _resolve_input(registry: Registry, slug: str) -> _ResolvedInput:
    """Resolve a framework-input slug to a value the evaluator can multiply.

    An atomic primitive contributes its sourced value directly. A *composite*
    is computed from its member atomics via the declared same-unit set
    operation (Q3): ``union`` sums the members. The composite's snapshot hash
    is content-addressed over its members' hashes so the resulting TAM stays
    reproducible. Composites never do unit-crossing math — that stays in the
    framework (the composite/framework line is load-bearing, Q3).

    Set ops other than ``union`` are not yet consumed by the v0.2 evaluator;
    they raise rather than silently mis-computing.
    """
    if slug in registry.atomic:
        a = registry.atomic[slug]
        return _ResolvedInput(
            a.value,
            a.source.snapshot_sha256,
            a.name,
            a.unit,
            _banners_for(a),
            str(a.source.tier),
            source_url=str(a.source.url),
        )

    if slug not in registry.composite:
        raise EvaluatorError(
            f"input slug {slug!r} is neither a known atomic nor composite primitive"
        )

    comp = registry.composite[slug]
    missing = [m for m in comp.inputs if m not in registry.atomic]
    if missing:
        raise EvaluatorError(f"composite {slug!r} references unknown atomic primitives {missing}")
    members = [registry.atomic[m] for m in comp.inputs]
    for m in members:
        if m.unit != comp.unit:
            raise EvaluatorError(
                f"composite {slug!r} member {m.slug!r} unit {m.unit!r} != composite "
                f"unit {comp.unit!r}; composites are same-unit only (Q3)"
            )
    if comp.set_operation is not SetOperation.UNION:
        raise EvaluatorError(
            f"composite {slug!r} set_operation {comp.set_operation.value!r} is not yet "
            f"supported by the evaluator (only 'union')"
        )
    value = math.fsum(m.value for m in members)
    # Content-address over slug:hash pairs (not bare hashes) so two members that
    # happen to share a snapshot hash can't collapse the composite identity.
    snapshot = hashlib.sha256(
        "|".join(sorted(f"{m.slug}:{m.source.snapshot_sha256}" for m in members)).encode()
    ).hexdigest()
    banners: list[ScenarioBanner] = []
    for m in members:
        banners.extend(_banners_for(m))
    member_tiers = {str(m.source.tier) for m in members}
    comp_tier = member_tiers.pop() if len(member_tiers) == 1 else "mixed"
    return _ResolvedInput(value, snapshot, comp.name, comp.unit, banners, comp_tier)


def _build_scenario(
    registry: Registry,
    fw: Framework,
    variant: FrameworkVariant,
    lens: AnalysisLens,
    overrides: EvalOverrides | None = None,
) -> _ScenarioBuild:
    value = 1.0
    inputs_used: list[InputUsed] = []
    banners: list[ScenarioBanner] = []
    uses_synthetic = False

    # framework_assumptions re-point named inputs to a different EXISTING
    # primitive (schema-pure). Validate up front so a bad slug fails cleanly.
    assumptions = overrides.framework_assumptions.get(fw.slug, {}) if overrides else {}
    for input_name, repointed in assumptions.items():
        if repointed not in registry.atomic and repointed not in registry.composite:
            raise ValueError(
                f"framework_assumptions[{fw.slug!r}][{input_name!r}] points at "
                f"{repointed!r}, which is not a known primitive"
            )

    primitive_overrides = overrides.primitive_overrides if overrides else {}

    for input_def in fw.inputs:
        primitive_slug = assumptions.get(input_def.name) or variant.default_inputs.get(
            input_def.name
        )
        if primitive_slug is None:
            raise EvaluatorError(
                f"framework {fw.slug!r} variant scope={variant.scope!r} missing "
                f"binding for input {input_def.name!r}"
            )
        resolved = _resolve_input(registry, primitive_slug)
        input_banners = resolved.banners
        input_value = resolved.value
        # A transient what-if scalar substitutes the sourced value (Strata
        # Live). The unit is kept; never written back to the registry.
        if primitive_slug in primitive_overrides:
            ov = primitive_overrides[primitive_slug]
            input_value = ov.value
            uses_synthetic = True
            input_banners = [
                ScenarioBanner(
                    kind=BannerKind.USER_OVERRIDE,
                    message=(
                        f"{resolved.name} overridden with a transient what-if value "
                        f"{ov.value:g} (not a sourced primitive)."
                    ),
                )
            ]
        value *= input_value
        if not math.isfinite(value):
            raise EvaluatorError(
                f"framework {fw.slug!r} variant scope={variant.scope!r} produced "
                f"non-finite value after multiplying primitive {primitive_slug!r} "
                f"(value={input_value!r})"
            )
        inputs_used.append(
            InputUsed(
                role_name=input_def.name,
                role=input_def.role,
                primitive_slug=primitive_slug,
                snapshot_sha256=resolved.snapshot_sha256,
                value=input_value,
                name=resolved.name,
                unit=resolved.unit,
                source_tier=resolved.source_tier,
                source_url=resolved.source_url,
            )
        )
        banners.extend(input_banners)

    return _ScenarioBuild(
        framework=fw,
        variant=variant,
        lens=lens,
        value=value,
        inputs_used=inputs_used,
        banners=_dedupe_banners(banners),
        uses_synthetic=uses_synthetic,
    )


def _banners_for(p: AtomicPrimitive) -> list[ScenarioBanner]:
    # Wave 5B — a private org-scoped first-party input sharpens the TAM with data
    # only this tenant can see; flag it so the output is clearly tenant-private.
    if p.visibility == "private":
        return [
            ScenarioBanner(
                kind=BannerKind.PRIVATE,
                message=(
                    f"{p.name} is private first-party data"
                    + (f" (org {p.org_id})" if p.org_id else "")
                    + " — visible only to this tenant."
                ),
            )
        ]
    if isinstance(p.source, AnalystParaphraseSource):
        return [
            ScenarioBanner(
                kind=BannerKind.ANALYST_PARAPHRASE,
                message=(
                    f"Paraphrased from {p.source.original_publisher}; verify against "
                    f"full text at {p.source.url} (accessed {p.source.accessed.isoformat()})."
                ),
            )
        ]
    # A community-modeled input is an estimate, not a sourced measurement — it
    # MUST surface as a footnote in the UI and exports (Q20/Q37 honesty rule).
    # (p.source is narrowed to StandardSource here — the paraphrase branch
    # returned above.)
    if p.source.tier is SourceTier.COMMUNITY_MODELED:
        rng = (
            f" (modeled range {p.uncertainty.range[0]:g}-{p.uncertainty.range[1]:g})"
            if p.uncertainty is not None
            else ""
        )
        return [
            ScenarioBanner(
                kind=BannerKind.MODELED,
                message=f"{p.name} is community-modeled, not a sourced measurement{rng}.",
            )
        ]
    return []


def _dedupe_banners(banners: list[ScenarioBanner]) -> list[ScenarioBanner]:
    seen: set[tuple[BannerKind, str]] = set()
    out: list[ScenarioBanner] = []
    for b in banners:
        key = (b.kind, b.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


def _build_to_scenario(b: _ScenarioBuild) -> Scenario:
    return Scenario(
        definition=f"{b.framework.name} bound to variant {b.variant.scope!r}",
        lens=b.lens,
        framework=b.framework.slug,
        framework_variant=b.variant.scope,
        value=b.value,
        unit=b.framework.output_unit,
        inputs_used=tuple(b.inputs_used),
        assumptions={},
        banners=tuple(b.banners),
        uses_synthetic_primitives=b.uses_synthetic,
    )


def _convergence(builds: list[_ScenarioBuild]) -> Convergence | None:
    """MV2: bottoms-up vs tops-down cross-check. Group builds by method family,
    take each family's median value, and compare the lowest-valued family head
    to head with the highest-valued one. Returns None unless ≥2 distinct families
    sized the concept (a single method has nothing to converge with — never
    fabricate a second). Pure synthesis of already-sourced scenario values."""
    by_family: dict[MethodFamily, list[float]] = {}
    for b in builds:
        by_family.setdefault(b.framework.method_family, []).append(b.value)
    if len(by_family) < 2:
        return None
    # Comparing values across families is only meaningful if they share a unit;
    # a ratio between USD/year and a stock USD would be dimensionally invalid. If
    # the families disagree on output unit, there is nothing honest to converge.
    output_unit = builds[0].framework.output_unit
    if any(b.framework.output_unit != output_unit for b in builds):
        return None
    family_median = {fam: median(values) for fam, values in by_family.items()}
    low_family = min(family_median, key=lambda f: family_median[f])
    high_family = max(family_median, key=lambda f: family_median[f])
    low_value = family_median[low_family]
    high_value = family_median[high_family]
    if low_value <= 0:
        return None
    return Convergence(
        low_family=low_family,
        high_family=high_family,
        low_value=low_value,
        high_value=high_value,
        ratio=high_value / low_value,
        unit=output_unit,
    )


def _independence(builds: list[_ScenarioBuild]) -> float:
    """Q7: independence is the fraction of method-families that are distinct.

    Single-scenario or single-family TAMs get 0.0; mixed-family multi-scenario
    TAMs approach 1.0 as the family set grows.
    """
    if len(builds) <= 1:
        return 0.0
    families = {b.framework.method_family for b in builds}
    return (len(families) - 1) / max(1, len(builds) - 1)


def _build_scenario_as_of(
    registry: Registry,
    fw: Framework,
    variant: FrameworkVariant,
    lens: AnalysisLens,
    cutoff: date,
) -> _ScenarioBuild | None:
    """Attempt to build a scenario using only primitives available at `cutoff`.

    Returns None if any required input is missing at that date so the caller
    can skip this framework for this point rather than raising.
    """
    value = 1.0
    inputs_used: list[InputUsed] = []
    banners: list[ScenarioBanner] = []

    for input_def in fw.inputs:
        primitive_slug = variant.default_inputs.get(input_def.name)
        if primitive_slug is None:
            return None
        # Skip inputs whose data postdates the snapshot. A composite is
        # available only once every member atomic is (its effective as_of is
        # the latest member).
        if primitive_slug in registry.atomic:
            if registry.atomic[primitive_slug].as_of > cutoff:
                return None
        elif primitive_slug in registry.composite:
            members = registry.composite[primitive_slug].inputs
            if any(m not in registry.atomic for m in members):
                return None
            if any(registry.atomic[m].as_of > cutoff for m in members):
                return None
        else:
            return None

        resolved = _resolve_input(registry, primitive_slug)
        value *= resolved.value
        if not math.isfinite(value):
            return None
        inputs_used.append(
            InputUsed(
                role_name=input_def.name,
                role=input_def.role,
                primitive_slug=primitive_slug,
                snapshot_sha256=resolved.snapshot_sha256,
                value=resolved.value,
                name=resolved.name,
                unit=resolved.unit,
                source_tier=resolved.source_tier,
                source_url=resolved.source_url,
            )
        )
        banners.extend(resolved.banners)

    return _ScenarioBuild(
        framework=fw,
        variant=variant,
        lens=lens,
        value=value,
        inputs_used=inputs_used,
        banners=_dedupe_banners(banners),
    )


def trajectory(registry: Registry, concept_slug: str) -> TAMTrajectory:
    """Compute a TAM-over-time series for a concept.

    For each distinct ``as_of`` date across the concept's measurement
    primitives, we re-evaluate the concept using only primitives whose
    ``as_of <= date``.  Frameworks whose required inputs aren't yet available
    at a given date are skipped — if none are satisfiable the point is omitted
    entirely.  ``points`` is empty when no date yields a satisfiable evaluation.
    """
    try:
        concept = registry.get_concept(concept_slug)
    except RegistryError as exc:
        raise EvaluatorError(f"concept {concept_slug!r} not found") from exc

    lens_allowed = {concept.analysis_lens.primary}
    if concept.analysis_lens.secondary is not None:
        lens_allowed.add(concept.analysis_lens.secondary)

    # Collect the universe of primitives that any applicable framework could
    # consume for this concept, then extract their distinct as_of dates.
    candidate_slugs: set[str] = set()
    applicable_fws: list[tuple[Framework, FrameworkVariant]] = []

    for fw in registry.iter_frameworks():
        if fw.applicable_to and concept.slug not in fw.applicable_to:
            continue
        if fw.lens not in lens_allowed:
            continue
        variant = fw.variant_for(concept.slug)
        if variant is None:
            continue
        applicable_fws.append((fw, variant))
        for primitive_slug in variant.default_inputs.values():
            candidate_slugs.add(primitive_slug)
            # A composite contributes its members' dates (the composite slug
            # itself isn't in registry.atomic, so its as_of comes from members).
            if primitive_slug in registry.composite:
                candidate_slugs.update(registry.composite[primitive_slug].inputs)

    if not applicable_fws:
        return TAMTrajectory(
            concept_slug=concept.slug,
            concept_name=concept.name,
            unit=_pick_output_unit(applicable_fws),
            points=[],
        )

    # Distinct dates from primitives that actually exist in the registry.
    dates: list[date] = sorted(
        {registry.atomic[slug].as_of for slug in candidate_slugs if slug in registry.atomic}
    )

    output_unit = _pick_output_unit(applicable_fws)
    points: list[TrajectoryPoint] = []

    for cutoff in dates:
        builds: list[_ScenarioBuild] = []
        for fw, variant in applicable_fws:
            build = _build_scenario_as_of(registry, fw, variant, fw.lens, cutoff)
            if build is not None:
                builds.append(build)

        if not builds:
            continue

        values = [b.value for b in builds]
        method_families = sorted({b.framework.method_family.value for b in builds})
        points.append(
            TrajectoryPoint(
                as_of=cutoff,
                # Midpoint triangulation mirrors the /build TAMOutput midpoint.
                value=sum(values) / len(values),
                low=min(values),
                high=max(values),
                method_families=method_families,
                scenarios_n=len(builds),
            )
        )

    return TAMTrajectory(
        concept_slug=concept.slug,
        concept_name=concept.name,
        unit=output_unit,
        points=points,
    )


def _pick_output_unit(fw_pairs: list[tuple[Framework, FrameworkVariant]]) -> Unit:
    """Return the output unit of the first applicable framework, or a generic
    currency unit when the list is empty (trajectory with no satisfiable points).
    """
    if fw_pairs:
        return fw_pairs[0][0].output_unit
    return Unit(
        kind=UnitKind.FLOW,
        dimension=UnitDimension.CURRENCY,
        denominator="year",
        currency="USD",
        basis=UnitBasis.NOMINAL,
    )
