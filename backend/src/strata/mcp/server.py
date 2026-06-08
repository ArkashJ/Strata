"""Strata MCP server wrapper (AC5A.1).

Thin adapter over the official ``mcp`` SDK: advertises the five read-only tools
from ``tools.TOOLS`` and dispatches ``tools/call`` to ``tools.call_tool``. Two
transports:

* **stdio** (local-trust) — ``python -m strata.mcp.server --stdio`` or the
  ``strata-mcp`` console script. This is what ``claude mcp add`` launches.
* **streamable HTTP** (hosted) — ``build_streamable_http_app()`` returns an ASGI
  app mounted at ``/mcp`` on the FastAPI server, wrapped by ``McpAuthMiddleware``
  (Phase 3 / Workstream A) so every hosted request requires an ``X-API-Key``.
  The stdio transport above stays local-trust (it never instantiates the wrapper).

The registry is loaded read-only from YAML (dev) or Postgres (prod), mirroring
``api.deps``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import inspect
import sys
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from ..config import settings
from ..loader import load_data_dir
from ..registry import Registry
from . import schemas
from .errors import ToolError
from .prompts import register_prompts
from .resources import register_resources
from .result import tool_result
from .tools import TOOLS, call_tool

_SERVER_NAME = "strata"

# A boot-frozen registry made saved primitives / fresh ingest invisible (#97/#98).
# Cache the on-disk YAML load with a short TTL so a long-lived stdio process picks
# up data changes without a restart, while a tight loop of calls still shares one
# load. The HTTP transport prefers the API's shared app.state.registry (app.py),
# so this TTL only governs the stdio / fallback path.
_REGISTRY_TTL_SECONDS = 30.0
_registry_cache: Registry | None = None
_registry_loaded_at: float = 0.0


def _data_root() -> Path:
    root = Path(settings.data_dir)
    if not root.is_absolute():
        # Mirror api.deps: backend/src/strata/mcp/server.py -> parents[4] == repo root.
        root = Path(__file__).resolve().parents[4] / root
    return root


def load_registry() -> Registry:
    """Build a read-only registry from on-disk YAML, cached with a short TTL so a
    saved primitive / fresh ingest becomes visible without a process restart."""
    global _registry_cache, _registry_loaded_at
    now = time.monotonic()
    if _registry_cache is not None and (now - _registry_loaded_at) < _REGISTRY_TTL_SECONDS:
        return _registry_cache
    _registry_cache = Registry.from_loaded(load_data_dir(_data_root()))
    _registry_loaded_at = now
    return _registry_cache


def invalidate_registry_cache() -> None:
    """Force the next ``load_registry`` to re-read from disk (e.g. after a write)."""
    global _registry_cache, _registry_loaded_at
    _registry_cache = None
    _registry_loaded_at = 0.0


def build_server(get_registry: Callable[[], Registry] = load_registry) -> Server:
    """Build the MCP server. ``get_registry`` is resolved per ``tools/call`` so
    the API-mounted instance can share the live (prod: DB-loaded) registry rather
    than the on-disk YAML — see ``build_streamable_http_app`` / ``app.py``."""
    server: Server = Server(_SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:  # pyright: ignore[reportUnusedFunction]
        return [
            types.Tool(
                name=name,
                description=spec["description"],
                inputSchema=spec["inputSchema"],
                outputSchema=schemas.OUTPUT_SCHEMAS.get(name),
                annotations=(
                    types.ToolAnnotations(**spec["annotations"])
                    if spec.get("annotations")
                    else None
                ),
            )
            for name, spec in TOOLS.items()
        ]

    @server.call_tool()
    async def _call_tool(  # pyright: ignore[reportUnusedFunction]
        name: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        reg = get_registry()
        status = "ok"
        # result_view is the JSON-serializable dict the tracer hashes/summarizes:
        # the plain dict a handler returned when available, else a minimal stable
        # view derived from the CallToolResult (so replay has a comparable signal).
        result_view: dict[str, Any]
        t0 = time.monotonic()
        try:
            result = call_tool(reg, name, arguments)
            # Write/read DB tools return a coroutine — await it on this loop (the
            # same loop the async engine is bound to, mirroring the HTTP routes).
            if inspect.isawaitable(result):
                result = await result
        except ToolError as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            status = "error"
            payload = exc.to_payload()
            out = tool_result(payload, is_error=True)
            result_view = payload
        else:
            duration_ms = int((time.monotonic() - t0) * 1000)
            # A handler may return a fully-built CallToolResult (the result-aware
            # tools) or a plain dict (wrap it). A dict carrying a top-level
            # "error" is an in-band failure → mark the result isError.
            if isinstance(result, types.CallToolResult):
                out = result
                if out.isError:
                    status = "error"
                # No plain dict to hash; prefer the structured content the SDK
                # carries, else a minimal stable view of the error flag.
                sc = out.structuredContent
                result_view = sc if isinstance(sc, dict) else {"isError": out.isError}
            else:
                dict_result: dict[str, Any] = result
                is_err = "error" in dict_result
                status = "error" if is_err else "ok"
                out = tool_result(dict_result, is_error=is_err)
                result_view = dict_result
        await _audit_call(name, arguments, status)
        await _trace_call(name, arguments, status, result_view, duration_ms)
        return out

    register_resources(server, get_registry)
    register_prompts(server)
    return server


async def _audit_call(name: str, arguments: dict[str, Any], status: str) -> None:
    """Best-effort per-call audit (Phase 2 / A4). Args are hashed, never stored
    verbatim, so the trail records WHAT ran without leaking inputs. Never raises
    into the call path — an audit failure must not break the tool."""
    try:
        from ..db.audit import record_audit_safe
        from .context import current_org_id, current_principal

        principal = current_principal.get()
        args_hash = hashlib.sha256(repr(sorted(arguments.items())).encode()).hexdigest()[:16]
        await record_audit_safe(
            actor=(principal.key_id if principal is not None else None),
            action=f"mcp.{name}",
            target=str(arguments.get("concept_slug") or arguments.get("slug") or "") or None,
            meta={"status": status, "args_hash": args_hash},
            org_id=current_org_id(),
        )
    except Exception:  # audit is best-effort; never break the tool call
        pass


async def _trace_call(
    name: str,
    arguments: dict[str, Any],
    status: str,
    result: dict[str, Any],
    duration_ms: int,
) -> None:
    """Best-effort trace capture of a tool call (Phase 2, plan #6). Gated off by
    default — when ``trace_capture_enabled`` is False this returns before any
    import or DB work, so behaviour is byte-identical to before (AC-1.5).

    Unlike ``_audit_call`` (which hashes args), trace-capture keeps real args +
    a result summary because replay needs the inputs (privacy trade D4). The
    whole body is guarded — capture must never break or slow a real tool call."""
    if not settings.trace_capture_enabled:
        return
    try:
        from ..db.traces import record_trace_safe
        from ..models.trace import TraceStatus
        from .context import current_org_id, current_trace_session_id

        await record_trace_safe(
            org_id=current_org_id(),
            session_id=current_trace_session_id(),
            tool=name,
            args=arguments,
            result=result,
            status=TraceStatus(status),
            duration_ms=duration_ms,
        )
    except Exception:  # capture is fire-and-forget; never break the tool call
        pass


async def run_stdio() -> None:
    from mcp.server.stdio import stdio_server

    from .context import current_trace_session

    server = build_server()
    # One stdio process is one trace session (plan D1): set a process-stable id
    # once so a local run's calls group together. Sequence numbers order them.
    current_trace_session.set(uuid.uuid4().hex)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def build_streamable_http_app(get_registry: Callable[[], Registry] = load_registry) -> Any:
    """ASGI app for the hosted transport, with its session-manager lifespan.

    Mounted at ``/mcp`` by the FastAPI app. Stateless so each request is
    self-contained (no server-side session affinity needed behind a load
    balancer). ``get_registry`` lets the API share its live registry (prod: DB)."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount

    server = build_server(get_registry)
    manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)

    async def _handle(scope: Any, receive: Any, send: Any) -> None:
        await manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def _lifespan(_app: Starlette) -> AsyncGenerator[None]:
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/", app=_handle)], lifespan=_lifespan)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strata-mcp", description=__doc__)
    parser.add_argument("--stdio", action="store_true", help="run over stdio (default)")
    parser.parse_args(argv)
    # stdio is the only CLI transport; the HTTP transport is mounted on the API.
    asyncio.run(run_stdio())
    return 0


if __name__ == "__main__":
    sys.exit(main())
