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
from dataclasses import dataclass
from datetime import UTC, date, datetime

from ..hashing import mint_state_hash
from ..models import (
    AnalysisLens,
    AnalystParaphraseSource,
    AtomicPrimitive,
    BannerKind,
    Concept,
    Framework,
    FrameworkVariant,
    InputUsed,
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
from ..registry import Registry, RegistryError


class EvaluatorError(RuntimeError):
    pass


@dataclass(slots=True)
class _ScenarioBuild:
    framework: Framework
    variant: FrameworkVariant
    lens: AnalysisLens
    value: float
    inputs_used: list[InputUsed]
    banners: list[ScenarioBanner]


def size_concept(registry: Registry, concept_slug: str) -> TAMOutput:
    try:
        concept = registry.get_concept(concept_slug)
    except RegistryError as exc:
        raise EvaluatorError(f"concept {concept_slug!r} not found") from exc
    builds = list(_iter_scenario_builds(registry, concept))
    if not builds:
        raise EvaluatorError(f"concept {concept_slug!r} has no applicable framework variants")
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
    tam_hash = mint_state_hash(payload)
    return TAMOutput(
        kind="tam_output",
        state_hash=tam_hash,
        schema_version=1,
        created_by="strata-evaluator",
        created_at=datetime.now(tz=UTC),
        target=TAMTarget(concept=concept.slug, concept_name=concept.name),
        scenarios=scenarios,
        method_families_used=tuple(method_families),
        independence_score=_independence(builds),
        uses_synthetic_primitives=False,
        uses_modeled_composites=False,
    )


def _iter_scenario_builds(registry: Registry, concept: Concept) -> Iterator[_ScenarioBuild]:
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
        yield _build_scenario(registry, fw, variant, fw.lens)


@dataclass(slots=True)
class _ResolvedInput:
    value: float
    snapshot_sha256: str
    name: str
    unit: Unit
    banners: list[ScenarioBanner]


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
        return _ResolvedInput(a.value, a.source.snapshot_sha256, a.name, a.unit, _banners_for(a))

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
    return _ResolvedInput(value, snapshot, comp.name, comp.unit, banners)


def _build_scenario(
    registry: Registry,
    fw: Framework,
    variant: FrameworkVariant,
    lens: AnalysisLens,
) -> _ScenarioBuild:
    value = 1.0
    inputs_used: list[InputUsed] = []
    banners: list[ScenarioBanner] = []

    for input_def in fw.inputs:
        primitive_slug = variant.default_inputs.get(input_def.name)
        if primitive_slug is None:
            raise EvaluatorError(
                f"framework {fw.slug!r} variant scope={variant.scope!r} missing "
                f"binding for input {input_def.name!r}"
            )
        resolved = _resolve_input(registry, primitive_slug)
        value *= resolved.value
        if not math.isfinite(value):
            raise EvaluatorError(
                f"framework {fw.slug!r} variant scope={variant.scope!r} produced "
                f"non-finite value after multiplying primitive {primitive_slug!r} "
                f"(value={resolved.value!r})"
            )
        inputs_used.append(
            InputUsed(
                role_name=input_def.name,
                role=input_def.role,
                primitive_slug=primitive_slug,
                snapshot_sha256=resolved.snapshot_sha256,
                value=resolved.value,
                name=resolved.name,
                unit=resolved.unit,
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


def _banners_for(p: AtomicPrimitive) -> list[ScenarioBanner]:
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
