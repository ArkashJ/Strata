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

ADD_PORTFOLIO_COMPANY: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Company name (required)."},
        "domain": {"type": "string", "description": "Website / domain (the idempotency key)."},
        "vertical": {"type": "string", "description": "Industry vertical."},
        "market_concept_slug": {
            "type": "string",
            "description": (
                "Explicit market concept slug. Validated against the registry — an "
                "unknown slug is an honest error with suggestions, never fuzzy-rerouted."
            ),
        },
        "size": {
            "type": "boolean",
            "description": "Size the company immediately (registry-first, offline-safe).",
        },
    },
    "required": ["name"],
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

# ── Feedback tools (Phase F) — the improvement flywheel ─────────────────────
SUBMIT_FEEDBACK: dict[str, Any] = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": (
                "The flag. A flag is commentary on the tool, never an input to the math (E1)."
            ),
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "bad_assumption",
                        "failed_query",
                        "primitive_correction",
                        "missing_data",
                        "general",
                    ],
                },
                "target_type": {
                    "type": "string",
                    "enum": ["tam", "primitive", "concept", "framework", "query", "report"],
                },
                "body": {"type": "string", "description": "What's wrong / what you observed."},
                "target_id": {
                    "type": "string",
                    "description": "The flagged target (e.g. a TAM state_hash or primitive slug).",
                },
                "query_text": {"type": "string", "description": "The query that failed, if any."},
                "severity": {"type": "string", "description": "info | warning | error."},
                "suggested_value": {
                    "type": "object",
                    "description": "Advisory proposed correction; never auto-applied.",
                },
            },
            "required": ["kind", "target_type", "body"],
        },
    },
    "required": ["payload"],
    "additionalProperties": False,
}

LIST_FEEDBACK: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["open", "triaged", "resolved", "wontfix"],
            "description": "Filter by triage status.",
        },
    },
    "additionalProperties": False,
}
ADMIN_LIST_FEEDBACK: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["open", "triaged", "resolved", "wontfix"],
            "description": "Filter by triage status.",
        },
        "kind": {
            "type": "string",
            "enum": [
                "bad_assumption",
                "failed_query",
                "primitive_correction",
                "missing_data",
                "general",
            ],
            "description": "Filter by flag kind.",
        },
        "org_id": {"type": "string", "description": "Narrow to a single tenant's queue."},
        "limit": {"type": "integer", "description": "Max rows (1-500, default 100)."},
    },
    "additionalProperties": False,
}
ADMIN_PROMOTE_CORRECTION: dict[str, Any] = {
    "type": "object",
    "properties": {
        "feedback_id": {
            "type": "integer",
            "description": (
                "The correction flag to promote into the shared bank. Uses the "
                "org-private primitive it created (resolved_primitive_id) or its "
                "suggested_value; re-validated + fenced (Q20)."
            ),
        },
    },
    "required": ["feedback_id"],
    "additionalProperties": False,
}
REPORT_SOURCING_GAP: dict[str, Any] = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": "What sourced data was missing. At least one of query_text "
            "or resource_target is required.",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "The market / question that had no sourced answer.",
                },
                "resource_target": {
                    "type": "string",
                    "description": "The connector:method that would fill it, e.g. "
                    "'bls:displacement-by-occupation' (de-dups many phrasings to one gap).",
                },
                "concept_slug": {"type": "string"},
                "role": {"type": "string", "description": "The framework role left unsourced."},
                "lens": {"type": "string"},
                "unit_hint": {"type": "string"},
                "source": {
                    "type": "string",
                    "enum": ["resolve_miss", "report_gap", "unverifiable_claim", "manual"],
                    "description": "Where the miss was observed (default: manual).",
                },
                "note": {"type": "string"},
            },
        },
    },
    "required": ["payload"],
    "additionalProperties": False,
}
LIST_SOURCING_GAPS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["open", "sourced", "wontfix"],
            "description": "Filter by status (default: all).",
        },
        "scope": {
            "type": "string",
            "enum": ["org", "all"],
            "description": "'org' (default) = your workspace; 'all' = every workspace "
            "ranked platform-wide (ADMIN only).",
        },
        "limit": {"type": "integer", "description": "Max rows (1-500, default 50)."},
    },
    "additionalProperties": False,
}

APPLY_FEEDBACK: dict[str, Any] = {
    "type": "object",
    "properties": {
        "feedback_id": {
            "type": "integer",
            "description": ("The primitive_correction / missing_data flag to accept and apply."),
        },
        "primitive_payload": {
            "type": "object",
            "description": (
                "The AtomicPrimitive to create from the correction. Omit to apply "
                "the flag's own stored suggested_value. visibility/org_id are forced "
                "server-side; a modeled / analyst-tier number is rejected (Q20)."
            ),
            "properties": {
                "slug": {"type": "string", "description": "Stable kebab-case id."},
                "value": {"type": "number"},
                "unit": {"type": "object", "description": "Structured unit."},
                "source": {"type": "object", "description": "Citation: url, tier, snapshot."},
            },
        },
    },
    "required": ["feedback_id"],
    "additionalProperties": False,
}

