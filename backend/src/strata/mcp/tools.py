"""Strata MCP tool handlers — pure, read-only, sourced (AC5A.2 / AC5A.3).

Every numeric payload carries its citation: ``source_url``, ``source_tier`` and
``snapshot_sha256`` straight off the registry record (no fabricated hosts — the
URL is whatever the curated source declares). None of these handlers mutate the
registry or write primitives: they only read ``registry`` and call the existing
evaluator/resolver. ``resolve_market`` is deliberately registry-first and does
NOT trigger LLM synthesis, so an MCP client can never get an unsourced number.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import CallToolResult

from ..evaluator import size_concept
from ..evaluator.engine import EvalOverrides, EvaluatorError, OverrideValue
from ..models import AtomicPrimitive
from ..models.tam_output import TAMOutput
from ..registry import Registry, RegistryError
from ..resolver.match import match_concept
from . import schemas
from .charts import build_all_charts

# ToolError now lives in errors.py with a code taxonomy; imported here so the many
# ``from .tools import ToolError`` / ``raise ToolError(...)`` sites are unchanged
# (the positional message constructor stays backward-compatible).
from .errors import (
    CODE_CONCEPT_NOT_FOUND,
    CODE_EVALUATOR_ERROR,
    CODE_INVALID_INPUT,
    CODE_LIVE_DISABLED,
    CODE_NO_MATCH,
    CODE_PRIMITIVE_NOT_FOUND,
    ToolError,
)
from .integrity import primitive_integrity
from .result import tool_result

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
    source_url is None for modeled numbers that have no external citation).

    Carries an MCP ``resource_uri`` (``strata://primitive/<slug>``) so the number
    is one click from its full record, and a serve-time ``integrity`` status so a
    tampered / placeholder pin never silently backs a number (Phase 1/2)."""
    return {
        "slug": p.slug,
        "name": p.name,
        "value": p.value,
        "unit": p.unit.model_dump(mode="json"),
        "as_of": p.as_of.isoformat(),
        "source_url": _clean_url(p.source.url),
        "source_tier": p.source.tier.value,
        "snapshot_sha256": p.source.snapshot_sha256,
        "integrity": primitive_integrity(p),
        "resource_uri": f"strata://primitive/{p.slug}",
    }


# Public alias so other modules (resources.py) can build the same sourced-number
# citation without reaching into a private name.
cite_primitive = _cite


def _paginated(
    key: str, items: list[dict[str, Any]], *, total: int, offset: int, **extra: Any
) -> dict[str, Any]:
    """Uniform pagination envelope (mcp-builder): the page under ``key`` plus
    ``total`` / ``count`` / ``offset`` / ``has_more`` / ``next_offset`` so an
    agent can walk a large result set without loading it all at once.

    Also emits an opaque ``cursor`` (the next page's offset, base64-encoded) so a
    cursor-style client can page without knowing it is offset-backed; ``offset``
    stays for offset-style clients (A6)."""
    import base64

    next_offset = offset + len(items)
    has_more = next_offset < total
    cursor = base64.urlsafe_b64encode(str(next_offset).encode()).decode() if has_more else None
    return {
        **extra,
        "total": total,
        "count": len(items),
        "offset": offset,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "cursor": cursor,
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
        raise ToolError(
            f"primitive {slug!r} not found",
            code=CODE_PRIMITIVE_NOT_FOUND,
            remediation="list_primitives to find a valid slug",
        ) from exc
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


def _serialize_tam_output(reg: Registry, tam: TAMOutput) -> dict[str, Any]:
    """Serialize an already-computed TAM (no sizing). The result carries the
    chart specs + the resource_uri for the permalink so an agent can drill down
    or render a chart without a second call."""
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
        "convergence": (tam.convergence.model_dump(mode="json") if tam.convergence else None),
        "scenarios": scenarios,
        "charts": build_all_charts(tam),
        "permalink": f"/tam/{tam.state_hash}",
    }


def _serialize_tam(
    reg: Registry, concept_slug: str, overrides: EvalOverrides | None = None
) -> dict[str, Any]:
    tam = size_concept(reg, concept_slug, overrides=overrides)
    # Cache the computed TAM so get_report_for_tam(<hash>) / /tam/<hash> resolve
    # the exact tree this call produced (incl. what-if overrides) without a DB
    # round-trip — the report can then bind to the steered numbers (GAP-1).
    reg.remember_tam(tam)
    return _serialize_tam_output(reg, tam)


