"""Structured MCP result builder (Phase 0).

``tool_result`` is the single chokepoint that turns a handler's plain dict into
an SDK :class:`~mcp.types.CallToolResult`:

* ``structuredContent`` — the typed payload (validates against the tool's
  ``outputSchema``); ``next_actions`` are embedded here so a driving agent can
  chain follow-up calls (drill down, challenge an assumption, widen scope).
* a ``TextContent`` block — a JSON fallback so text-only hosts (no structured
  support) still see the data.
* zero or more ``resource_link`` content blocks — one-click drill-down to the
  primitive / source / TAM behind each number (Phase 1).

Everything is JSON-sanitized (``json.loads(json.dumps(x, default=str))``) so a
date / enum / Decimal can't break serialization downstream.
"""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types
from pydantic import AnyUrl


def _json_safe(obj: Any) -> Any:
    """Round-trip through JSON so dates/enums/Decimals become plain JSON types."""
    return json.loads(json.dumps(obj, default=str))


def _resource_link(link: dict[str, Any]) -> types.ResourceLink:
    """Build one ResourceLink content block from a plain dict.

    ``uri`` + ``name`` are required by the SDK; the rest are optional drill-down
    metadata. A link missing ``name`` falls back to the uri so the block is still
    valid (an agent can always render the uri)."""
    uri = str(link["uri"])
    return types.ResourceLink(
        type="resource_link",
        uri=AnyUrl(uri),
        name=str(link.get("name") or uri),
        title=link.get("title"),
        description=link.get("description"),
        mimeType=link.get("mimeType"),
    )


def tool_result(
    structured: dict[str, Any],
    *,
    links: list[dict[str, Any]] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
    text: str | None = None,
    is_error: bool = False,
) -> types.CallToolResult:
    """Assemble a ``CallToolResult`` from a handler's structured payload.

    ``next_actions`` is embedded into ``structuredContent`` (not a separate
    protocol field) so it survives to any host and is self-describing. ``links``
    become ``resource_link`` content blocks AND, when present, a compact mirror in
    ``structuredContent["resource_links"]`` so a structured-only consumer sees
    them too. ``text`` overrides the default JSON text fallback.
    """
    payload = dict(structured)
    if next_actions:
        payload["next_actions"] = list(next_actions)
    if links:
        payload["resource_links"] = [
            {k: v for k, v in dict(link).items() if v is not None} for link in links
        ]

    safe = _json_safe(payload)
    content: list[Any] = [
        types.TextContent(type="text", text=text or json.dumps(safe, default=str))
    ]
    # ResourceLink.uri must be an absolute URL (the SDK rejects a relative path).
    # Emit only scheme-qualified URIs (strata://…, https://…) as content blocks;
    # any relative path a handler passes still rides structuredContent.resource_links.
    for link in links or []:
        if "://" in str(link.get("uri", "")):
            content.append(_resource_link(link))

    return types.CallToolResult(
        content=content,
        structuredContent=safe,
        isError=is_error,
    )


__all__ = ["tool_result"]