GET_REPORT_FOR_TAM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "state_hash": {
            "type": "string",
            "description": (
                "The state hash of a previously built/sized TAM (from size_tam / "
                "build_tam). The report is bound to THAT exact TAM — what-if "
                "overrides are reflected — not a fresh re-evaluation of the concept."
            ),
        },
    },
    "required": ["state_hash"],
    "additionalProperties": False,
}

EXPORT_REPORT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "state_hash": {
            "type": "string",
            "description": (
                "The state hash of a previously built/sized TAM (from size_tam / "
                "build_tam). The exported report is bound to THAT exact TAM."
            ),
        },
        "format": {
            "type": "string",
            "enum": ["html", "pdf"],
            "default": "html",
            "description": (
                "html (default) returns the self-contained HTML deck; pdf also "
                "returns pdf_base64 when WeasyPrint is available, else falls back "
                "to HTML with a note."
            ),
        },
        "branding": {
            "type": "object",
            "description": (
                "Optional firm branding for the report header/footer (firm_name, "
                "prepared_by, logo_url, logo_data_uri, brand_color, disclaimer)."
            ),
            "properties": {
                "firm_name": {"type": "string"},
                "prepared_by": {"type": "string"},
                "logo_url": {"type": "string"},
                "logo_data_uri": {"type": "string"},
                "brand_color": {"type": "string"},
                "disclaimer": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "required": ["state_hash"],
    "additionalProperties": False,
}

RECORD_SESSION_REASONING: dict[str, Any] = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": (
                "The agent's reasoning for this session. reasoning is required; "
                "session_id defaults to the active X-Strata-Trace-Session; outcome "
                "is a coarse self-assessment tag."
            ),
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": (
                        "The trace session to attach reasoning to. Omit to use the "
                        "active X-Strata-Trace-Session (the common case)."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "The agent's chain-of-thought, plan, or self-assessment for "
                        "this session. Non-empty. Stored verbatim — write as if "
                        "explaining your decisions to a reviewer who will replay the "
                        "session against updated code."
                    ),
                },
                "outcome": {
                    "type": "string",
                    "enum": ["ok", "unsourced", "unverifiable", "error", "flagged"],
                    "description": (
                        "Coarse self-assessment of the session result: ok = answered "
                        "with sourced data; unsourced = the query had no sourced "
                        "primitive; unverifiable = a claim could not be verified; "
                        "error = a tool call failed; flagged = suspicious / needs "
                        "human review."
                    ),
                },
            },
            "required": ["reasoning"],
        },
    },
    "required": ["payload"],
    "additionalProperties": False,
}

VERIFY_MARKET_CLAIM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim": {
            "type": "string",
            "description": "A market claim in natural language (e.g. 'the X TAM is $Y by 2027').",
        },
        "asserted_value": {
            "type": "number",
            "description": "Optional: the numeric figure the claim asserts (same unit as the market).",
        },
        "asserted_unit": {
            "type": "string",
            "description": "Optional: a free-text label of the asserted unit (display only).",
        },
        "as_of": {
            "type": "string",
            "description": "Optional: the as-of date / year the claim refers to (display only).",
        },
    },
    "required": ["claim"],
    "additionalProperties": False,
}

SENSE_CHECK: dict[str, Any] = {
    "type": "object",
    "properties": {
        "players": {
            "type": "array",
            "minItems": 1,
            "description": (
                "The top players in the market. Each needs a name, a market_share "
                "(fraction 0.15 or percent 15), and EITHER a numeric revenue (analyst "
                "estimate, offline) OR an edgar_ticker (sourced TOTAL-company revenue "
                "from SEC EDGAR — live, gated by STRATA_MCP_LIVE_CONNECTORS=1)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Player / company name."},
                    "revenue": {
                        "type": "number",
                        "description": (
                            "The player's annual revenue IN THIS MARKET (analyst "
                            "estimate). Mutually exclusive with edgar_ticker."
                        ),
                    },
                    "edgar_ticker": {
                        "type": "string",
                        "description": (
                            "US-listed ticker to pull a SOURCED (total-company) revenue "
                            "from SEC EDGAR. Live call — requires "
                            "STRATA_MCP_LIVE_CONNECTORS=1. Mutually exclusive with revenue."
                        ),
                    },
                    "market_share": {
                        "type": "number",
                        "description": "Estimated revenue share: fraction (0.15) or percent (15).",
                    },
                    "revenue_as_of": {
                        "type": "string",
                        "description": (
                            "When the revenue was measured: 'YYYY', 'YYYY-MM', or "
                            "'YYYY-MM-DD'. With edgar_ticker it is filled automatically "
                            "from the filing's fiscal-period end (do not pass both). A "
                            ">~6-month gap vs share_as_of fires a time-match warning — "
                            "pairing a current revenue with a stale share inflates/"
                            "deflates the implied TAM."
                        ),
                    },
                    "share_as_of": {
                        "type": "string",
                        "description": (
                            "When the market-share estimate was measured: 'YYYY', "
                            "'YYYY-MM', or 'YYYY-MM-DD'. See revenue_as_of for the "
                            "time-match guardrail; un-dated inputs get an assumptions "
                            "note instead."
                        ),
                    },
                    "share_basis": {
                        "type": "string",
                        "enum": ["revenue", "usage"],
                        "description": (
                            "What the share measures. The method's denominator must be a "
                            "REVENUE share; 'usage' (seats/usage) triggers a strong "
                            "warning because a usage share understates the implied "
                            "market. Unspecified is noted as 'shares assumed to be "
                            "revenue shares'."
                        ),
                    },
                },
                "required": ["name", "market_share"],
                "additionalProperties": False,
            },
        },
        "concept_slug": {
            "type": "string",
            "description": (
                "Optional curated concept slug to cross-check the implied TAM against "
                "its sourced scenario range (verdict: within / above / below)."
            ),
        },
    },
    "required": ["players"],
    "additionalProperties": False,
}

