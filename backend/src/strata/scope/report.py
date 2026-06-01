"""Build a serializable scope report for a sized concept (sub-project 1).

Bridges the pure guard (``classify_scope`` → dataclasses) to the Pydantic
``ScopeReport`` the API attaches to a ``TAMOutput``. For each unique primitive a
scenario consumes, it snaps the displayed scope to that primitive's true scope
and surfaces only *definite* divergences from the concept's declared scope —
``UNKNOWN`` (a primitive that declares nothing on a dimension, e.g. a price seat
with no persona, or a not-yet-backfilled legacy primitive) is suppressed so the
report flags real mismatches, not missing metadata.
"""

from __future__ import annotations

from collections.abc import Iterable

from strata.models.scope import InputScope, MarketScope, ScopeReport, ScopeWarningOut
from strata.models.tam_output import Scenario
from strata.registry import Registry, RegistryError
from strata.scope.guard import Relationship, classify_scope


def _primitive_scope(registry: Registry, slug: str) -> MarketScope:
    """The primitive's own declared scope, or an empty scope when it is a
    composite / not found (treated as unverified, never a hard mismatch)."""
    try:
        return registry.get_atomic(slug).scope
    except RegistryError:
        return MarketScope()


def build_scope_report(
    registry: Registry, declared: MarketScope, scenarios: Iterable[Scenario]
) -> ScopeReport:
    """Compare the declared market scope against each consumed primitive's true
    scope. One ``InputScope`` per unique primitive (first role wins); warnings are
    the guard's definite divergences (UNKNOWN suppressed)."""
    inputs: list[InputScope] = []
    seen: set[str] = set()
    for scenario in scenarios:
        for iu in scenario.inputs_used:
            if iu.primitive_slug in seen:
                continue
            seen.add(iu.primitive_slug)
            actual = _primitive_scope(registry, iu.primitive_slug)
            match = classify_scope(declared, actual)
            warnings = tuple(
                ScopeWarningOut(
                    dimension=w.dimension,
                    relationship=w.relationship.value,
                    message=w.message,
                )
                for w in match.warnings
                if w.relationship is not Relationship.UNKNOWN
            )
            inputs.append(
                InputScope(
                    primitive_slug=iu.primitive_slug,
                    role_name=iu.role_name,
                    displayed=match.displayed,
                    warnings=warnings,
                )
            )
    return ScopeReport(
        declared=declared,
        inputs=tuple(inputs),
        ok=not any(i.warnings for i in inputs),
    )
