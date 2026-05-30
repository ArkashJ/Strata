"""4-step hybrid retrieval pipeline (spec §3, §3.5).

This is the engine both the HTTP route and the CLI subcommand call into.
It emits a stream of ``PipelineEvent``s and a terminal ``ResolverResult``.

Pipeline flow
-------------

  query (free-form text)
          │
          ▼  pre: resolve_slug (Claude — maps query to concept/primitive slug or NOVEL)
          │
          ├──► Step 1: concept hit
          │    registry.concepts[slug] → evaluator.size_concept → ResolverResult(via="concept")
          │
          ├──► Step 2: primitive hit
          │    registry.atomic[slug(s)] → compose or single → ResolverResult(via="primitive")
          │
          ├──► Step 3: connector live  (skip when allow_live=False / STRATA_OFFLINE=1)
          │    router.choose → connectors._dispatch.call_and_convert
          │    → writer.upsert_primitive → ResolverResult(via="connector")
          │
          └──► Step 4: fallback        (skip when allow_fallback=False / STRATA_OFFLINE=1)
               parse_query (Claude) → search_primitive (Exa) × N
               → multiply hits → ResolverResult(via="fallback")  [ephemeral, never on disk]

Steps are tried in order; the first to return a non-None result wins.
Steps 3 and 4 are opt-out via RunOptions. The CLI maps STRATA_OFFLINE=1
to ``allow_live=False, allow_fallback=False``.

The router is loaded lazily inside step 3 to keep ``import strata.resolver``
fast for paths that don't need it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from ..evaluator import size_concept
from ..models import AtomicPrimitive
from ..registry import Registry, RegistryError
from . import writer
from .events import PipelineEvent, PipelineEventKind, PipelineStatus, ResolverResult, ScenarioLite
from .parse import ParsedQuery, parse_query
from .search import PrimitiveHit, search_primitive
from .slug import (
    ConceptSummary,
    PrimitiveSummary,
    ResolvedQuery,
    ResolverIntent,
    resolve_slug,
)
from .units import UnitMismatchError, assert_multipliable

# Injection seams so the HTTP route can force a deterministic fallback path
# (its own patchable parse/search functions) without touching the network for
# slug resolution or routing. Defaults are the real module functions, which is
# what the CLI uses for the full 4-step pipeline.
SlugFn = Callable[[str], ResolvedQuery]
ParseFn = Callable[..., ParsedQuery]
SearchFn = Callable[..., PrimitiveHit | None]

_log = logging.getLogger(__name__)


def call_and_convert(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
    """Thin, patchable indirection to ``connectors._dispatch.call_and_convert``.

    Imported lazily (via ``import_module`` so static analysis does not require
    the dispatch module to exist yet) to keep the resolver import path free of
    network-heavy connector clients. If the dispatch layer is absent, the
    ``ModuleNotFoundError`` propagates and step 3 treats it as a dispatch
    failure — the caller falls through to step 4.
    """
    import importlib

    dispatch = importlib.import_module("strata.connectors._dispatch")
    result: dict[str, Any] = dispatch.call_and_convert(connector, method, args)
    return result


@dataclass(slots=True)
class RunOptions:
    """Pipeline knobs. CLI flags + env vars surface through this struct."""

    allow_live: bool = True
    allow_fallback: bool = True
    expansion_budget: int = 6
    primitive_only: bool = False
    model: str = "claude-sonnet-4-6"


@dataclass(slots=True)
class _RunState:
    events: list[PipelineEvent] = field(default_factory=list[PipelineEvent])
    resolved: ResolvedQuery | None = None
    wrote_primitives: list[str] = field(default_factory=list[str])


def _summarize_concepts(registry: Registry) -> list[ConceptSummary]:
    return [
        ConceptSummary(
            slug=c.slug,
            name=c.name,
            one_line_description=(getattr(c, "definition", "") or "")[:200],
        )
        for c in registry.concepts.values()
    ]


def _summarize_primitives(registry: Registry) -> list[PrimitiveSummary]:
    return [
        PrimitiveSummary(
            slug=p.slug,
            name=p.name,
            one_line_description=(getattr(p, "description", "") or "")[:200],
        )
        for p in registry.atomic.values()
    ]


def _emit(state: _RunState, event: PipelineEvent) -> None:
    state.events.append(event)


def _step1_concept(
    state: _RunState, registry: Registry, resolved: ResolvedQuery
) -> ResolverResult | None:
    if resolved.intent != ResolverIntent.CONCEPT or not resolved.concept_slug:
        return None
    concept = registry.concepts.get(resolved.concept_slug)
    if concept is None:
        return None
    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.CONCEPT_HIT,
            step="1",
            payload={"concept_slug": concept.slug, "name": concept.name},
        ),
    )
    # Size the concept through the evaluator so the concept path returns the
    # FULL composed TAM (value + attached primitives + lens), not just the
    # name — the CLI compact view and the frontend charts both render off
    # these fields. Falls back to the identity-only result when the concept has
    # no applicable framework variant (so its disagreement view still loads).
    sized = _size_registered_concept(state, registry, concept.slug, via="concept")
    if sized is not None:
        sized.definition = getattr(concept, "definition", None)
        return sized
    return ResolverResult(
        status=PipelineStatus.OK,
        via="concept",
        concept_name=concept.name,
        definition=getattr(concept, "definition", None),
        events=state.events,
    )


def _step2_primitives(
    state: _RunState,
    registry: Registry,
    resolved: ResolvedQuery,
    options: RunOptions,
) -> ResolverResult | None:
    # Step 2 only fires when the slug resolver already named specific primitives.
    # Falling through here (returning None) sends the query to connector live /
    # fallback, which is appropriate for novel queries the registry hasn't seen.
    if resolved.intent != ResolverIntent.PRIMITIVE or not resolved.primitive_slugs:
        return None

    hits: list[AtomicPrimitive] = []
    for slug in resolved.primitive_slugs:
        prim = registry.atomic.get(slug)
        if prim is None:
            continue
        hits.append(prim)
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.PRIMITIVE_HIT,
                step="2",
                payload={"slug": prim.slug, "value": prim.value, "unit": prim.unit.model_dump()},
            ),
        )
    if not hits:
        return None

    if len(hits) == 1 or options.primitive_only:
        p = hits[0]
        return ResolverResult(
            status=PipelineStatus.OK,
            via="primitive",
            tam_value=p.value,
            formatted_tam=str(p.value),
            primitives_used=[
                {
                    "slug": p.slug,
                    "name": p.name,
                    "value": p.value,
                    "unit": p.unit.model_dump(),
                }
            ],
            banner="single primitive, not a TAM",
            events=state.events,
        )

    primitives_used = [
        {
            "slug": p.slug,
            "name": p.name,
            "value": p.value,
            "unit": p.unit.model_dump(),
        }
        for p in hits
    ]

    # Step 2b (best-effort): if the framework_hint names a *registered concept*,
    # the evaluator can build a real scenario tree from the bound variants. This
    # turns the multi-primitive miss into a fully-composed TAM instead of the
    # PARTIAL fallthrough below. Slug resolution already did the expensive work;
    # we just need to confirm the concept exists before paying the evaluator cost.
    hint = resolved.framework_hint
    if hint and hint in registry.concepts:
        composed = _size_registered_concept(state, registry, hint, via="primitive")
        if composed is not None:
            composed.primitives_used = primitives_used or composed.primitives_used
            return composed

    # Multi-primitive with no usable framework: return primitives_used so the
    # renderer can show them; banner explains why no composed TAM was emitted.
    return ResolverResult(
        status=PipelineStatus.PARTIAL,
        via="primitive",
        primitives_used=primitives_used,
        framework_name=resolved.framework_hint,
        banner=(
            "matched multiple primitives; framework composition not yet wired "
            "for free-form queries — run `strata size <concept-slug>` for a "
            "fully-composed TAM."
        ),
        events=state.events,
    )


def _size_registered_concept(
    state: _RunState,
    registry: Registry,
    concept_slug: str,
    *,
    via: Literal["concept", "primitive", "connector", "fallback", "none"],
) -> ResolverResult | None:
    """Run the evaluator for a registered concept and map the scenario tree
    into a ``ResolverResult``. Returns ``None`` if the evaluator can't size it
    (e.g. the concept has no applicable framework variants) so the caller can
    fall back to its PARTIAL path.
    """
    try:
        tam = size_concept(registry, concept_slug)
    except Exception:  # EvaluatorError / RegistryError — best-effort, fall back
        _log.warning("step 2b evaluator failed for %s", concept_slug, exc_info=True)
        return None

    scenarios = tam.scenarios
    if not scenarios:
        return None
    primary = scenarios[0]
    inputs_used = [
        {
            "slug": iu.primitive_slug,
            "name": iu.name,
            "value": iu.value,
            "unit": iu.unit.model_dump() if iu.unit is not None else None,
        }
        for iu in primary.inputs_used
    ]
    # A concept that spans ≥2 method families is a triangulated estimate; one
    # framework (or one family) is single_method and earns an honesty banner.
    triangulated = len(tam.method_families_used) >= 2
    scenario_tree = _scenario_tree(registry, tam.scenarios, triangulated=triangulated)
    return ResolverResult(
        status=PipelineStatus.OK,
        via=via,
        estimate_kind="triangulated" if triangulated else "single_method",
        scenarios=scenario_tree,
        tam_value=primary.value,
        formatted_tam=_format_usd(primary.value),
        concept_name=tam.target.concept_name,
        lens=primary.lens.value,
        framework_name=primary.framework,
        independence_score=tam.independence_score,
        primitives_used=inputs_used,
        banner=None if triangulated else "single method family — not yet triangulated",
        events=state.events,
    )


def _scenario_tree(registry: Registry, scenarios: Any, *, triangulated: bool) -> list[ScenarioLite]:
    """Map evaluator ``Scenario`` objects into the wire-level ``ScenarioLite``
    tree (AC0.2). ``method`` is the framework's method_family so the UI can show
    method spread; ``label`` is the variant scope (or framework slug)."""
    tree: list[ScenarioLite] = []
    for s in scenarios:
        try:
            method = registry.get_framework(s.framework).method_family.value
        except RegistryError:
            method = s.lens.value
        tree.append(
            ScenarioLite(
                label=s.framework_variant or s.framework,
                value=s.value,
                method=method,
                framework=s.framework,
                triangulated=triangulated,
            )
        )
    return tree


def _step3_connector(state: _RunState, query: str, options: RunOptions) -> ResolverResult | None:
    """Router → connector dispatch → writer.upsert.

    The router (``strata.router.choose``) picks one or more connector methods.
    Each is dispatched via ``connectors._dispatch.call_and_convert`` and the
    resulting AtomicPrimitive YAML is persisted with ``writer.upsert_primitive``
    (auto-primitives only — never the committed tree). Independent calls run
    concurrently, capped at ``options.expansion_budget``.

    Returns ``None`` on *any* failure (router miss, dispatch error, writer
    error) so the caller falls through to the step-4 fallback unchanged.
    """
    decisions = _route(state, query, options)
    if not decisions:
        return None

    budget = max(1, options.expansion_budget)
    if len(decisions) > budget:
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.BUDGET_EXCEEDED,
                step="3",
                payload={"budget": budget, "requested": len(decisions)},
            ),
        )
        decisions = decisions[:budget]

    try:
        primitives = asyncio.run(_dispatch_all(state, decisions))
    except Exception:
        _log.warning("step 3 connector dispatch failed", exc_info=True)
        return None

    if not primitives:
        return None

    primitives_used: list[dict[str, Any]] = []
    for prim_yaml in primitives:
        slug = str(prim_yaml.get("slug", ""))
        if slug:
            state.wrote_primitives.append(slug)
        primitives_used.append(
            {
                "slug": slug,
                "name": prim_yaml.get("name"),
                "value": prim_yaml.get("value"),
                "unit": prim_yaml.get("unit"),
            }
        )

    return ResolverResult(
        status=PipelineStatus.OK if len(primitives_used) > 1 else PipelineStatus.PARTIAL,
        via="connector",
        primitives_used=primitives_used,
        wrote_primitives=list(state.wrote_primitives),
        banner=(
            "pulled live from connector(s); written to ~/.strata/auto-primitives/ "
            "— promote with `strata promote <slug>` to cite."
        ),
        events=state.events,
    )


def _route(state: _RunState, query: str, options: RunOptions) -> list[Any]:
    """Call the router and normalise its return to a list of decisions.

    ``router.choose`` historically returns a single ``RoutingDecision | None``;
    a list is also accepted so the router can grow multi-pick. Emits a
    ROUTER_DECISION event per decision.
    """
    try:
        import importlib

        router_mod = importlib.import_module("strata.router")
        raw = router_mod.choose(query, model=options.model)
    except Exception as exc:
        _log.warning("router.choose failed", exc_info=True)
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.ERROR,
                step="3",
                payload={"step": "router", "error": exc.__class__.__name__},
                message=str(exc),
            ),
        )
        return []

    if raw is None:
        return []
    is_seq = isinstance(raw, list | tuple)
    decisions: list[Any] = cast("list[Any]", raw) if is_seq else [raw]
    for decision in decisions:
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.ROUTER_DECISION,
                step="3",
                payload=decision.model_dump(),
            ),
        )
    return decisions


async def _dispatch_all(state: _RunState, decisions: list[Any]) -> list[dict[str, Any]]:
    """Dispatch every decision concurrently; return the primitive YAMLs that
    succeeded. Individual failures are swallowed so a partial batch still
    yields results.
    """
    results = await asyncio.gather(
        *(_dispatch_one(state, d) for d in decisions),
        return_exceptions=True,
    )
    out: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, dict):
            out.append(r)
        else:
            _log.warning("connector dispatch failed for one decision", exc_info=r)
    return out


async def _dispatch_one(state: _RunState, decision: Any) -> dict[str, Any]:
    """Call one connector method off the event loop, persist, emit events."""
    connector = decision.connector
    method = decision.method
    args = dict(decision.args)

    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.CONNECTOR_CALL,
            step="3",
            payload={"connector": connector, "method": method, "args": args},
        ),
    )

    prim_yaml = await asyncio.to_thread(call_and_convert, connector, method, args)
    path = await asyncio.to_thread(
        writer.upsert_primitive,
        primitive_yaml=prim_yaml,
        connector=connector,
        method=method,
        args=args,
    )
    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.WROTE_PRIMITIVE,
            step="3",
            payload={"slug": prim_yaml.get("slug"), "path": str(path)},
        ),
    )
    return prim_yaml


def _step4_fallback(
    state: _RunState,
    query: str,
    options: RunOptions,
    *,
    parse_fn: ParseFn,
    search_fn: SearchFn,
) -> ResolverResult:
    """Synthesize via Claude+Exa. Ephemeral — never written to disk.

    This step exists so the product gives a best-effort answer for markets
    that haven't been curated yet, while the banner makes clear the result
    hasn't been reviewed.  Results stay out of the data bank until a human
    runs ``strata promote <slug>``.
    """
    try:
        parsed = parse_fn(query, model=options.model)
    except Exception as exc:
        _log.warning("fallback parse_query failed", exc_info=True)
        return ResolverResult(
            status=PipelineStatus.FAILED,
            via="none",
            events=state.events,
            error=f"fallback parse failed: {exc.__class__.__name__}",
        )

    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.FRAMEWORK_SELECTED,
            step="4",
            payload={"framework": parsed.lens, "lens": parsed.lens},
        ),
    )

    hits: list[dict[str, Any]] = []
    for prim_spec in parsed.primitives_needed:
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.SEARCHING,
                step="4",
                payload={"primitive_name": prim_spec.role, "role": prim_spec.role},
            ),
        )
        hit = search_fn(prim_spec, model=options.model)
        if hit is None:
            continue
        hits.append(hit.model_dump())

    if len(hits) < 2:
        return ResolverResult(
            status=PipelineStatus.FAILED,
            via="fallback",
            events=state.events,
            error="not enough primitives synthesized via fallback",
        )

    # AC1.6: refuse to emit a TAM from a dimensionally-invalid multiply (two
    # currency factors, or none) instead of silently producing a wrong number.
    try:
        assert_multipliable([h.get("unit") for h in hits])
    except UnitMismatchError as exc:
        return ResolverResult(
            status=PipelineStatus.FAILED,
            via="fallback",
            events=state.events,
            error=f"unit guard: {exc}",
        )

    tam_value = 1.0
    for h in hits:
        tam_value *= float(h["value"])

    return ResolverResult(
        status=PipelineStatus.OK,
        via="fallback",
        estimate_kind="single_method",
        scenarios=[
            ScenarioLite(
                label=parsed.lens.replace("_", " ").title(),
                value=tam_value,
                method=parsed.lens,
                framework=parsed.lens.replace("_", " ").title(),
                triangulated=False,
            )
        ],
        tam_value=tam_value,
        formatted_tam=_format_usd(tam_value),
        concept_name=parsed.concept_name,
        definition=parsed.definition,
        lens=parsed.lens,
        framework_name=parsed.lens.replace("_", " ").title(),
        independence_score=0.0,
        primitives_used=hits,
        banner="synthesized via fallback — not in data bank, do not cite without manual verification",
        events=state.events,
    )


def _format_usd(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def run(
    query: str,
    *,
    registry: Registry,
    options: RunOptions | None = None,
    slug_fn: SlugFn | None = None,
    parse_fn: ParseFn | None = None,
    search_fn: SearchFn | None = None,
) -> ResolverResult:
    """Run the 4-step pipeline. Returns the terminal result with events.

    ``slug_fn`` / ``parse_fn`` / ``search_fn`` are injection seams for the HTTP
    route (which patches its own parse/search functions and skips network slug
    resolution); the CLI leaves them ``None`` to use the full pipeline.
    """

    options = options or RunOptions()
    parse_fn = parse_fn or parse_query
    search_fn = search_fn or search_primitive
    state = _RunState()

    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.PARSING,
            step="pre",
            payload={"query": query, "model": options.model},
        ),
    )

    try:
        if slug_fn is not None:
            resolved = slug_fn(query)
        else:
            resolved = resolve_slug(
                query,
                known_concepts=_summarize_concepts(registry),
                known_primitives=_summarize_primitives(registry),
                model=options.model,
            )
    except Exception as exc:
        _log.warning("slug resolution failed", exc_info=True)
        # If slug resolution fails we go straight to fallback (if allowed).
        resolved = ResolvedQuery(intent=ResolverIntent.NOVEL, confidence=0.0)
        _emit(
            state,
            PipelineEvent(
                kind=PipelineEventKind.ERROR,
                step="pre",
                payload={"step": "slug", "error": exc.__class__.__name__},
                message=str(exc),
            ),
        )

    state.resolved = resolved
    _emit(
        state,
        PipelineEvent(
            kind=PipelineEventKind.SLUG_RESOLVED,
            step="pre",
            payload=resolved.model_dump(),
        ),
    )

    if resolved.confidence >= 0.5:
        result = _step1_concept(state, registry, resolved)
        if result is not None:
            return result
        result = _step2_primitives(state, registry, resolved, options)
        if result is not None:
            return result

    # Step 3 (connector live): router.choose → connector dispatch → writer.
    if options.allow_live:
        result = _step3_connector(state, query, options)
        if result is not None:
            return result

    if options.allow_fallback:
        return _step4_fallback(state, query, options, parse_fn=parse_fn, search_fn=search_fn)

    return ResolverResult(
        status=PipelineStatus.FAILED,
        via="none",
        events=state.events,
        error="no result — registry miss and both --no-live and --no-fallback are set",
    )
