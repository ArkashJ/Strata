"""Phase 3 / Workstream A — the hosted /mcp transport now requires an API key.

Unit-tests the pure-ASGI McpAuthMiddleware (401/429/forward/meter) and an
integration check that create_app() actually wraps the /mcp mount."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from strata.api import mcp_auth
from strata.api.auth import principal_for_headers, register_key
from strata.api.mcp_auth import McpAuthMiddleware


def _scope(headers: dict[str, str] | None = None) -> dict[str, Any]:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return {"type": "http", "method": "POST", "path": "/", "headers": raw}


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


class _Sink:
    """Captures ASGI send messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    @property
    def status(self) -> int:
        return next(m["status"] for m in self.sent if m["type"] == "http.response.start")

    @property
    def body(self) -> dict[str, Any]:
        raw = next(m["body"] for m in self.sent if m["type"] == "http.response.body")
        return json.loads(raw)


class _Inner:
    """A stand-in for the wrapped MCP app; records if/how it was called and
    emits a response with a configurable status so metering can be exercised."""

    def __init__(self, status: int = 200) -> None:
        self.called = False
        self.scope: dict[str, Any] | None = None
        self._status = status

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.called = True
        self.scope = scope
        if scope.get("type") == "http":
            await send({"type": "http.response.start", "status": self._status, "headers": []})
            await send({"type": "http.response.body", "body": b"{}", "more_body": False})


# --------------------------------------------------------------------------- #
# principal_for_headers — the transport-agnostic resolver
# --------------------------------------------------------------------------- #
def test_headers_require_forces_key() -> None:
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({}, require=True)
    assert exc.value.status_code == 401
    assert "missing" in str(exc.value.detail).lower()


def test_headers_invalid_key_401() -> None:
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"x-api-key": "nope"}, require=True)
    assert exc.value.status_code == 401
    assert "invalid" in str(exc.value.detail).lower()


def test_headers_valid_key_resolves() -> None:
    register_key("p3-auth-test-key", "acme-org")
    p = principal_for_headers({"x-api-key": "p3-auth-test-key"}, require=True)
    assert p.org_id == "acme-org"


# --------------------------------------------------------------------------- #
# McpAuthMiddleware — the ASGI gate
# --------------------------------------------------------------------------- #
async def test_mcp_missing_key_401() -> None:
    inner = _Inner()
    sink = _Sink()
    await McpAuthMiddleware(inner)(_scope(), _receive, sink)
    assert sink.status == 401
    assert not inner.called  # gated before the MCP app


async def test_mcp_valid_key_forwards_and_meters(monkeypatch: pytest.MonkeyPatch) -> None:
    register_key("p3-fwd-key", "fwd-org")
    recorded: list[tuple[str, str]] = []

    class _Meter:
        def record(self, org_id: str, route: str) -> None:
            recorded.append((org_id, route))

    monkeypatch.setattr(mcp_auth, "get_meter", lambda: _Meter())

    inner = _Inner()
    sink = _Sink()
    await McpAuthMiddleware(inner)(_scope({"x-api-key": "p3-fwd-key"}), _receive, sink)
    assert inner.called
    assert inner.scope is not None
    assert inner.scope["state"]["principal"].org_id == "fwd-org"
    assert recorded == [("fwd-org", "/mcp")]  # metered once on the 200 response


async def test_mcp_inner_failure_not_metered(monkeypatch: pytest.MonkeyPatch) -> None:
    # A malformed MCP request the session manager rejects (4xx) must not inflate usage.
    register_key("p3-fail-key", "fail-org")
    recorded: list[tuple[str, str]] = []

    class _Meter:
        def record(self, org_id: str, route: str) -> None:
            recorded.append((org_id, route))

    monkeypatch.setattr(mcp_auth, "get_meter", lambda: _Meter())
    inner = _Inner(status=400)
    sink = _Sink()
    await McpAuthMiddleware(inner)(_scope({"x-api-key": "p3-fail-key"}), _receive, sink)
    assert inner.called
    assert recorded == []  # 4xx inner response → no meter


async def test_mcp_rate_limited_429(monkeypatch: pytest.MonkeyPatch) -> None:
    register_key("p3-rl-key", "rl-org")

    def _boom(_org: str) -> None:
        raise HTTPException(
            status_code=429, detail="rate limit exceeded", headers={"Retry-After": "1"}
        )

    monkeypatch.setattr(mcp_auth, "enforce_rate_limit", _boom)
    inner = _Inner()
    sink = _Sink()
    await McpAuthMiddleware(inner)(_scope({"x-api-key": "p3-rl-key"}), _receive, sink)
    assert sink.status == 429
    assert not inner.called


async def test_non_http_scope_passes_through() -> None:
    inner = _Inner()
    sink = _Sink()
    await McpAuthMiddleware(inner)({"type": "lifespan"}, _receive, sink)
    assert inner.called  # lifespan/websocket scopes are never gated


# --------------------------------------------------------------------------- #
# Integration — the mount is actually wrapped
# --------------------------------------------------------------------------- #
async def test_mounted_mcp_requires_key() -> None:
    from strata.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    # follow_redirects mirrors a real client: POST /mcp 307→/mcp/ (the mount), where
    # the auth wrapper runs. Hit the mounted path directly to land on the gate.
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        resp = await client.post("/mcp/", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
    # The wrapper rejects before the MCP session manager — a clean 401, not a
    # half-open stream. If the mount were unwrapped this would be an MCP protocol
    # response, never a 401 from our auth layer.
    assert resp.status_code == 401
    assert "key" in resp.json().get("error", "").lower()
