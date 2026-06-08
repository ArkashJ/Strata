"""Per-request principal and trace-session for MCP tool handlers.

The MCP SDK's session manager does not thread the ASGI ``scope`` into tool
callbacks, so the authenticated principal can't be passed as an argument. The
auth middleware sets these ``ContextVar``s around the request and the tools read
them — giving write/portfolio tools the caller's real ``org_id`` instead of the
``"default"`` placeholder, and powering ``strata_whoami``.

``current_trace_session`` carries the trace-session id for grouping captured tool
calls (plan D1).  Over hosted HTTP, ``McpAuthMiddleware`` reads the optional
``X-Strata-Trace-Session`` header and sets it here so every tool call in a
multi-turn agent conversation lands in the same session row.  Over stdio, one
process equals one session: ``run_stdio`` sets the var once at boot.  When absent
(ungrouped hosted call), the var is ``None`` and the trace row is written with
``session_id = NULL`` — a captured-but-ungrouped call is better than a dropped one.

stdio (local-trust) never sets ``current_principal``; tools fall back to a local default.
"""

from __future__ import annotations

from contextvars import ContextVar

from strata.api.auth import Principal

current_principal: ContextVar[Principal | None] = ContextVar("strata_mcp_principal", default=None)

# Trace session id for the in-flight MCP request.  Set by McpAuthMiddleware
# (hosted) or run_stdio (local) — never by the tool handlers themselves.
current_trace_session: ContextVar[str | None] = ContextVar("strata_mcp_trace_session", default=None)


def current_org_id(default: str = "default") -> str:
    """The caller's org for the in-flight MCP request, or ``default`` over stdio."""
    p = current_principal.get()
    return p.org_id if p is not None else default


def current_trace_session_id() -> str | None:
    """The trace-session id for the in-flight MCP request, or ``None`` when unset.

    ``None`` is normal for ungrouped hosted calls (no ``X-Strata-Trace-Session``
    header) — capture still writes the row, just without a session grouping."""
    return current_trace_session.get()
