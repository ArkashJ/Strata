"""Framework → scenario tree.

For v0.2 the evaluator is intentionally narrow: every supported framework is
multiplicative across its declared inputs. Variants bind input names to
primitive slugs; the evaluator multiplies the bound primitive values and emits
a ``Scenario`` per applicable framework, pinned by primitive ``snapshot_sha256``.

Per Q1, the TAM is a scenario tree, never a scalar.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from ..hashing import mint_state_hash
from ..models import (
    AnalysisLens,
    AtomicPrimitive,
    Concept,
    Framework,
    FrameworkVariant,
    InputUsed,
    Scenario,
    ScenarioBanner,
    SourceTier,
    TAMOutput,
    TAMTarget,
)
from ..registry import Registry


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
    concept = registry.get_concept(concept_slug)
    builds = list(_iter_scenario_builds(registry, concept))
    if not builds:
        raise EvaluatorError(f"concept {concept_slug!r} has no applicable framework variants")
    scenarios = tuple(_build_to_scenario(b) for b in builds)
    method_families = tuple(sorted({b.framework.method_family.value for b in builds}))
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
    tam_slug = mint_state_hash(payload)
    return TAMOutput(
        kind="tam_output",
        slug=tam_slug,
        schema_version=1,
        created_by="strata-evaluator",
        created_at=datetime.now(tz=UTC),
        target=TAMTarget(concept=concept.slug),
        scenarios=scenarios,
        method_families_used=method_families,
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
        atomic = registry.get_atomic(primitive_slug)
        value *= atomic.value
        inputs_used.append(
            InputUsed(
                role_name=input_def.name,
                role=input_def.role,
                primitive_slug=primitive_slug,
                snapshot_sha256=atomic.source.snapshot_sha256,
            )
        )
        banners.extend(_banners_for(atomic))

    return _ScenarioBuild(
        framework=fw,
        variant=variant,
        lens=lens,
        value=value,
        inputs_used=inputs_used,
        banners=_dedupe_banners(banners),
    )


def _banners_for(p: AtomicPrimitive) -> list[ScenarioBanner]:
    if p.source.tier == SourceTier.ANALYST_PARAPHRASE:
        publisher = p.source.original_publisher or "unknown"
        return [
            ScenarioBanner(
                kind="analyst-paraphrase",
                message=(
                    f"Paraphrased from {publisher}; verify against full text at "
                    f"{p.source.url} (accessed {p.source.accessed.isoformat()})."
                ),
            )
        ]
    return []


def _dedupe_banners(banners: list[ScenarioBanner]) -> list[ScenarioBanner]:
    seen: set[tuple[str, str]] = set()
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
