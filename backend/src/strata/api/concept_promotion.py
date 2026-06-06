"""Concept promotion + intersection auto-promotion (PR5, flow 39).

Two flows, both validator-gated and routed through the existing ``/contribute``
review queue — NEVER a direct write to the public bank:

1. **Concept promotion**: a proposed ``Concept`` is structurally validated and
   queued for human review (handled inline by ``routes/contribute._validate``).

2. **Intersection auto-promotion**: when two existing public concepts share a
   scope dimension (e.g. the same vertical NAICS *and* the same persona SOC),
   their *intersection* is a candidate concept worth surfacing — but it is still
   only ever *proposed* into the review queue, never auto-published. The
   "auto" refers to *detecting + drafting* the intersection candidate, not to
   bypassing review (the v1.0 roadmap's "intersection-concept auto-promotion"
   under the v0.5 contribution gate).

This module is pure (no DB, no network): it builds a draft ``Concept`` payload
from two registry concepts. The caller queues the draft via the contribute
review queue.
"""

from __future__ import annotations

from strata.models import Concept
from strata.models.scope import CodedTag, MarketScope
from strata.registry import Registry


def _shared_coded_tags(a: tuple[CodedTag, ...], b: tuple[CodedTag, ...]) -> tuple[CodedTag, ...]:
    """Coded tags present (by code) in both tuples — the intersection on a
    hierarchical scope dimension."""
    b_codes = {t.code for t in b}
    seen: set[str] = set()
    out: list[CodedTag] = []
    for t in a:
        if t.code in b_codes and t.code not in seen:
            out.append(t)
            seen.add(t.code)
    return tuple(out)


def _shared_geo(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    bset = set(b)
    return tuple(g for g in a if g in bset)


def intersection_candidate(reg: Registry, slug_a: str, slug_b: str) -> Concept | None:
    """Return a DRAFT intersection ``Concept`` for two public concepts, or
    ``None`` when they don't meaningfully intersect.

    "Meaningfully" = they share at least one scope dimension (vertical, persona,
    or geo). The draft inherits the intersected scope, the primary lens of
    ``slug_a``, and lists both parents as ``competing_concepts`` so the lineage is
    explicit. The slug is deterministic (``intersection-<a>-x-<b>`` sorted) so
    re-detecting the same pair yields the same candidate (idempotent dedupe at
    review time).
    """
    a = reg.concepts.get(slug_a)
    b = reg.concepts.get(slug_b)
    if a is None or b is None or slug_a == slug_b:
        return None

    vertical = _shared_coded_tags(a.scope.vertical, b.scope.vertical)
    persona = _shared_coded_tags(a.scope.persona, b.scope.persona)
    geo_supply = _shared_geo(a.scope.geo_supply, b.scope.geo_supply)
    geo_demand = _shared_geo(a.scope.geo_demand, b.scope.geo_demand)

    if not (vertical or persona or geo_supply or geo_demand):
        return None  # no shared dimension → no defensible intersection.

    lo, hi = sorted((slug_a, slug_b))
    inter_slug = f"intersection-{lo}-x-{hi}"

    scope = MarketScope(
        vertical=vertical,
        persona=persona,
        geo_supply=geo_supply,
        geo_demand=geo_demand,
    )
    return Concept(
        kind="concept",
        slug=inter_slug,
        schema_version=1,
        name=f"{a.name} ∩ {b.name}",
        definition=(
            f"Auto-detected intersection of '{a.name}' and '{b.name}' on their shared "
            f"scope. A draft candidate for human review — no measurements are attached "
            f"until sourced primitives are bound."
        ),
        analysis_lens=a.analysis_lens,
        scope=scope,
        # No fabricated measurements: the intersection inherits scope + lineage
        # only. Sourced primitives are bound during review (Q20: never invent).
        measurements=(),
        competing_concepts=(lo, hi),
    )
