"""Dynamic TAM query resolution via the shared resolver pipeline.

``POST /resolve`` streams SSE events as the pipeline parses, searches, and
evaluates. The heavy lifting lives in ``strata.resolver.pipeline`` so this HTTP
surface and the ``strata goal`` CLI share one engine.

The wire format is frozen per spec §9.1 — see ``test_sse_event_contract.py``.
Only the six §9.1 events (parsing, searching, framework_selected, evaluating,
result, error) plus the two legacy compatibility events (step, done) ever reach
the network; the pipeline's CLI-only event kinds (slug_resolved, router_decision,
connector_call, ...) are filtered out here.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from strata.loader import LoadedRecords
from strata.registry import Registry
from strata.resolver.events import PipelineEvent, PipelineEventKind, PipelineStatus, ResolverResult

# parse_query / search_primitive are bound here so tests can patch them at
# ``strata.api.routes.resolve.<name>``; the request handler passes the current
# bindings into ``pipeline.run`` so those patches drive the fallback step.
from strata.resolver.parse import parse_query
from strata.resolver.pipeline import RunOptions, run
from strata.resolver.search import search_primitive

router = APIRouter(tags=["resolve"])

# Load .env — walks up directory tree automatically.
load_dotenv()

_log = logging.getLogger(__name__)


class ResolveRequest(BaseModel):
    query: str


def _sse(event: str, data: dict[str, object] | str) -> str:
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def _empty_registry() -> Registry:
    """The HTTP surface has no registry of its own — the pipeline drives results
    through the Claude+Exa fallback, so an empty registry skips the slug step."""
    return Registry.from_loaded(LoadedRecords())


def _searching_events(result: ResolverResult) -> list[PipelineEvent]:
    return [e for e in result.events if e.kind is PipelineEventKind.SEARCHING]


def _framework_event(result: ResolverResult) -> PipelineEvent | None:
    for e in result.events:
        if e.kind is PipelineEventKind.FRAMEWORK_SELECTED:
            return e
    return None


def _result_payload(result: ResolverResult) -> dict[str, Any]:
    """Frozen §9.1 result shape plus the additive fields the frontend reads."""
    primitives = result.primitives_used
    return {
        "tam_usd": result.tam_value,
        "scenarios": [{"label": "point", "value": result.tam_value}],
        "sources": [{"url": p.get("source_url"), "tier": p.get("source_tier")} for p in primitives],
        # Additive payload for the existing frontend.
        "concept_name": result.concept_name,
        "definition": result.definition,
        "tam_value": result.tam_value,
        "formatted_tam": result.formatted_tam,
        "lens": result.lens,
        "framework_name": result.framework_name,
        "independence_score": result.independence_score,
        "primitives_used": primitives,
    }


def _user_facing_error(result: ResolverResult) -> dict[str, object]:
    """Translate an internal pipeline failure into a safe client message.

    Never leak raw exception text. A fallback that parsed but found <2 inputs is
    a data-coverage miss; anything else (parse blew up, etc.) is an internal
    error the user can retry.
    """
    err = (result.error or "").lower()
    if "not enough primitives" in err:
        return {
            "message": "Could not find enough market data for this query.",
            "step": "search",
        }
    if "fallback parse failed" in err:
        return {
            "message": "Failed to parse AI response. Please try again.",
            "step": "parse",
        }
    return {"message": "An internal error occurred.", "step": "unknown"}


@router.post("/resolve")
async def resolve_query(body: ResolveRequest) -> StreamingResponse:
    async def generate():  # type: ignore[return]
        try:
            # Open with the frozen ``parsing`` event followed by the legacy
            # ``step`` the current frontend still listens for. Emitted before the
            # pipeline runs so the wire always opens with ``parsing``.
            yield _sse("parsing", {"query": body.query, "model": RunOptions().model})
            yield _sse("step", {"type": "parsing", "message": f'Parsing: "{body.query}"...'})

            # Inject this module's parse/search bindings so test patches on
            # ``strata.api.routes.resolve.*`` reach the pipeline's fallback step.
            options = RunOptions(allow_live=False)
            result = await asyncio.to_thread(
                run,
                body.query,
                registry=_empty_registry(),
                options=options,
                parse_fn=parse_query,
                search_fn=search_primitive,
            )

            if result.status is PipelineStatus.FAILED:
                yield _sse("error", _user_facing_error(result))
                yield _sse("done", {})
                return

            # Canonical lifecycle order (the pipeline emits framework before
            # search in its fallback step; the wire contract is search → framework
            # → evaluating → result).
            for ev in _searching_events(result):
                role = ev.payload.get("role") or ev.payload.get("primitive_name")
                yield _sse("searching", {"primitive_name": role, "role": role})

            fw = _framework_event(result)
            lens = result.lens or (fw.payload.get("lens") if fw else None)
            yield _sse("framework_selected", {"framework": lens, "lens": lens})

            yield _sse(
                "evaluating",
                {
                    "inputs": [
                        {"slug": p.get("role") or p.get("slug"), "value": p.get("value")}
                        for p in result.primitives_used
                    ]
                },
            )

            yield _sse("result", _result_payload(result))
            yield _sse("done", {})

        except Exception:
            _log.exception("resolve failed")
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
