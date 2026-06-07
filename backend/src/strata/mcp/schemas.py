"""Input JSON Schemas for the Strata MCP tools (AC5A.2).

Kept separate from the handlers so the schema set is the single source of truth
for both the MCP ``tools/list`` advertisement and any client codegen.
"""

from __future__ import annotations

from typing import Any

WHOAMI: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

SEARCH_CONCEPTS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Free-text market / concept query."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        "offset": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Skip this many matches (pagination).",
        },
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
    # Exactly one of concept_slug / query — a client must supply one.
    "minProperties": 1,
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

LIST_PRIMITIVES: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tier": {
            "type": "string",
            "description": "Filter by source tier (e.g. regulator, aggregator, community-modeled).",
        },
        "dimension": {
            "type": "string",
            "description": "Filter by unit dimension (e.g. people, currency, organizations).",
        },
        "query": {"type": "string", "description": "Substring match on slug / name."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        "offset": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Skip this many rows (pagination).",
        },
    },
    "additionalProperties": False,
}

BUILD_TAM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concept_slug": {"type": "string", "description": "Exact curated concept slug."},
        "primitive_overrides": {
            "type": "object",
            "description": (
                "What-if: map a primitive slug → a scalar value. Never persisted; "
                "the result carries a user_override banner."
            ),
            "additionalProperties": {"type": "number"},
        },
        "framework_assumptions": {
            "type": "object",
            "description": (
                "Re-point a framework input to a different EXISTING primitive slug: "
                "{framework_slug: {input_name: primitive_slug}}."
            ),
        },
    },
    "required": ["concept_slug"],
    "additionalProperties": False,
}

LIST_CONNECTORS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tier": {"type": "string", "description": "Filter by source tier."},
    },
    "additionalProperties": False,
}

GET_CONNECTOR_DATA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "connector": {"type": "string", "description": "Connector name (e.g. fred, worldbank)."},
        "method": {"type": "string", "description": "Connector method (e.g. get_indicator)."},
        "args": {
            "type": "object",
            "description": "Method args + converter metadata (primitive_slug, concept_slug, name, "
            "description, source_url, unit_*). Same shape as one ingest-manifest arg_set.",
        },
    },
    "required": ["connector", "method", "args"],
    "additionalProperties": False,
}

# ── Write tools (portfolio P1) — gated by STRATA_PORTFOLIO_ENABLED ──────────
IMPORT_PORTFOLIO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "description": "Company pointers to link to your org.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": "string"},
                    "vertical": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            "minItems": 1,
        },
    },
    "required": ["rows"],
    "additionalProperties": False,
}

SIZE_COMPANY: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Company domain (preferred key)."},
        "name": {"type": "string", "description": "Company name (fallback key)."},
    },
    "minProperties": 1,
    "additionalProperties": False,
}

LIST_PORTFOLIO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["unsized", "sized", "unsizable"]},
        "vertical": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
    },
    "additionalProperties": False,
}

SAVE_PRIMITIVE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": (
                "The AtomicPrimitive to store. `visibility` and `org_id` are forced "
                "server-side; a modeled / analyst-tier number is rejected (Q20)."
            ),
            "properties": {
                "slug": {"type": "string", "description": "Stable kebab-case id."},
                "label": {"type": "string"},
                "value": {"type": "number"},
                "unit": {
                    "type": "object",
                    "description": "Structured unit: kind, dimension, currency, basis.",
                },
                "source": {
                    "type": "object",
                    "description": "Citation: url, tier (regulator/first_party/...), snapshot_sha256.",
                },
            },
            "required": ["slug", "value", "unit", "source"],
        },
    },
    "required": ["payload"],
    "additionalProperties": False,
}

LIST_MY_PRIMITIVES: dict[str, Any] = {"type": "object", "properties": {}}

GET_REPORT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concept_slug": {
            "type": "string",
            "description": "The concept to assemble a sourced market report for (e.g. doc-gen-pc).",
        },
    },
    "required": ["concept_slug"],
    "additionalProperties": False,
}
