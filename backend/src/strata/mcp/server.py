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
import json
import sys
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from ..config import settings
from ..loader import load_data_dir
from ..registry import Registry
from .tools import TOOLS, ToolError, call_tool

_SERVER_NAME = "strata"

_registry_cache: Registry | None = None


def load_registry() -> Registry:
    """Build a read-only registry. Cached per process (the MCP surface never
    mutates it, so one load is safe)."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    root = Path(settings.data_dir)
    if not root.is_absolute():
        # Mirror api.deps: backend/src/strata/mcp/server.py -> parents[4] == repo root.
        root = Path(__file__).resolve().parents[4] / root
    _registry_cache = Registry.from_loaded(load_data_dir(root))
    return _registry_cache


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
            )
            for name, spec in TOOLS.items()
        ]

    @server.call_tool()
    async def _call_tool(  # pyright: ignore[reportUnusedFunction]
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        reg = get_registry()
        try:
            result = call_tool(reg, name, arguments)
        except ToolError as exc:
            result = {"error": str(exc)}
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def run_stdio() -> None:
    from mcp.server.stdio import stdio_server

    server = build_server()
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
