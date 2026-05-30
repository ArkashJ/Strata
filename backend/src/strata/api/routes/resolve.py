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
from strata.db.audit import record_audit_safe
from strata.registry import Registry
from strata.resolver import RunOptions, parse_query, run, search_primitive
from strata.resolver.events import PipelineStatus, ResolverResult
from strata.resolver.match import match_concept
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


def _registry_first_slug(query: str, registry: Registry) -> ResolvedQuery:
    """Registry-first slug seam (AC0.2): if the query already names a curated
    concept, resolve it to a CONCEPT intent (no LLM round-trip) so the pipeline
    returns the full triangulated scenario tree. On a miss, fall through to
    NOVEL → the dynamic-synthesis fallback path."""
    slug = match_concept(registry, query)
    if slug is not None:
        return ResolvedQuery(intent=ResolverIntent.CONCEPT, concept_slug=slug, confidence=1.0)
    return ResolvedQuery(intent=ResolverIntent.NOVEL, confidence=0.0)


@router.post("/resolve")
async def resolve_query(
    body: ResolveRequest,
    registry: Registry = _get_registry,
    principal: Principal = _require_principal,
) -> StreamingResponse:
    # AC3.1/AC3.2: auth resolves the principal (401 if required+missing); the
    # LLM route is token-bucket rate-limited per org (429 + Retry-After).
    enforce_rate_limit(principal.org_id)

    async def generate() -> AsyncIterator[str]:
        # ── parsing event (frozen §9.1) ────────────────────────────────
        yield _sse("parsing", {"query": body.query, "model": _MODEL})
        yield _sse("step", {"type": "parsing", "message": f'Parsing: "{body.query}"...'})

        try:
            result: ResolverResult = await asyncio.to_thread(
                run,
                body.query,
                registry=registry,
                options=RunOptions(allow_live=False, allow_fallback=True, model=_MODEL),
                slug_fn=lambda q: _registry_first_slug(q, registry),
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
            actor=None,
            action="resolve",
            target=result.concept_name or body.query[:128],
            meta={"query": body.query, "lens": result.lens, "tam_value": tam_value},
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
