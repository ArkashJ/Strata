"""Input JSON Schemas for the Strata MCP tools (AC5A.2).

Kept separate from the handlers so the schema set is the single source of truth
for both the MCP ``tools/list`` advertisement and any client codegen.
"""

from __future__ import annotations

from typing import Any

SEARCH_CONCEPTS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Free-text market / concept query."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    },
    "required": ["query"],
    "additionalProperties": False,
}

GET_PRIMITIVE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slug": {"type": "string", "description": "Atomic-primitive slug."},
    },
    "required": ["slug"],
    "additionalProperties": False,
}

LIST_FRAMEWORKS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

SIZE_TAM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concept_slug": {"type": "string", "description": "Exact curated concept slug."},
        "query": {"type": "string", "description": "Free-text query (registry-matched)."},
    },
    "additionalProperties": False,
}

RESOLVE_MARKET: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Free-text market query."},
    },
    "required": ["query"],
    "additionalProperties": False,
}
