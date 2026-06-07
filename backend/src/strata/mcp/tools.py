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
from ..evaluator.engine import EvalOverrides, EvaluatorError, OverrideValue
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


def _paginated(
    key: str, items: list[dict[str, Any]], *, total: int, offset: int, **extra: Any
) -> dict[str, Any]:
    """Uniform pagination envelope (mcp-builder): the page under ``key`` plus
    ``total`` / ``count`` / ``offset`` / ``has_more`` / ``next_offset`` so an
    agent can walk a large result set without loading it all at once."""
    next_offset = offset + len(items)
    has_more = next_offset < total
    return {
        **extra,
        "total": total,
        "count": len(items),
        "offset": offset,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        key: items,
    }


def search_concepts(
    reg: Registry, *, query: str, limit: int = 10, offset: int = 0
) -> dict[str, Any]:
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

    total = len(scored)
    page = scored[offset : offset + limit]
    results: list[dict[str, Any]] = []
    for _, slug in page:
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
    return _paginated("concepts", results, total=total, offset=offset, query=query)


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
            # Taxonomy: a canonical lens shape (parent null, modifiers []) vs a
            # subframework specializing it — so an agent can group the 6 shapes
            # and see how each variant differs before choosing one for a TAM.
            "is_canonical": fw.is_canonical,
            "parent_lens_shape": fw.parent_lens_shape,
            "realism_modifiers": [m.value for m in fw.realism_modifiers],
        }
        for fw in reg.iter_frameworks()
    ]
    frameworks.sort(key=lambda f: str(f["slug"]))
    return {"count": len(frameworks), "frameworks": frameworks}


def _serialize_tam(
    reg: Registry, concept_slug: str, overrides: EvalOverrides | None = None
) -> dict[str, Any]:
    tam = size_concept(reg, concept_slug, overrides=overrides)
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


