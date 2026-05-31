"""Strata MCP tool handlers — pure, read-only, sourced (AC5A.2 / AC5A.3).

Every numeric payload carries its citation: ``source_url``, ``source_tier`` and
``snapshot_sha256`` straight off the registry record (no fabricated hosts — the
URL is whatever the curated source declares). None of these handlers mutate the
registry or write primitives: they only read ``registry`` and call the existing
evaluator/resolver. ``resolve_market`` is deliberately registry-first and does
NOT trigger LLM synthesis, so an MCP client can never get an unsourced number.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..evaluator import size_concept
from ..evaluator.engine import EvaluatorError
from ..models import AtomicPrimitive
from ..registry import Registry, RegistryError
from ..resolver.match import match_concept
from . import schemas


class ToolError(RuntimeError):
    """A tool was called with bad arguments or an unknown slug."""


# Internal/synthetic host marker used by community-modeled primitives. These are
# honest estimates, not externally-citable measurements — so the MCP surface
# emits source_url=None for them rather than a fabricated host (AC5A.2). The tier
# (community-modeled) still tells the client the number is modeled. Wave 1's
# citation allowlist formalizes this.
_INTERNAL_HOST = "strata.internal"


def _clean_url(url: str) -> str | None:
    return None if (not url or _INTERNAL_HOST in url) else url


def _cite(p: AtomicPrimitive) -> dict[str, Any]:
    """The sourced-number contract: value + unit + citation (hash always pinned;
    source_url is None for modeled numbers that have no external citation)."""
    return {
        "slug": p.slug,
        "name": p.name,
        "value": p.value,
        "unit": p.unit.model_dump(mode="json"),
        "as_of": p.as_of.isoformat(),
        "source_url": _clean_url(p.source.url),
        "source_tier": p.source.tier.value,
        "snapshot_sha256": p.source.snapshot_sha256,
    }


def search_concepts(reg: Registry, *, query: str, limit: int = 10) -> dict[str, Any]:
    q = query.lower().strip()
    scored: list[tuple[int, str]] = []
    for slug, c in reg.concepts.items():
        hay = f"{slug} {c.name} {c.definition}".lower()
        if q in hay or q in slug:
            # Crude rank: exact slug/name first, then substring hits.
            rank = 0 if q in (slug, c.name.lower()) else 1
            scored.append((rank, slug))
    # Always include the best fuzzy match so a near-miss query still resolves.
    best = match_concept(reg, query)
    if best is not None and all(best != s for _, s in scored):
        scored.append((2, best))
    scored.sort(key=lambda x: (x[0], x[1]))

    results: list[dict[str, Any]] = []
    for _, slug in scored[:limit]:
        c = reg.concepts[slug]
        measurements = [_cite(reg.atomic[m]) for m in c.measurements if m in reg.atomic]
        results.append(
            {
                "slug": slug,
                "name": c.name,
                "definition": c.definition,
                "competing_concepts": list(c.competing_concepts),
                "measurements": measurements,
            }
        )
    return {"query": query, "count": len(results), "concepts": results}


def get_primitive(reg: Registry, *, slug: str) -> dict[str, Any]:
    try:
        p = reg.get_atomic(slug)
    except RegistryError as exc:
        raise ToolError(f"primitive {slug!r} not found") from exc
    return {"primitive": {**_cite(p), "description": p.description}}


def list_frameworks(reg: Registry) -> dict[str, Any]:
    frameworks = [
        {
            "slug": fw.slug,
            "name": fw.name,
            "method_family": fw.method_family.value,
            "lens": fw.lens.value,
            "inputs": [{"name": i.name, "role": i.role.value} for i in fw.inputs],
            "formula": fw.formula,
        }
        for fw in reg.iter_frameworks()
    ]
    frameworks.sort(key=lambda f: f["slug"])
    return {"count": len(frameworks), "frameworks": frameworks}


def _serialize_tam(reg: Registry, concept_slug: str) -> dict[str, Any]:
    tam = size_concept(reg, concept_slug)
    scenarios = [
        {
            "framework": s.framework,
            "variant": s.framework_variant,
            "method": (
                reg.frameworks[s.framework].method_family.value
                if s.framework in reg.frameworks
                else s.lens.value
            ),
            "value": s.value,
            "unit": s.unit.model_dump(mode="json"),
            # Every input carries its hash pin so the number is reproducible.
            "inputs": [
                {
                    "name": iu.role_name,
                    "primitive": iu.primitive_slug,
                    "value": iu.value,
                    "snapshot_sha256": iu.snapshot_sha256,
                }
                for iu in s.inputs_used
            ],
            "banners": [{"kind": b.kind.value, "message": b.message} for b in s.banners],
        }
        for s in tam.scenarios
    ]
    return {
        "concept": tam.target.concept,
        "concept_name": tam.target.concept_name,
        "state_hash": tam.state_hash,
        "estimate_kind": "triangulated" if len(tam.method_families_used) >= 2 else "single_method",
        "method_families": [m.value for m in tam.method_families_used],
        "independence_score": tam.independence_score,
        "scenarios": scenarios,
    }


def size_tam(
    reg: Registry, *, concept_slug: str | None = None, query: str | None = None
) -> dict[str, Any]:
    slug = concept_slug
    if slug is None and query is not None:
        slug = match_concept(reg, query)
    if slug is None:
        raise ToolError("provide a known concept_slug or a query that matches one")
    if slug not in reg.concepts:
        raise ToolError(f"concept {slug!r} not found")
    try:
        return _serialize_tam(reg, slug)
    except EvaluatorError as exc:
        raise ToolError(str(exc)) from exc


def resolve_market(reg: Registry, *, query: str) -> dict[str, Any]:
    """Registry-first, LLM-free: a curated concept hit returns the sourced
    triangulated tree; a miss returns ``matched: false`` (never a synthesized,
    unsourced number — that path is the authenticated web app)."""
    slug = match_concept(reg, query)
    if slug is None:
        return {
            "matched": False,
            "query": query,
            "message": (
                "No curated concept matches this query. Strata's MCP surface only "
                "returns sourced, hash-pinned numbers; use the Strata web app for "
                "novel LLM synthesis."
            ),
        }
    return {"matched": True, "via": "concept", **_serialize_tam(reg, slug)}


_Handler = Callable[[Registry, dict[str, Any]], dict[str, Any]]


def _h_search(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return search_concepts(reg, query=args["query"], limit=int(args.get("limit", 10)))


def _h_get_primitive(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return get_primitive(reg, slug=args["slug"])


def _h_list_frameworks(reg: Registry, _args: dict[str, Any]) -> dict[str, Any]:
    return list_frameworks(reg)


def _h_size_tam(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return size_tam(reg, concept_slug=args.get("concept_slug"), query=args.get("query"))


def _h_resolve_market(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return resolve_market(reg, query=args["query"])


# name -> (description, inputSchema, handler). server.py iterates this for both
# tools/list and tools/call so there is exactly one tool registry.
TOOLS: dict[str, dict[str, Any]] = {
    "search_concepts": {
        "description": "Search curated market concepts; returns each with its sourced measurements.",
        "inputSchema": schemas.SEARCH_CONCEPTS,
        "handler": _h_search,
    },
    "get_primitive": {
        "description": "Fetch one atomic primitive with its value, unit, and source citation.",
        "inputSchema": schemas.GET_PRIMITIVE,
        "handler": _h_get_primitive,
    },
    "list_frameworks": {
        "description": "List the TAM frameworks (method family, lens, inputs).",
        "inputSchema": schemas.LIST_FRAMEWORKS,
        "handler": _h_list_frameworks,
    },
    "size_tam": {
        "description": "Size a curated concept into a sourced, hash-pinned scenario tree.",
        "inputSchema": schemas.SIZE_TAM,
        "handler": _h_size_tam,
    },
    "resolve_market": {
        "description": "Resolve a free-form market query to a sourced TAM (registry-first, no LLM).",
        "inputSchema": schemas.RESOLVE_MARKET,
        "handler": _h_resolve_market,
    },
}


def call_tool(reg: Registry, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(f"unknown tool {name!r}")
    handler: _Handler = spec["handler"]
    return handler(reg, arguments or {})