# ── Output schemas (Phase 0) ────────────────────────────────────────────────
# Advertised in tools/list so a host gets typed structuredContent. Permissive by
# design (the payloads are rich + evolving): object with additionalProperties so
# extra fields never break validation, while the key props are documented.
_PERMISSIVE_OBJECT: dict[str, Any] = {"type": "object", "additionalProperties": True}

_TAM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "concept": {"type": "string"},
        "state_hash": {"type": "string"},
        "estimate_kind": {"type": "string"},
        "method_families": {"type": "array", "items": {"type": "string"}},
        "independence_score": {"type": "number"},
        "scenarios": {"type": "array", "items": {"type": "object"}},
        # Today + future market (temporal sizing). ``projection`` carries the
        # realized (today) and projected (horizon) points + the sourced growth
        # rate's provenance, or {available:false, reason} when no growth primitive
        # backs the concept. ``trajectory`` is the backward, sourced-only history.
        "projection": {"type": "object"},
        "trajectory": {"type": "object"},
        "charts": {"type": "object"},
        "next_actions": {"type": "array", "items": {"type": "object"}},
        "resource_links": {"type": "array", "items": {"type": "object"}},
    },
}

OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "size_tam": _TAM_OUTPUT_SCHEMA,
    "resolve_market": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "matched": {"type": "boolean"},
            "via": {"type": "string"},
            "state_hash": {"type": "string"},
            "scenarios": {"type": "array", "items": {"type": "object"}},
        },
    },
    "get_primitive": {
        "type": "object",
        "additionalProperties": True,
        "properties": {"primitive": {"type": "object"}},
    },
    "get_report": _PERMISSIVE_OBJECT,
    "get_report_for_tam": _PERMISSIVE_OBJECT,
    "export_report": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "state_hash": {"type": "string"},
            "format": {"type": "string"},
            "html": {"type": "string"},
            "pdf_base64": {"type": ["string", "null"]},
            "pdf_available": {"type": "boolean"},
            "premium": {"type": "object"},
            "charts": {"type": "object"},
            "citations": {"type": "array", "items": {"type": "object"}},
            "next_actions": {"type": "array", "items": {"type": "object"}},
        },
    },
    "verify_market_claim": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "verdict": {"type": "string"},
            "asserted": {"type": ["object", "null"]},
            "strata_range": {"type": ["object", "null"]},
            "spread_x": {"type": ["number", "null"]},
            "method_families": {"type": "array", "items": {"type": "string"}},
            "independence_score": {"type": ["number", "null"]},
            "inputs": {"type": "array", "items": {"type": "object"}},
            "charts": {"type": "object"},
        },
    },
    "record_session_reasoning": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "recorded": {"type": "boolean"},
            "session_id": {"type": "string"},
            "outcome": {"type": ["string", "null"]},
            "readable_at": {"type": "string"},
        },
    },
    "sense_check": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            # modeled is ALWAYS true (Q20): shares are analyst estimates.
            "modeled": {"type": "boolean", "const": True},
            "modeled_label": {"type": "string"},
            "implied_tam": {"type": "number"},
            "implied_low": {"type": ["number", "null"]},
            "implied_high": {"type": ["number", "null"]},
            "revenue_floor": {"type": "number"},
            "combined_share": {"type": "number"},
            "leverage": {"type": ["number", "null"]},
            "residual": {"type": ["number", "null"]},
            "spread_ratio": {"type": "number"},
            "per_player": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "sourced_range": {"type": ["object", "null"]},
            "verdict": {"type": ["string", "null"]},
        },
    },
}
