"""Per-request principal for MCP tool handlers.

The MCP SDK's session manager does not thread the ASGI ``scope`` into tool
callbacks, so the authenticated principal can't be passed as an argument. The
auth middleware sets this ``ContextVar`` around the request and the tools read it
— giving write/portfolio tools the caller's real ``org_id`` instead of the
``"default"`` placeholder, and powering ``strata_whoami``.

stdio (local-trust) never sets this; tools fall back to a local default.
"""

from __future__ import annotations

from contextvars import ContextVar

from strata.api.auth import Principal

current_principal: ContextVar[Principal | None] = ContextVar("strata_mcp_principal", default=None)


def current_org_id(default: str = "default") -> str:
    """The caller's org for the in-flight MCP request, or ``default`` over stdio."""
    p = current_principal.get()
    return p.org_id if p is not None else default
