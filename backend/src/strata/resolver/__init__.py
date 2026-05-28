"""Shared resolver pipeline for both ``POST /resolve`` and ``strata goal``.

The resolver runs a free-form TAM query through a 4-step hybrid retrieval
(spec §3.5):

    pre. slug resolver  — Claude one-shot → ResolvedQuery
    1.   concept match  — registry.concept → evaluator.size_concept
    2.   primitive match — registry.primitive[]  → return value or compose
    3.   connector live — router.choose → connector.method → writer.upsert
    4.   fallback       — resolver.parse_and_search (Claude+Exa, ephemeral)

Each stage emits a ``PipelineEvent`` consumed by the renderer (compact,
streaming SSE, or JSON). Steps 3 & 4 are opt-out via flags / env vars.
"""

from __future__ import annotations

from .events import (
    PipelineEvent,
    PipelineEventKind,
    PipelineStatus,
    ResolverResult,
)
from .parse import ParsedPrimitive, ParsedQuery, parse_query
from .pipeline import RunOptions, run
from .render import RenderMode, render_event, render_result
from .search import PrimitiveHit, search_primitive
from .slug import (
    ConceptSummary,
    PrimitiveSummary,
    ResolvedQuery,
    ResolverIntent,
    resolve_slug,
)
from .writer import AUTO_PRIMITIVES_DIR, upsert_primitive

__all__ = [
    "AUTO_PRIMITIVES_DIR",
    "ConceptSummary",
    "ParsedPrimitive",
    "ParsedQuery",
    "PipelineEvent",
    "PipelineEventKind",
    "PipelineStatus",
    "PrimitiveHit",
    "PrimitiveSummary",
    "RenderMode",
    "ResolvedQuery",
    "ResolverIntent",
    "ResolverResult",
    "RunOptions",
    "parse_query",
    "render_event",
    "render_result",
    "resolve_slug",
    "run",
    "search_primitive",
    "upsert_primitive",
]