def list_primitives(
    reg: Registry,
    *,
    tier: str | None = None,
    dimension: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated browse over sizing-grade primitives with optional filters —
    every row carries its sourced citation (the harness's data inventory)."""
    q = (query or "").lower().strip()
    matched: list[AtomicPrimitive] = []
    for slug, p in sorted(reg.atomic.items()):
        if tier and p.source.tier.value != tier:
            continue
        if dimension and p.unit.dimension.value != dimension:
            continue
        if q and q not in f"{slug} {p.name}".lower():
            continue
        matched.append(p)
    page = [_cite(p) for p in matched[offset : offset + limit]]
    return _paginated("primitives", page, total=len(matched), offset=offset)


def build_tam(
    reg: Registry,
    *,
    concept_slug: str,
    primitive_overrides: dict[str, float] | None = None,
    framework_assumptions: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Override-aware sizing so an agent can run what-if scenarios (swap a
    primitive's value, or re-point a framework input) — not just read the frozen
    TAM. What-if values are NEVER persisted (the result carries a banner)."""
    if concept_slug not in reg.concepts:
        raise ToolError(f"concept {concept_slug!r} not found")
    # A what-if value keeps the unit of the primitive it replaces, so the
    # framework input signature still validates (the unit is looked up, not
    # supplied by the caller).
    po: dict[str, OverrideValue] = {}
    for slug, val in (primitive_overrides or {}).items():
        if slug not in reg.atomic:
            raise ToolError(f"override target primitive {slug!r} not found")
        po[slug] = OverrideValue(value=float(val), unit=reg.atomic[slug].unit)
    overrides = EvalOverrides(
        primitive_overrides=po,
        framework_assumptions={k: dict(v) for k, v in (framework_assumptions or {}).items()},
    )
    try:
        return _serialize_tam(reg, concept_slug, overrides)
    except EvaluatorError as exc:
        raise ToolError(str(exc)) from exc


def list_connectors(reg: Registry, *, tier: str | None = None) -> dict[str, Any]:
    """List the typed data connectors (the supply side of the data bank): each
    connector, its source tier, and its callable methods. Pairs with
    ``get_connector_data`` to pull a fresh sourced number on demand."""
    from ..connectors._capability import all_capabilities

    by_connector: dict[str, dict[str, Any]] = {}
    for spec in all_capabilities():
        spec_tier = str(spec.source_tier)
        if tier and spec_tier != tier:
            continue
        entry = by_connector.setdefault(
            spec.connector,
            {"connector": spec.connector, "source_tier": spec_tier, "methods": []},
        )
        entry["methods"].append({"method": spec.method, "returns": spec.returns})
    connectors = sorted(by_connector.values(), key=lambda c: c["connector"])
    return {"count": len(connectors), "connectors": connectors}


def get_connector_data(
    reg: Registry, *, connector: str, method: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Live, sourced fetch: run one connector method and return the validated
    primitive (value + unit + source_url + hash). Gated behind
    ``STRATA_MCP_LIVE_CONNECTORS=1`` so the default MCP surface stays offline-safe
    and an agent can't trigger surprise network/credentialed calls."""
    import os

    if os.getenv("STRATA_MCP_LIVE_CONNECTORS") != "1":
        raise ToolError(
            "live connector calls are disabled; set STRATA_MCP_LIVE_CONNECTORS=1 to enable "
            "get_connector_data (the read-only tools — search_concepts/list_primitives/"
            "size_tam — need no network)."
        )
    from ..connectors._dispatch import call_and_convert

    try:
        primitive = call_and_convert(connector, method, dict(args))
    except Exception as exc:
        raise ToolError(f"connector call failed: {type(exc).__name__}: {exc}") from exc
    return {"connector": connector, "method": method, "primitive": primitive}


def whoami(reg: Registry) -> dict[str, Any]:
    """Diagnostics: confirm the connection works and show who the caller is + how
    much data the bank holds. The first call an agent (or a VC verifying setup)
    should make. Reads the authenticated principal from the request context
    (hosted ``/mcp``); over local stdio there is no principal (local-trust)."""
    from .. import __version__
    from .context import current_principal

    p = current_principal.get()
    connectors_count = 0
    try:
        from ..connectors._capability import all_capabilities

        connectors_count = len({spec.connector for spec in all_capabilities()})
    except Exception:
        connectors_count = 0
    return {
        "ok": True,
        "authenticated": p is not None,
        "org_id": p.org_id if p is not None else None,
        "key_id": p.key_id if p is not None else None,
        "scopes": list(p.scopes) if p is not None else [],
        "transport": "http" if p is not None else "stdio",
        "version": __version__,
        "bank": {
            "concepts": len(reg.concepts),
            "primitives": len(reg.atomic),
            "frameworks": sum(1 for _ in reg.iter_frameworks()),
            "connectors": connectors_count,
        },
    }


_Handler = Callable[[Registry, dict[str, Any]], dict[str, Any]]


def _h_whoami(reg: Registry, _args: dict[str, Any]) -> dict[str, Any]:
    return whoami(reg)


def _h_search(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return search_concepts(
        reg,
        query=args["query"],
        limit=int(args.get("limit", 10)),
        offset=int(args.get("offset", 0)),
    )


def _h_get_primitive(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return get_primitive(reg, slug=args["slug"])


def _h_list_frameworks(reg: Registry, _args: dict[str, Any]) -> dict[str, Any]:
    return list_frameworks(reg)


def _h_size_tam(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return size_tam(reg, concept_slug=args.get("concept_slug"), query=args.get("query"))


def _h_resolve_market(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return resolve_market(reg, query=args["query"])


def _h_list_primitives(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return list_primitives(
        reg,
        tier=args.get("tier"),
        dimension=args.get("dimension"),
        query=args.get("query"),
        limit=int(args.get("limit", 50)),
        offset=int(args.get("offset", 0)),
    )


def _h_build_tam(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return build_tam(
        reg,
        concept_slug=args["concept_slug"],
        primitive_overrides=args.get("primitive_overrides"),
        framework_assumptions=args.get("framework_assumptions"),
    )


def _h_list_connectors(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return list_connectors(reg, tier=args.get("tier"))


def _h_get_connector_data(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return get_connector_data(
        reg, connector=args["connector"], method=args["method"], args=dict(args.get("args", {}))
    )


def _h_import_portfolio(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from .portfolio_tools import import_portfolio

    return import_portfolio(reg, rows=list(args.get("rows", [])))


def _h_size_company(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from .portfolio_tools import size_company as _size_company_tool

    return _size_company_tool(reg, domain=args.get("domain"), name=args.get("name"))


def _h_list_portfolio(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from .portfolio_tools import list_portfolio

    return list_portfolio(
        reg,
        status=args.get("status"),
        vertical=args.get("vertical"),
        limit=(int(args["limit"]) if args.get("limit") is not None else None),
    )


# Tool annotations (mcp-builder): hints a client uses to label a tool. All Strata
# tools that touch the data bank are read-only; the two portfolio tools write to
# the caller's org store (non-destructive); connector + size_company touch the
# network only behind their gates.
_READ: dict[str, bool] = {"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True}
_READ_NET: dict[str, bool] = {"readOnlyHint": True, "openWorldHint": True}
_WRITE: dict[str, bool] = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}

# name -> (description, inputSchema, handler, annotations). server.py iterates this
# for both tools/list and tools/call so there is exactly one tool registry.
TOOLS: dict[str, dict[str, Any]] = {
    "whoami": {
        "description": (
            "Verify the connection and show the caller's org + how much data the bank "
            "holds (concepts/primitives/frameworks/connectors). Call this first to "
            "confirm Strata is connected."
        ),
        "inputSchema": schemas.WHOAMI,
        "handler": _h_whoami,
        "annotations": _READ,
    },
    "search_concepts": {
        "description": "Search curated market concepts; returns each with its sourced measurements.",
        "inputSchema": schemas.SEARCH_CONCEPTS,
        "handler": _h_search,
        "annotations": _READ,
    },
    "get_primitive": {
        "description": "Fetch one atomic primitive with its value, unit, and source citation.",
        "inputSchema": schemas.GET_PRIMITIVE,
        "handler": _h_get_primitive,
        "annotations": _READ,
    },
    "list_frameworks": {
        "description": (
            "List the TAM frameworks (method family, lens, inputs). Each is either a "
            "canonical lens shape (is_canonical=true) or a subframework that specializes "
            "one — parent_lens_shape names the canonical, realism_modifiers how it differs."
        ),
        "inputSchema": schemas.LIST_FRAMEWORKS,
        "handler": _h_list_frameworks,
        "annotations": _READ,
    },
    "size_tam": {
        "description": "Size a curated concept into a sourced, hash-pinned scenario tree.",
        "inputSchema": schemas.SIZE_TAM,
        "handler": _h_size_tam,
        "annotations": _READ,
    },
    "resolve_market": {
        "description": "Resolve a free-form market query to a sourced TAM (registry-first, no LLM).",
        "inputSchema": schemas.RESOLVE_MARKET,
        "handler": _h_resolve_market,
        "annotations": _READ,
    },
    "list_primitives": {
        "description": "Browse sizing-grade primitives (filter by tier/dimension/query); each row "
        "carries its source citation. The harness's data inventory.",
        "inputSchema": schemas.LIST_PRIMITIVES,
        "handler": _h_list_primitives,
        "annotations": _READ,
    },
    "build_tam": {
        "description": "Size a concept with what-if overrides (swap a primitive's value or re-point "
        "a framework input) — scenario analysis, never persisted.",
        "inputSchema": schemas.BUILD_TAM,
        "handler": _h_build_tam,
        "annotations": _READ,
    },
    "list_connectors": {
        "description": "List the typed data connectors (supply side): each connector, its source "
        "tier, and callable methods. Pairs with get_connector_data.",
        "inputSchema": schemas.LIST_CONNECTORS,
        "handler": _h_list_connectors,
        "annotations": _READ,
    },
    "get_connector_data": {
        "description": "[LIVE] Run one connector method and return the validated, hash-pinned "
        "primitive. Gated by STRATA_MCP_LIVE_CONNECTORS=1 (network/credentialed).",
        "inputSchema": schemas.GET_CONNECTOR_DATA,
        "handler": _h_get_connector_data,
        "annotations": _READ_NET,
    },
    "import_portfolio": {
        "description": (
            "[WRITE] Link a list of portfolio companies to your org (idempotent on "
            "domain). Gated by STRATA_PORTFOLIO_ENABLED."
        ),
        "inputSchema": schemas.IMPORT_PORTFOLIO,
        "handler": _h_import_portfolio,
        "annotations": _WRITE,
    },
    "size_company": {
        "description": (
            "[WRITE] Size one linked company registry-first (offline-safe; never a "
            "live LLM/Exa call). Returns the sourced TAM + provenance or an honest "
            "unsizable reason. Gated by STRATA_PORTFOLIO_ENABLED."
        ),
        "inputSchema": schemas.SIZE_COMPANY,
        "handler": _h_size_company,
        "annotations": _WRITE,
    },
    "list_portfolio": {
        "description": "[READ] List linked companies with TAM + progress counts.",
        "inputSchema": schemas.LIST_PORTFOLIO,
        "handler": _h_list_portfolio,
        "annotations": _READ,
    },
}


def call_tool(reg: Registry, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(f"unknown tool {name!r}")
    handler: _Handler = spec["handler"]
    return handler(reg, arguments or {})
