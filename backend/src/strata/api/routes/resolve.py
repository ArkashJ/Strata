"""Dynamic TAM query resolution via the shared resolver pipeline.

``POST /resolve`` streams SSE events as the resolver parses, searches, and
evaluates a free-form market query. The heavy lifting lives in
``strata.resolver.pipeline`` so this HTTP surface and the ``strata goal`` CLI
share one engine.

Wire format is frozen per spec §9.1 — see ``test_sse_event_contract.py``. The
six wire-level events are ``parsing``, ``searching``, ``framework_selected``,
``evaluating``, ``result``, ``error`` (plus legacy ``step`` / ``done`` for the
current frontend). The pipeline's CLI-only event kinds (slug_resolved,
concept_hit, primitive_hit, router_decision, connector_call, wrote_primitive,
budget_exceeded) are NEVER emitted to network clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from strata.api.auth import Principal, require_principal
from strata.api.deps import get_registry
from strata.api.ratelimit import enforce_rate_limit
from strata.api.responses import RATE_LIMITED, UNAUTHORIZED, merge
from strata.db.audit import record_audit_safe
from strata.registry import Registry
from strata.resolver import RunOptions, parse_query, run, search_primitive
from strata.resolver.events import PipelineStatus, ResolverResult
from strata.resolver.match import match_concept
from strata.resolver.pipeline import exa_fallback_enabled
from strata.resolver.slug import ResolvedQuery, ResolverIntent

router = APIRouter(tags=["resolve"])

_get_registry = Depends(get_registry)
_require_principal = Depends(require_principal)

# Load .env — walks up directory tree automatically.
load_dotenv()

_log = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"


class ResolveRequest(BaseModel):
    query: str


def _sse(event: str, data: dict[str, object] | str) -> str:
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def _format_usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _registry_first_slug(
    query: str, registry: Registry, *, semantic_slug: str | None = None
) -> ResolvedQuery:
    """Registry-first slug seam (AC0.2): if the query already names a curated
    concept, resolve it to a CONCEPT intent (no LLM round-trip) so the pipeline
    returns the full triangulated scenario tree.

    Order (flow 39): exact/fuzzy ``match_concept`` is PRIMARY; ``semantic_slug``
    (a pgvector NN hit pre-computed in the async route) is a FALLBACK used only
    when the literal matcher misses. On a total miss, fall through to NOVEL → the
    dynamic-synthesis fallback path."""
    slug = match_concept(registry, query)
    if slug is not None:
        return ResolvedQuery(intent=ResolverIntent.CONCEPT, concept_slug=slug, confidence=1.0)
    if semantic_slug is not None and semantic_slug in registry.concepts:
        # Lower confidence than a literal hit: it's a semantic recovery, not an
        # exact name match.
        return ResolvedQuery(
            intent=ResolverIntent.CONCEPT, concept_slug=semantic_slug, confidence=0.7
        )
    return ResolvedQuery(intent=ResolverIntent.NOVEL, confidence=0.0)


async def _semantic_concept_slug(query: str, registry: Registry) -> str | None:
    """pgvector NN fallback (flow 39): only consulted when the literal
    ``match_concept`` would miss. Best-effort — a DB/pgvector failure (e.g. the
    extension/embeddings aren't provisioned yet) degrades silently to ``None`` so
    resolve still works without the semantic layer."""
    if match_concept(registry, query) is not None:
        return None  # literal match wins; don't pay for a DB round-trip.
    # A one-word query is too collision-prone for feature-hashing to match
    # reliably (it can spuriously align with an unrelated concept's hashed
    # tokens); leave those to the LLM/novel path.
    if len(query.split()) < 2:
        return None
    try:
        from strata.db.embeddings import match_concept_semantic
        from strata.db.engine import SessionLocal
        from strata.resolver.embeddings import embed_text

        query_vec = embed_text(query)
        async with SessionLocal() as session:
            return await match_concept_semantic(session, query_vec)
    except Exception:
        _log.debug("semantic concept match unavailable", exc_info=True)
        return None


@router.post(
    "/resolve",
    summary="Resolve a market query (SSE)",
    responses=merge(UNAUTHORIZED, RATE_LIMITED),
)
async def resolve_query(
    body: ResolveRequest,
    registry: Registry = _get_registry,
    principal: Principal = _require_principal,
) -> StreamingResponse:
    """Stream SSE events as the resolver parses and evaluates a market query.

    Requires authentication (API key or Clerk session). Subject to per-org
    rate limiting (429 response).

    Response is text/event-stream with events: ``parsing``, ``searching``,
    ``framework_selected``, ``evaluating``, ``result``, ``error``, ``done``
    (plus legacy ``step`` for frontend compatibility)."""
    # AC3.1/AC3.2: auth resolves the principal (401 if required+missing); the
    # LLM route is token-bucket rate-limited per org (429 + Retry-After).
    enforce_rate_limit(principal.org_id)

    async def generate() -> AsyncIterator[str]:
        # ── parsing event (frozen §9.1) ────────────────────────────────
        yield _sse("parsing", {"query": body.query, "model": _MODEL})
        yield _sse("step", {"type": "parsing", "message": f'Parsing: "{body.query}"...'})

        # Semantic NN fallback (flow 39) — resolved here (async) so the
        # in-thread, sync ``slug_fn`` can consume it without a DB round-trip.
        semantic_slug = await _semantic_concept_slug(body.query, registry)

        try:
            result: ResolverResult = await asyncio.to_thread(
                run,
                body.query,
                registry=registry,
                # Phase 4 fence — the route requests the Exa fallback only when
                # the operator has opted in (STRATA_ALLOW_EXA_FALLBACK=1); otherwise
                # an unresolved query returns an honest 'no curated result'.
                options=RunOptions(
                    allow_live=False, allow_fallback=exa_fallback_enabled(), model=_MODEL
                ),
                slug_fn=lambda q: _registry_first_slug(q, registry, semantic_slug=semantic_slug),
                parse_fn=parse_query,
                search_fn=search_primitive,
            )
        except Exception:
            _log.exception("resolve pipeline failed")
            yield _sse("error", {"message": "An internal error occurred.", "step": "unknown"})
            yield _sse("done", {})
            return

        if result.status is PipelineStatus.FAILED or not result.primitives_used:
            # Distinguish the two known terminal failure shapes for the UI copy.
            # A "fallback parse" failure means the LLM backend itself errored
            # (commonly no API key / exhausted credits), not a transient glitch —
            # say so honestly and point the user at the curated library, which
            # needs no LLM.
            message = (
                "Dynamic resolution is unavailable — the AI backend returned an "
                "error (commonly a missing/expired API key or exhausted credits). "
                "Pick the nearest curated concept below, or retry once a backend "
                "is configured."
                if (result.error or "").startswith("fallback parse")
                else "Could not find enough market data for this query."
            )
            yield _sse("error", {"message": message, "step": "search"})
            yield _sse("done", {})
            return

        primitives = result.primitives_used

        # ── per-primitive search (frozen §9.1) ─────────────────────────
        for p in primitives:
            role = p.get("role")
            name = p.get("name")
            yield _sse("searching", {"primitive_name": role, "role": role})
            yield _sse(
                "step",
                {
                    "type": "primitive_found",
                    "role": role,
                    "name": name,
                    "value": p.get("value"),
                    "unit": p.get("unit"),
                    "source_url": p.get("source_url"),
                    "source_tier": p.get("source_tier", "community"),
                },
            )

        # ── framework_selected (frozen §9.1) ───────────────────────────
        lens = result.lens or "cost_efficiency"
        yield _sse("framework_selected", {"framework": lens, "lens": lens})
        yield _sse(
            "step",
            {
                "type": "framework_selected",
                "name": result.framework_name or lens.replace("_", " ").title(),
                "lens": lens,
            },
        )

        # ── evaluating (frozen §9.1) ───────────────────────────────────
        yield _sse(
            "evaluating",
            {
                "inputs": [
                    {
                        "slug": p.get("role") or p.get("slug"),
                        "value": p.get("value"),
                        "unit": p.get("unit"),
                    }
                    for p in primitives
                ]
            },
        )
        yield _sse("step", {"type": "evaluating", "message": "Computing TAM scenarios..."})

        tam_value = result.tam_value if result.tam_value is not None else 0.0

        # ── result (frozen §9.1) ───────────────────────────────────────
        # The scenario tree (AC0.2/AC0.3): a concept hit carries ≥2 scenarios
        # across method families; the novel path carries a single
        # ``triangulated=false`` scenario. Fall back to a single point only when
        # the pipeline emitted no tree at all.
        scenarios = (
            [s.model_dump() for s in result.scenarios]
            if result.scenarios
            else [{"label": "point", "value": tam_value, "triangulated": False}]
        )
        yield _sse(
            "result",
            {
                "tam_usd": tam_value,
                "estimate_kind": result.estimate_kind,
                "scenarios": scenarios,
                "sources": [
                    {"url": p.get("source_url"), "tier": p.get("source_tier")} for p in primitives
                ],
                # Extended payload for the existing frontend (additive).
                "concept_name": result.concept_name,
                "definition": result.definition,
                "tam_value": tam_value,
                "formatted_tam": result.formatted_tam or _format_usd(tam_value),
                "lens": result.lens,
                "framework_name": result.framework_name,
                "independence_score": result.independence_score,
                "primitives_used": primitives,
                "banner": result.banner,
            },
        )
        await record_audit_safe(
            actor=principal.user_id,
            action="resolve",
            target=result.concept_name or body.query[:128],
            meta={"query": body.query, "lens": result.lens, "tam_value": tam_value},
            org_id=principal.org_id,
        )
        yield _sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
