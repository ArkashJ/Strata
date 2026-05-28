"""Dynamic TAM query resolution via LLM + Exa search.

``POST /resolve`` streams SSE events as it parses, searches, and evaluates.

The heavy lifting lives in ``strata.resolver`` so both this HTTP surface
and the new ``strata goal`` CLI share the same pipeline. The wire format
is frozen per spec §9.1 — see ``test_sse_event_contract.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import cast

from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from strata.resolver.parse import ParsedPrimitive, parse_query
from strata.resolver.search import search_primitive

router = APIRouter(tags=["resolve"])

# Load .env — walks up directory tree automatically.
load_dotenv()

FRAMEWORK_TEMPLATES: dict[str, dict[str, str]] = {
    "cost_efficiency": {
        "name": "Bottoms-up cost efficiency",
        "formula": "persona_pool x cost_per_persona",
    },
    "revenue_generation": {
        "name": "Top-down revenue capture",
        "formula": "target_segment x spend_per_target",
    },
    "latent_demand": {
        "name": "Adoption curve latent demand",
        "formula": "addressable_population x adoption_value",
    },
    "platform_throughput": {
        "name": "Throughput take-rate",
        "formula": "volume x take_rate",
    },
    "bundle_consolidation": {
        "name": "Consolidation sum-then-discount",
        "formula": "total_spend x consolidation_rate",
    },
    "productivity_uplift": {
        "name": "Productivity uplift value-split",
        "formula": "persona_count x value_per_persona",
    },
}


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


def _select_framework(lens: str) -> dict[str, str]:
    return FRAMEWORK_TEMPLATES.get(lens, FRAMEWORK_TEMPLATES["cost_efficiency"])


@router.post("/resolve")
async def resolve_query(body: ResolveRequest) -> StreamingResponse:
    async def generate():  # type: ignore[return]
        try:
            # ── parsing event (frozen §9.1) ────────────────────────────
            yield _sse(
                "parsing",
                {"query": body.query, "model": "claude-sonnet-4-20250514"},
            )
            # Backwards-compat ``step`` event for the existing frontend.
            yield _sse(
                "step",
                {"type": "parsing", "message": f'Parsing: "{body.query}"...'},
            )

            try:
                parsed = await asyncio.to_thread(parse_query, body.query)
            except Exception:
                logging.getLogger(__name__).exception("/resolve parse failed")
                yield _sse(
                    "error",
                    {"message": "Failed to parse AI response. Please try again.", "step": "parse"},
                )
                yield _sse("done", {})
                return

            yield _sse(
                "step",
                {
                    "type": "parsed",
                    "lens": parsed.lens,
                    "concept_name": parsed.concept_name,
                    "definition": parsed.definition,
                    "primitives_needed": [p.model_dump() for p in parsed.primitives_needed],
                },
            )

            # ── per-primitive search (frozen §9.1) ─────────────────────
            found_primitives: list[dict[str, object]] = []
            for prim in parsed.primitives_needed:
                prim = cast(ParsedPrimitive, prim)
                yield _sse(
                    "searching",
                    {"primitive_name": prim.role, "role": prim.role},
                )
                yield _sse(
                    "step",
                    {
                        "type": "searching",
                        "role": prim.role,
                        "message": f"Searching for {prim.description}...",
                    },
                )
                hit = await asyncio.to_thread(search_primitive, prim)
                if hit is not None:
                    payload: dict[str, object] = hit.model_dump()
                    found_primitives.append(payload)
                    yield _sse(
                        "step",
                        {
                            "type": "primitive_found",
                            "role": payload["role"],
                            "name": payload["name"],
                            "value": payload["value"],
                            "unit": payload["unit"],
                            "source_url": payload["source_url"],
                            "source_tier": payload.get("source_tier", "community"),
                        },
                    )

            if len(found_primitives) < 2:
                yield _sse(
                    "error",
                    {
                        "message": "Could not find enough market data for this query.",
                        "step": "search",
                    },
                )
                yield _sse("done", {})
                return

            # ── framework_selected (frozen §9.1) ───────────────────────
            framework_info = _select_framework(parsed.lens)
            yield _sse(
                "framework_selected",
                {"framework": parsed.lens, "lens": parsed.lens},
            )
            yield _sse(
                "step",
                {
                    "type": "framework_selected",
                    "name": framework_info["name"],
                    "lens": parsed.lens,
                    "formula": framework_info["formula"],
                },
            )

            # ── evaluating (frozen §9.1) ───────────────────────────────
            yield _sse(
                "evaluating",
                {
                    "inputs": [
                        {"slug": p.get("role"), "value": p["value"], "unit": p["unit"]}
                        for p in found_primitives
                    ]
                },
            )
            yield _sse(
                "step",
                {"type": "evaluating", "message": "Computing TAM scenarios..."},
            )

            tam_value = 1.0
            for p in found_primitives:
                tam_value *= float(p["value"])  # type: ignore[arg-type]

            # ── result (frozen §9.1) ───────────────────────────────────
            yield _sse(
                "result",
                {
                    "tam_usd": tam_value,
                    "scenarios": [{"label": "point", "value": tam_value}],
                    "sources": [
                        {"url": p.get("source_url"), "tier": p.get("source_tier")}
                        for p in found_primitives
                    ],
                    # Extended payload for the existing frontend (additive).
                    "concept_name": parsed.concept_name,
                    "definition": parsed.definition,
                    "tam_value": tam_value,
                    "formatted_tam": _format_usd(tam_value),
                    "lens": parsed.lens,
                    "framework_name": framework_info["name"],
                    "independence_score": 0.0,
                    "primitives_used": found_primitives,
                },
            )

            yield _sse("done", {})

        except Exception:
            logging.getLogger(__name__).exception("resolve failed")
            yield _sse("error", {"message": "An internal error occurred.", "step": "unknown"})
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
