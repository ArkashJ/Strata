"""Strata MCP server — expose the curated data bank + evaluator to any MCP
client (Claude Desktop, IDE agents) as sourced, hash-pinned market numbers.

The tool *logic* lives in ``tools.py`` (pure, read-only, no SDK import) so it is
unit-testable without a transport; ``server.py`` is the thin MCP SDK wrapper
(stdio + streamable-HTTP ASGI mount).
"""

from __future__ import annotations

from .tools import TOOLS, ToolError, call_tool

__all__ = ["TOOLS", "ToolError", "call_tool"]