def _tam_resource_links(reg: Registry, tam_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Drill-down links for a TAM result: the TAM + report resources, the web
    permalink + forwardable report, and each unique sourced input primitive."""
    state_hash = str(tam_dict.get("state_hash", ""))
    concept = str(tam_dict.get("concept", ""))
    links: list[dict[str, Any]] = [
        {"uri": f"strata://tam/{state_hash}", "name": "tam", "description": "the frozen TAM"},
        {"uri": f"strata://report/{concept}", "name": "report", "description": "market report"},
        {"uri": f"/tam/{state_hash}", "name": "permalink", "mimeType": "text/html"},
        {"uri": f"/tam/{state_hash}/report", "name": "report_pdf", "mimeType": "text/html"},
    ]
    seen: set[str] = set()
    for sc in tam_dict.get("scenarios", []):
        for inp in sc.get("inputs", []):
            slug = str(inp.get("primitive", ""))
            if slug and slug not in seen and slug in reg.atomic:
                seen.add(slug)
                links.append({"uri": f"strata://primitive/{slug}", "name": slug})
                links.append(
                    {"uri": f"/p/{slug}", "name": f"{slug} (web)", "mimeType": "text/html"}
                )
    return links


def _tam_next_actions(tam_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Affordances the agent can chain off a TAM result."""
    state_hash = str(tam_dict.get("state_hash", ""))
    concept = str(tam_dict.get("concept", ""))
    return [
        {
            "tool": "get_report_for_tam",
            "description": "Assemble the full sourced report bound to this exact TAM.",
            "arguments": {"state_hash": state_hash},
        },
        {
            "tool": "build_tam",
            "description": "Challenge an assumption with a what-if override.",
            "arguments": {"concept_slug": concept},
        },
    ]


def size_tam(
    reg: Registry, *, concept_slug: str | None = None, query: str | None = None
) -> dict[str, Any]:
    slug = concept_slug
    if slug is None and query is not None:
        slug = match_concept(reg, query)
    if slug is None:
        raise ToolError(
            "provide a known concept_slug or a query that matches one",
            code=CODE_NO_MATCH,
            remediation="search_concepts to find a matching slug",
        )
    if slug not in reg.concepts:
        raise ToolError(
            f"concept {slug!r} not found",
            code=CODE_CONCEPT_NOT_FOUND,
            remediation="search_concepts to find a matching slug",
        )
    try:
        return _serialize_tam(reg, slug)
    except EvaluatorError as exc:
        raise ToolError(str(exc), code=CODE_EVALUATOR_ERROR) from exc


def resolve_market(reg: Registry, *, query: str) -> dict[str, Any]:
    """Registry-first, LLM-free: a curated concept hit returns the sourced
    triangulated tree; a miss returns ``matched: false`` (never a synthesized,
    unsourced number — that path is the authenticated web app)."""
    slug = match_concept(reg, query)
    if slug is None:
        return {
            "matched": False,
            # Machine-readable so an agent cannot mistake a miss for a sourced
            # number (AC-B2.1): no sourced data exists for this query.
            "unsourced": True,
            "estimate_kind": None,
            "independence_score": 0.0,
            "query": query,
            "message": (
                "No curated concept matches this query. Strata's MCP surface only "
                "returns sourced, hash-pinned numbers — this query is unsourced. "
                "Report it with report_sourcing_gap so the miss becomes ranked "
                "demand for the sourcing backlog."
            ),
            "next_action": {
                "tool": "report_sourcing_gap",
                "payload": {"query_text": query, "source": "resolve_miss"},
            },
        }
    return {"matched": True, "via": "concept", **_serialize_tam(reg, slug)}


async def get_report_for_tam(reg: Registry, *, state_hash: str) -> dict[str, Any]:
    """Assemble the report bound to a previously built/sized TAM (GAP-1). Resolves
    the TAM from the registry cache (a prior size_tam/build_tam call remembered it),
    falling back to the durable Postgres store so a shared permalink keeps resolving
    under stateless HTTP / multi-worker / cache eviction (mirrors GET /tam/{hash}/report)."""
    from ..db.tams import get_tam_from_db_safe
    from ..report import assemble_premium_report_for_tam, assemble_report_for_tam

    tam = reg.tam_outputs.get(state_hash)
    if tam is None:
        tam = await get_tam_from_db_safe(state_hash)
        if tam is not None:
            reg.remember_tam(tam)
    if tam is None:
        raise ToolError(
            f"no TAM with state_hash {state_hash!r} in this session; size it first",
            code=CODE_NO_MATCH,
            remediation="call size_tam or build_tam, then pass the returned state_hash",
        )
    # The flat answer rows (back-compat) plus the premium $1M section view that an
    # agent forwards as a deliverable — both bound to THIS tam, no re-evaluation.
    report = assemble_report_for_tam(reg, tam).model_dump(mode="json")
    report["premium"] = assemble_premium_report_for_tam(reg, tam).model_dump(mode="json")
    return report


async def _resolve_tam_for_report(reg: Registry, state_hash: str) -> TAMOutput:
    """Resolve a previously built/sized TAM: cache first, durable store fallback
    (the same resolution :func:`get_report_for_tam` uses, factored out so
    ``export_report`` binds to the identical TAM)."""
    from ..db.tams import get_tam_from_db_safe

    tam = reg.tam_outputs.get(state_hash)
    if tam is None:
        tam = await get_tam_from_db_safe(state_hash)
        if tam is not None:
            reg.remember_tam(tam)
    if tam is None:
        raise ToolError(
            f"no TAM with state_hash {state_hash!r} in this session; size it first",
            code=CODE_NO_MATCH,
            remediation="call size_tam or build_tam, then pass the returned state_hash",
        )
    return tam


async def export_report(
    reg: Registry,
    *,
    state_hash: str,
    format: str = "html",
    branding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Maximum-utility export: the ENTIRE professional report in one call.

    Bundles the premium structured sections + the self-contained Altimeter-grade
    HTML deck (+ a base64 PDF when WeasyPrint is available and format=pdf) + the
    Vega-Lite/Mermaid chart specs + the deduped citations + chainable next_actions
    — all bound to THIS exact TAM (what-if overrides reflected). Every figure is
    sourced or reproducibly derived; nothing is synthesized (Q20). A PDF that
    cannot render (missing native libs) degrades to HTML with an honest note,
    never an error."""
    import base64

    from ..report import (
        Branding,
        PdfUnavailableError,
        assemble_premium_report_for_tam,
        render_premium_html,
        render_premium_pdf,
    )

    tam = await _resolve_tam_for_report(reg, state_hash)
    premium = assemble_premium_report_for_tam(reg, tam)
    brand = Branding.model_validate(branding) if branding else None
    html = render_premium_html(premium, brand)

    fmt = format if format in {"html", "pdf"} else "html"
    pdf_b64: str | None = None
    pdf_available = False
    pdf_note: str | None = None
    if fmt == "pdf":
        try:
            pdf_b64 = base64.b64encode(render_premium_pdf(html)).decode("ascii")
            pdf_available = True
        except PdfUnavailableError as exc:
            pdf_note = f"PDF unavailable, returning HTML: {exc}"
        except Exception as exc:  # never break the documented HTML fallback contract
            # export_report promises a deliverable, not an error: a genuine WeasyPrint
            # render failure (libs present) degrades to HTML rather than failing the call.
            pdf_note = f"PDF render failed, returning HTML: {type(exc).__name__}: {exc}"

    citations = [
        {
            "primitive_slug": p.primitive_slug,
            "source_url": p.source_url,
            "source_tier": p.source_tier,
            "snapshot_sha256": p.snapshot_sha256,
        }
        for p in premium.sources
    ]
    out: dict[str, Any] = {
        "state_hash": tam.state_hash,
        "concept": tam.target.concept,
        "format": fmt,
        "html": html,
        "pdf_base64": pdf_b64,
        "pdf_available": pdf_available,
        "premium": premium.model_dump(mode="json"),
        "charts": build_all_charts(tam),
        "citations": citations,
        "permalink": f"/tam/{tam.state_hash}/report",
        # Chainable affordances embedded in the payload (the dict path does not
        # take a separate next_actions kwarg, so carry them inline — result.py
        # surfaces structuredContent.next_actions identically).
        "next_actions": [
            {
                "tool": "build_tam",
                "description": "Challenge an assumption with a what-if override, then re-export.",
                "arguments": {"concept_slug": tam.target.concept},
            },
            {
                "tool": "verify_market_claim",
                "description": "Verify a specific figure in the report against the sourced range.",
                "arguments": {"claim": tam.target.concept_name or tam.target.concept},
            },
        ],
    }
    if pdf_note:
        out["pdf_note"] = pdf_note
    return out


def _claim_verdict(asserted_value: float | None, low: float, high: float) -> tuple[str, float]:
    """Verdict + spread for an asserted figure vs the sourced range.

    supported: inside [low, high]; partially_supported: within 2× of an endpoint;
    unsupported: further out. With no asserted value we report the range only
    (verdict 'range_only'). Pure comparison of sourced numbers — nothing invented.
    """
    spread = (high / low) if low > 0 else 0.0
    if asserted_value is None:
        return "range_only", spread
    if low <= asserted_value <= high:
        return "supported", spread
    nearest = low if asserted_value < low else high
    ratio = (asserted_value / nearest) if nearest > 0 else float("inf")
    off_by = max(ratio, 1.0 / ratio) if ratio > 0 else float("inf")
    return ("partially_supported" if off_by <= 2.0 else "unsupported"), spread


def verify_market_claim(
    reg: Registry,
    *,
    claim: str,
    asserted_value: float | None = None,
    asserted_unit: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """The thesis tool: verify an AI-generated market claim against sourced data.

    Matches the claim to a curated concept (LLM-free), sizes it, and renders a
    verdict from the sourced scenario range + convergence. An unknown claim is
    ``unverifiable`` with an honest gap — a number is NEVER synthesized (Q20)."""
    slug = match_concept(reg, claim)
    if slug is None or slug not in reg.concepts:
        return {
            "verdict": "unverifiable",
            "claim": claim,
            "asserted": _asserted(asserted_value, asserted_unit, as_of),
            "strata_range": None,
            "message": (
                "No curated, sourced concept matches this claim, so Strata cannot "
                "verify it. This is an honest gap — no number is synthesized."
            ),
        }
    try:
        tam_dict = _serialize_tam(reg, slug)
    except EvaluatorError as exc:
        raise ToolError(str(exc), code=CODE_EVALUATOR_ERROR) from exc

    values = [float(s["value"]) for s in tam_dict["scenarios"]]
    low, high = min(values), max(values)
    mid = (low + high) / 2.0
    verdict, spread = _claim_verdict(asserted_value, low, high)
    inputs = [
        {
            "primitive": inp["primitive"],
            "value": inp["value"],
            "snapshot_sha256": inp["snapshot_sha256"],
        }
        for sc in tam_dict["scenarios"]
        for inp in sc["inputs"]
    ]
    return {
        "verdict": verdict,
        "claim": claim,
        "concept": slug,
        "asserted": _asserted(asserted_value, asserted_unit, as_of),
        "strata_range": {"low": low, "mid": mid, "high": high},
        "spread_x": spread,
        "method_families": tam_dict["method_families"],
        "independence_score": tam_dict["independence_score"],
        "convergence": tam_dict.get("convergence"),
        "inputs": inputs,
        "state_hash": tam_dict["state_hash"],
        "charts": tam_dict.get("charts", {}),
    }


def _asserted(value: float | None, unit: str | None, as_of: str | None) -> dict[str, Any] | None:
    if value is None and unit is None and as_of is None:
        return None
    return {"value": value, "unit": unit, "as_of": as_of}


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
        raise ToolError(
            f"concept {concept_slug!r} not found",
            code=CODE_CONCEPT_NOT_FOUND,
            remediation="search_concepts to find a matching slug",
        )
    # A what-if value keeps the unit of the primitive it replaces, so the
    # framework input signature still validates (the unit is looked up, not
    # supplied by the caller).
    po: dict[str, OverrideValue] = {}
    for slug, val in (primitive_overrides or {}).items():
        if slug not in reg.atomic:
            raise ToolError(
                f"override target primitive {slug!r} not found",
                code=CODE_PRIMITIVE_NOT_FOUND,
                remediation="list_primitives to find a valid override target",
            )
        po[slug] = OverrideValue(value=float(val), unit=reg.atomic[slug].unit)
    overrides = EvalOverrides(
        primitive_overrides=po,
        framework_assumptions={k: dict(v) for k, v in (framework_assumptions or {}).items()},
    )
    try:
        return _serialize_tam(reg, concept_slug, overrides)
    except EvaluatorError as exc:
        raise ToolError(str(exc), code=CODE_EVALUATOR_ERROR) from exc


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
        # Maximum agent utility: per-method args (name/type/required/example),
        # what it returns, a one-line example call, and the honest reliability
        # flags — everything an agent needs to pick + call a method correctly.
        args = [
            {
                "name": a.name,
                "type": str(a.type),
                "description": a.description,
                "required": a.required,
                "example": a.example,
            }
            for a in spec.args
        ]
        example_args = {a.name: a.example for a in spec.args if a.example is not None}
        entry["methods"].append(
            {
                "method": spec.method,
                "description": spec.description,
                "returns": spec.returns,
                "args": args,
                "source_tier": spec_tier,
                "is_fragile": spec.is_fragile,
                "requires_paid_tier": spec.requires_paid_tier,
                "example_call": {
                    "connector": spec.connector,
                    "method": spec.method,
                    "args": example_args,
                },
            }
        )
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
            "size_tam — need no network).",
            code=CODE_LIVE_DISABLED,
            remediation="set STRATA_MCP_LIVE_CONNECTORS=1 on the server to enable live fetches",
        )
    from ..connectors._dispatch import call_and_convert

    try:
        primitive = call_and_convert(connector, method, dict(args))
    except Exception as exc:
        raise ToolError(
            f"connector call failed: {type(exc).__name__}: {exc}",
            code=CODE_EVALUATOR_ERROR,
            retriable=True,
        ) from exc
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


# A handler returns a plain dict, a fully-built CallToolResult (the result-aware
# tools that attach resource_links / next_actions / charts), OR a coroutine
# resolving to a dict (the DB-backed write/read tools). ``server._call_tool``
# awaits the coroutine on the app's event loop and wraps a dict via tool_result.
_HandlerReturn = dict[str, Any] | CallToolResult | Awaitable[dict[str, Any]]
_Handler = Callable[[Registry, dict[str, Any]], _HandlerReturn]


def _tam_result(reg: Registry, tam_dict: dict[str, Any]) -> CallToolResult:
    """Wrap a TAM-shaped dict with its drill-down links + chainable next_actions."""
    return tool_result(
        tam_dict,
        links=_tam_resource_links(reg, tam_dict),
        next_actions=_tam_next_actions(tam_dict),
    )


def _h_whoami(reg: Registry, _args: dict[str, Any]) -> dict[str, Any]:
    return whoami(reg)


def _h_search(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return search_concepts(
        reg,
        query=args["query"],
        limit=int(args.get("limit", 10)),
        offset=int(args.get("offset", 0)),
    )


def _h_get_primitive(reg: Registry, args: dict[str, Any]) -> CallToolResult:
    out = get_primitive(reg, slug=args["slug"])
    slug = str(args["slug"])
    return tool_result(
        out,
        links=[
            {"uri": f"strata://primitive/{slug}", "name": slug},
            {"uri": f"/p/{slug}", "name": f"{slug} (web)", "mimeType": "text/html"},
        ],
    )


def _h_list_frameworks(reg: Registry, _args: dict[str, Any]) -> dict[str, Any]:
    return list_frameworks(reg)


def _h_size_tam(reg: Registry, args: dict[str, Any]) -> CallToolResult:
    return _tam_result(
        reg, size_tam(reg, concept_slug=args.get("concept_slug"), query=args.get("query"))
    )


def _h_resolve_market(reg: Registry, args: dict[str, Any]) -> CallToolResult:
    out = resolve_market(reg, query=args["query"])
    if out.get("matched"):
        return _tam_result(reg, out)
    return tool_result(out)


def _h_verify_market_claim(reg: Registry, args: dict[str, Any]) -> CallToolResult:
    out = verify_market_claim(
        reg,
        claim=args["claim"],
        asserted_value=args.get("asserted_value"),
        asserted_unit=args.get("asserted_unit"),
        as_of=args.get("as_of"),
    )
    links: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []
    if out.get("strata_range") is not None and out.get("state_hash"):
        links = _tam_resource_links(reg, {**out, "scenarios": []})
        next_actions = _tam_next_actions(out)
    return tool_result(out, links=links, next_actions=next_actions)


def _h_get_report_for_tam(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    # Async: it may fall back to the durable Postgres store (server._call_tool awaits).
    return get_report_for_tam(reg, state_hash=args["state_hash"])


def _h_export_report(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    # Async: shares the cache-then-durable-store TAM resolution (server awaits).
    return export_report(
        reg,
        state_hash=args["state_hash"],
        format=str(args.get("format", "html")),
        branding=args.get("branding"),
    )


def _h_list_primitives(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    return list_primitives(
        reg,
        tier=args.get("tier"),
        dimension=args.get("dimension"),
        query=args.get("query"),
        limit=int(args.get("limit", 50)),
        offset=int(args.get("offset", 0)),
    )


def _h_build_tam(reg: Registry, args: dict[str, Any]) -> CallToolResult:
    return _tam_result(
        reg,
        build_tam(
            reg,
            concept_slug=args["concept_slug"],
            primitive_overrides=args.get("primitive_overrides"),
            framework_assumptions=args.get("framework_assumptions"),
        ),
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


def _h_add_portfolio_company(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from .portfolio_tools import add_portfolio_company

    return add_portfolio_company(
        reg,
        name=str(args.get("name", "")),
        domain=str(args.get("domain", "")),
        vertical=(str(args["vertical"]) if args.get("vertical") else None),
        market_concept_slug=(
            str(args["market_concept_slug"]) if args.get("market_concept_slug") else None
        ),
        size=bool(args.get("size", False)),
    )


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


def _h_get_report(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from ..report import assemble_report

    slug = str(args.get("concept_slug", "")).strip()
    if not slug:
        return {"error": "provide concept_slug"}
    try:
        report = assemble_report(reg, slug)
    except RegistryError as exc:
        return {"error": "no_such_concept", "detail": str(exc)}
    return report.model_dump(mode="json")


def _h_save_primitive(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .user_primitive_tools import save_primitive

    return save_primitive(reg, payload=dict(args.get("payload") or {}))


def _h_submit_feedback(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .feedback_tools import submit_feedback

    return submit_feedback(reg, payload=dict(args.get("payload") or {}))


def _h_list_feedback(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .feedback_tools import list_feedback

    return list_feedback(reg, status=args.get("status"))


def _h_apply_feedback(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .feedback_tools import apply_feedback

    raw_payload = args.get("primitive_payload")
    payload: dict[str, Any] | None = dict(raw_payload) if isinstance(raw_payload, dict) else None
    return apply_feedback(reg, feedback_id=int(args["feedback_id"]), primitive_payload=payload)


def _h_list_my_primitives(reg: Registry, _args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .user_primitive_tools import list_my_primitives

    return list_my_primitives(reg)


def _h_admin_list_feedback(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .admin_tools import admin_list_feedback

    return admin_list_feedback(
        reg,
        status=args.get("status"),
        kind=args.get("kind"),
        org_id=args.get("org_id"),
        limit=int(args.get("limit", 100)),
    )


def _h_admin_promote_correction(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .admin_tools import admin_promote_correction

    return admin_promote_correction(reg, feedback_id=int(args["feedback_id"]))


def _h_report_sourcing_gap(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .sourcing_gap_tools import report_sourcing_gap

    return report_sourcing_gap(reg, payload=dict(args.get("payload") or {}))


def _h_record_session_reasoning(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .trace_tools import record_session_reasoning

    return record_session_reasoning(reg, payload=dict(args.get("payload") or {}))


def _h_sense_check(reg: Registry, args: dict[str, Any]) -> dict[str, Any]:
    from .sense_check_tool import sense_check_tool

    return sense_check_tool(
        reg,
        players=list(args.get("players", [])),
        concept_slug=args.get("concept_slug"),
    )


def _h_list_sourcing_gaps(reg: Registry, args: dict[str, Any]) -> Awaitable[dict[str, Any]]:
    from .sourcing_gap_tools import list_sourcing_gaps

    return list_sourcing_gaps(
        reg,
        status=args.get("status"),
        scope=str(args.get("scope", "org")),
        limit=int(args.get("limit", 50)),
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
    "add_portfolio_company": {
        "description": (
            "[WRITE] Add ONE company to your org's portfolio (idempotent on domain; "
            "a re-add with new vertical/market info updates the row). An explicit "
            "market_concept_slug must exist in the registry — an unknown slug is an "
            "honest error with suggestions, never a fuzzy reroute. Optional "
            "size=true sizes it immediately (registry-first, offline-safe). "
            "Gated by STRATA_PORTFOLIO_ENABLED."
        ),
        "inputSchema": schemas.ADD_PORTFOLIO_COMPANY,
        "handler": _h_add_portfolio_company,
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
    "save_primitive": {
        "description": (
            "[WRITE] Save a sourced primitive to your org's PRIVATE bank — durable in "
            "Postgres, org-scoped. visibility/org_id are forced server-side and a "
            "modeled / analyst-tier number is rejected (Q20). Readable back at /bank, "
            "GET /me/primitives, and via list_my_primitives."
        ),
        "inputSchema": schemas.SAVE_PRIMITIVE,
        "handler": _h_save_primitive,
        "annotations": _WRITE,
    },
    "list_my_primitives": {
        "description": (
            "[READ] List the private primitives in your org's bank (the ones an agent "
            "or you saved). RLS-scoped to your org."
        ),
        "inputSchema": schemas.LIST_MY_PRIMITIVES,
        "handler": _h_list_my_primitives,
        "annotations": _READ,
    },
    "get_report": {
        "description": (
            "[READ] Assemble the full sourced market report for a concept — the "
            "analysis-question answers, per-method equations, and provenance. "
            "Registry-only, no LLM. The forwardable PDF lives at /tam/<hash>/report."
        ),
        "inputSchema": schemas.GET_REPORT,
        "handler": _h_get_report,
        "annotations": _READ,
    },
    "submit_feedback": {
        "description": (
            "[WRITE] Flag a bad assumption, a failed query, a wrong primitive, or "
            "missing data on a tam/primitive/concept/framework/query/report. Stored "
            "org-scoped so the team can triage and improve the tool. Commentary "
            "only — never changes a sourced number (E1). Readable at /feedback, "
            "GET /feedback, and via list_feedback."
        ),
        "inputSchema": schemas.SUBMIT_FEEDBACK,
        "handler": _h_submit_feedback,
        "annotations": _WRITE,
    },
    "list_feedback": {
        "description": (
            "[READ] List your org's flags (optionally by status: open/triaged/"
            "resolved/wontfix). RLS-scoped to your org."
        ),
        "inputSchema": schemas.LIST_FEEDBACK,
        "handler": _h_list_feedback,
        "annotations": _READ,
    },
    "apply_feedback": {
        "description": (
            "[WRITE] Accept a primitive_correction / missing_data flag and write "
            "the fix into the data layer: create an org-private primitive (from "
            "primitive_payload or the flag's suggested_value), resolve the flag, "
            "and link the new primitive. Same fence as save_primitive — a modeled "
            "/ analyst-tier number is rejected (Q20). Closes the flag→fix→improve "
            "loop; never mutates an existing sourced number (E1)."
        ),
        "inputSchema": schemas.APPLY_FEEDBACK,
        "handler": _h_apply_feedback,
        "annotations": _WRITE,
    },
    "get_report_for_tam": {
        "description": (
            "[READ] Assemble the full sourced market report BOUND to a specific TAM "
            "(by state_hash from size_tam/build_tam) — so the report's numbers match "
            "the exact (possibly what-if) TAM you steered, not a fresh re-size."
        ),
        "inputSchema": schemas.GET_REPORT_FOR_TAM,
        "handler": _h_get_report_for_tam,
        "annotations": _READ,
    },
    "export_report": {
        "description": (
            "[READ] Export the ENTIRE professional report for a TAM (by state_hash) in "
            "one call: premium structured sections + a self-contained Altimeter-grade "
            "HTML deck (+ base64 PDF when format=pdf and WeasyPrint is available) + "
            "chart specs + citations + next_actions. The forwardable deliverable Maya "
            "emails to the IC — bound to the exact TAM, every figure sourced (Q20)."
        ),
        "inputSchema": schemas.EXPORT_REPORT,
        "handler": _h_export_report,
        "annotations": _READ,
    },
    "verify_market_claim": {
        "description": (
            "[READ] Verify an AI-generated market claim against Strata's sourced data: "
            "returns a verdict (supported / partially_supported / unsupported / "
            "unverifiable), the sourced range + spread, method families, and cited "
            "inputs. An unknown claim is unverifiable — never a synthesized number (Q20)."
        ),
        "inputSchema": schemas.VERIFY_MARKET_CLAIM,
        "handler": _h_verify_market_claim,
        "annotations": _READ,
    },
    "admin_list_feedback": {
        "description": (
            "[READ · ADMIN] List feedback across EVERY org's queue (newest-first). "
            "Restricted to orgs on STRATA_ADMIN_ORGS. Filter by status/kind/org_id. "
            "Each row carries its originating org_id. The owner's cross-tenant view "
            "of what users are flagging across all accounts."
        ),
        "inputSchema": schemas.ADMIN_LIST_FEEDBACK,
        "handler": _h_admin_list_feedback,
        "annotations": _READ,
    },
    "admin_promote_correction": {
        "description": (
            "[WRITE · ADMIN] Promote one org-private correction (by feedback_id) into "
            "the SHARED bank everyone reads: re-validates through the shared-bank fence "
            "(a modeled / analyst-tier number is rejected — Q20), resolves the flag, and "
            "RETURNS the committable data/primitives/<slug>.yaml. Does not write disk "
            "server-side; run `strata admin promote` in a checkout to commit it."
        ),
        "inputSchema": schemas.ADMIN_PROMOTE_CORRECTION,
        "handler": _h_admin_promote_correction,
        "annotations": _WRITE,
    },
    "report_sourcing_gap": {
        "description": (
            "[WRITE] Record that sourced data was MISSING for a query / role — so the "
            "miss becomes ranked demand instead of vanishing. Call this when "
            "resolve_market returns matched=false or verify_market_claim is "
            "unverifiable. De-duplicated (a repeat bumps hit_count). Commentary on "
            "supply, never a number (E1)."
        ),
        "inputSchema": schemas.REPORT_SOURCING_GAP,
        "handler": _h_report_sourcing_gap,
        "annotations": _WRITE,
    },
    "list_sourcing_gaps": {
        "description": (
            "[READ] List sourcing gaps, most-demanded first (hit_count desc). "
            "scope='org' (default) = your workspace; scope='all' = every workspace "
            "ranked platform-wide (ADMIN only). The demand-ranked connector / "
            "sourcing backlog."
        ),
        "inputSchema": schemas.LIST_SOURCING_GAPS,
        "handler": _h_list_sourcing_gaps,
        "annotations": _READ,
    },
    "sense_check": {
        "description": (
            "[READ] Market-share-implied TAM cross-check: Σ(top-player revenue) / "
            "Σ(market share), with sensitivity band, revenue floor, leverage, residual, "
            "per-player consistency, and explicit assumptions. ALWAYS MODELED (Q20) — "
            "shares are analyst estimates, so the payload carries modeled=true and is "
            "never a sourced number. revenue is a number, or edgar_ticker pulls a "
            "sourced TOTAL-company revenue from SEC EDGAR (live, gated by "
            "STRATA_MCP_LIVE_CONNECTORS=1). Optional concept_slug cross-checks the "
            "implied TAM against the curated market's sourced scenario range."
        ),
        "inputSchema": schemas.SENSE_CHECK,
        "handler": _h_sense_check,
        "annotations": _READ_NET,
    },
    "record_session_reasoning": {
        "description": (
            "[WRITE] Attach your reasoning / chain-of-thought / plan for THIS session "
            "so a captured trace is diagnosable, not just reproducible. The server "
            "records every tool call automatically; this adds the *why* it can't see. "
            "Provide session_id (or rely on the active one from X-Strata-Trace-Session), "
            "reasoning, and an optional outcome tag "
            "(ok|unsourced|unverifiable|error|flagged)."
        ),
        "inputSchema": schemas.RECORD_SESSION_REASONING,
        "handler": _h_record_session_reasoning,
        "annotations": _WRITE,
    },
}


def call_tool(
    reg: Registry, name: str, arguments: dict[str, Any]
) -> dict[str, Any] | CallToolResult | Awaitable[dict[str, Any]]:
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(
            f"unknown tool {name!r}", code=CODE_INVALID_INPUT, remediation="check the tool name"
        )
    handler: _Handler = spec["handler"]
    return handler(reg, arguments or {})
