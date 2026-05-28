"""4-step hybrid retrieval pipeline (spec §3, §3.5).

This is the engine both the HTTP route and the CLI subcommand call into.
It emits a stream of ``PipelineEvent``s and a terminal ``ResolverResult``.

    pre.  resolve_slug   → ResolvedQuery
    1.    concept hit    → registry.concept → evaluator.size_concept
    2.    primitive(s)   → registry.primitive[] (single or compose)
    3.    connector live → router.choose → connector.method → writer.upsert
    4.    fallback       → parse + search (Claude+Exa) → ephemeral result

Steps 3 and 4 are opt-out via RunOptions. The CLI maps STRATA_OFFLINE=1
to ``allow_live=False, allow_fallback=False``.

The router is loaded lazily inside step 3 to keep ``import strata.resolver``
fast for paths that don't need it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..models import AtomicPrimitive
from ..registry import Registry
from .events import PipelineEvent, PipelineEventKind, PipelineStatus, ResolverResult
from .parse import parse_query
from .search import search_primitive
from .slug import (
    ConceptSummary,
    PrimitiveSummary,
    ResolvedQuery,
    ResolverIntent,
    resolve_slug,
)

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class RunOptions:
    """Pipeline knobs. CLI flags + env vars surface through this struct."""

    allow_live: bool = True
    allow_fallback: bool = True
    expansion_budget: int = 6
    primitive_only: bool = False
    model: str = "claude-sonnet-4-20250514"


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
    # Evaluator integration is fully covered by the existing /c /size paths.
    # Step 1 returns a partial result that the renderer can finalise — the
    # CLI calls into evaluator.size_concept itself for the scenario tree.
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

    # Multi-primitive: framework hint composition is deferred to PR-B.3 where the
    # CLI evaluator wiring lives. We return primitives_used so the renderer can
    # at least show them; banner explains the deferred composition.
    return ResolverResult(
        status=PipelineStatus.PARTIAL,
        via="primitive",
        primitives_used=[
            {
                "slug": p.slug,
                "name": p.name,
                "value": p.value,
                "unit": p.unit.model_dump(),
            }
            for p in hits
        ],
        framework_name=resolved.framework_hint,
        banner=(
            "matched multiple primitives; framework composition not yet wired "
            "for free-form queries — run `strata size <concept-slug>` for a "
            "fully-composed TAM."
        ),
        events=state.events,
    )


def _step4_fallback(state: _RunState, query: str, options: RunOptions) -> ResolverResult:
    """Synthesize via Claude+Exa. Ephemeral — never written to disk."""
    try:
        parsed = parse_query(query, model=options.model)
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
        hit = search_primitive(prim_spec, model=options.model)
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

    tam_value = 1.0
    for h in hits:
        tam_value *= float(h["value"])

    return ResolverResult(
        status=PipelineStatus.OK,
        via="fallback",
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
) -> ResolverResult:
    """Run the 4-step pipeline. Returns the terminal result with events."""

    options = options or RunOptions()
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

    # Step 3 (connector live): defers to PR-B.2 router. The router lives in
    # strata.router but is imported lazily to avoid pulling Anthropic on the
    # import path for offline tools.
    if options.allow_live:
        try:
            import importlib

            router_mod = importlib.import_module("strata.router")
            decision = router_mod.choose(query)
        except Exception as exc:
            _log.warning("router.choose failed", exc_info=True)
            decision = None
            _emit(
                state,
                PipelineEvent(
                    kind=PipelineEventKind.ERROR,
                    step="3",
                    payload={"step": "router", "error": exc.__class__.__name__},
                    message=str(exc),
                ),
            )
        if decision is not None:
            _emit(
                state,
                PipelineEvent(
                    kind=PipelineEventKind.ROUTER_DECISION,
                    step="3",
                    payload=decision.model_dump(),
                ),
            )
            # Actual connector dispatch + writer.upsert is wired in PR-B.3 once
            # the CLI plumbing exists. For now we surface the decision so the
            # caller sees what would have run.

    if options.allow_fallback:
        return _step4_fallback(state, query, options)

    return ResolverResult(
        status=PipelineStatus.FAILED,
        via="none",
        events=state.events,
        error="no result — registry miss and both --no-live and --no-fallback are set",
    )
