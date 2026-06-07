"""Wave 5A / AC5A.1 — the MCP server starts and answers tools/list + tools/call.

Uses the SDK's in-memory client⇄server transport (the same machinery stdio /
streamable-HTTP ride on) so the test exercises the real MCP request path without
spawning a subprocess.
"""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from strata.mcp.server import build_server, build_streamable_http_app

# The 5 read-only tools (Wave 5A) + 3 write tools (portfolio P1) + 4 harness
# tools (data-bank expansion: browse, what-if sizing, connector inventory + live)
# + whoami (connection diagnostics) + 2 feedback tools (Phase F: submit/list flags).
_EXPECTED_TOOLS = {
    "whoami",
    "search_concepts",
    "get_primitive",
    "list_frameworks",
    "size_tam",
    "resolve_market",
    "import_portfolio",
    "size_company",
    "list_portfolio",
    "list_primitives",
    "build_tam",
    "list_connectors",
    "get_connector_data",
    "save_primitive",
    "list_my_primitives",
    "get_report",
    "submit_feedback",
    "list_feedback",
    "get_report_for_tam",
    "export_report",
    "verify_market_claim",
}


@pytest.mark.asyncio
async def test_tools_list_advertises_all_tools() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert names == _EXPECTED_TOOLS
        for t in result.tools:
            assert t.inputSchema and t.inputSchema.get("type") == "object"


@pytest.mark.asyncio
async def test_tools_call_returns_sourced_json() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("size_tam", {"concept_slug": "doc-gen-pc-insurance"})
        assert result.content, "tool returned no content"
        text = result.content[0].text  # type: ignore[union-attr]
        payload = json.loads(text)
        assert payload["scenarios"], "size_tam must return a scenario tree"
        # Every input is hash-pinned (sourced contract).
        assert all(inp["snapshot_sha256"] for sc in payload["scenarios"] for inp in sc["inputs"])


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_not_crash() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_primitive", {"slug": "no-such-primitive"})
        assert result.isError
        text = result.content[0].text  # type: ignore[union-attr]
        # Error payload is now the structured taxonomy envelope (code + message).
        err = json.loads(text)["error"]
        assert err["code"] == "PRIMITIVE_NOT_FOUND"
        assert "not found" in err["message"]


def test_streamable_http_app_builds() -> None:
    # The hosted transport (AC5A.1) constructs without error and is an ASGI app.
    app = build_streamable_http_app()
    assert callable(app)
