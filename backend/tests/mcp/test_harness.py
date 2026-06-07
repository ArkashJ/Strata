"""MCP report-harness tests (Phases 0-5).

Covers the structured-result builder, the error taxonomy payload, the
report-bound-to-TAM fix (GAP-1), verify_market_claim verdicts, the resources
read round-trip, and the chart spec builders. All pure / offline — no network,
no LLM, no DB.
"""

from __future__ import annotations

import asyncio

import pytest

from strata.evaluator import size_concept
from strata.evaluator.engine import EvalOverrides, OverrideValue
from strata.guards.fence import ModeledFenceError, validate_and_fence_primitive
from strata.mcp import charts
from strata.mcp.errors import CODE_PRIMITIVE_NOT_FOUND, ToolError
from strata.mcp.resources import read_resource_doc
from strata.mcp.result import tool_result
from strata.mcp.server import load_registry
from strata.mcp.tools import (
    _h_size_tam,
    _h_verify_market_claim,
    get_report_for_tam,
    verify_market_claim,
)
from strata.report import (
    assemble_premium_report_for_tam,
    assemble_report,
    assemble_report_for_tam,
)

_CONCEPT = "doc-gen-pc-insurance"


@pytest.fixture
def reg():
    return load_registry()


# --- P0: result builder + error taxonomy -----------------------------------


def test_tool_result_shape() -> None:
    res = tool_result(
        {"value": 1, "as_of": "2026"},
        links=[{"uri": "strata://primitive/x", "name": "x"}, {"uri": "/p/x", "name": "web"}],
        next_actions=[{"tool": "size_tam"}],
    )
    assert res.isError is False
    assert res.structuredContent is not None
    # next_actions + resource_links are embedded in structuredContent.
    assert res.structuredContent["next_actions"] == [{"tool": "size_tam"}]
    assert len(res.structuredContent["resource_links"]) == 2
    # Only the scheme-qualified link becomes a ResourceLink content block.
    link_blocks = [c for c in res.content if getattr(c, "type", None) == "resource_link"]
    assert len(link_blocks) == 1
    # TextContent JSON fallback is always present.
    assert any(getattr(c, "type", None) == "text" for c in res.content)


def test_error_taxonomy_payload() -> None:
    exc = ToolError(
        "primitive 'x' not found", code=CODE_PRIMITIVE_NOT_FOUND, remediation="list_primitives"
    )
    payload = exc.to_payload()
    assert payload["error"]["code"] == CODE_PRIMITIVE_NOT_FOUND
    assert payload["error"]["retriable"] is False
    assert payload["error"]["remediation"] == "list_primitives"
    # Positional message stays backward-compatible (default code).
    assert ToolError("boom").to_payload()["error"]["code"] == "TOOL_ERROR"


# --- P3: report bound to TAM (GAP-1) ---------------------------------------


def test_assemble_report_for_tam_binds_to_tam(reg) -> None:
    base_tam = size_concept(reg, _CONCEPT)
    base_report = assemble_report_for_tam(reg, base_tam)

    # Override a sourced input by a large factor → the TAM-bound report numbers
    # must move, while the concept-level report (a fresh size) is unchanged.
    iu = next(iu for sc in base_tam.scenarios for iu in sc.inputs_used if iu.value and iu.unit)
    overrides = EvalOverrides(
        primitive_overrides={
            iu.primitive_slug: OverrideValue(value=(iu.value or 1.0) * 10.0, unit=iu.unit)  # type: ignore[arg-type]
        }
    )
    swung_tam = size_concept(reg, _CONCEPT, overrides=overrides)
    swung_report = assemble_report_for_tam(reg, swung_tam)

    base_vals = {a.question_id: a.value for a in base_report.answers if a.value is not None}
    swung_vals = {a.question_id: a.value for a in swung_report.answers if a.value is not None}
    # At least one numeric answer changed because the report is bound to the TAM.
    assert any(base_vals.get(q) != swung_vals.get(q) for q in base_vals), (
        "overriding an input must change the TAM-bound report numbers"
    )

    # The concept-level report (sizes fresh) matches the base, not the override.
    concept_report = assemble_report(reg, _CONCEPT)
    concept_vals = {a.question_id: a.value for a in concept_report.answers if a.value is not None}
    assert concept_vals == base_vals


def test_get_report_for_tam_resolves_cached_hash(reg) -> None:
    res = _h_size_tam(reg, {"concept_slug": _CONCEPT})
    state_hash = res.structuredContent["state_hash"]
    # get_report_for_tam is async (it may fall back to the durable store); drive it.
    report = asyncio.run(get_report_for_tam(reg, state_hash=state_hash))
    assert report["concept_slug"] == _CONCEPT
    assert report["answers"]
    # The premium $1M view is bound to the same TAM.
    assert report["premium"]["state_hash"] == state_hash


def test_get_report_for_tam_unknown_hash_raises(reg) -> None:
    with pytest.raises(ToolError):
        asyncio.run(get_report_for_tam(reg, state_hash="0" * 64))


# --- P4: verify_market_claim verdicts --------------------------------------


def test_verify_supported(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    mid = (min(s.value for s in tam.scenarios) + max(s.value for s in tam.scenarios)) / 2
    name = reg.concepts[_CONCEPT].name
    out = verify_market_claim(reg, claim=name, asserted_value=mid)
    assert out["verdict"] == "supported"
    assert out["strata_range"]["low"] <= mid <= out["strata_range"]["high"]


def test_verify_unsupported(reg) -> None:
    name = reg.concepts[_CONCEPT].name
    out = verify_market_claim(reg, claim=name, asserted_value=1e30)
    assert out["verdict"] == "unsupported"


def test_verify_unverifiable_never_synthesizes(reg) -> None:
    out = verify_market_claim(reg, claim="completely-unknown-market-zzz-9999")
    assert out["verdict"] == "unverifiable"
    assert out["strata_range"] is None


def test_verify_handler_attaches_links(reg) -> None:
    name = reg.concepts[_CONCEPT].name
    res = _h_verify_market_claim(reg, {"claim": name})
    assert res.structuredContent["verdict"] in {"range_only", "supported"}
    # A matched claim carries drill-down + next-action affordances.
    assert res.structuredContent.get("resource_links")
    assert res.structuredContent.get("next_actions")


# --- P1: resources read round-trip -----------------------------------------


def test_resource_read_primitive_and_tam(reg) -> None:
    slug = next(iter(reg.atomic))
    doc = read_resource_doc(reg, f"strata://primitive/{slug}")
    assert doc["slug"] == slug
    assert doc["resource_uri"] == f"strata://primitive/{slug}"

    cdoc = read_resource_doc(reg, f"strata://concept/{_CONCEPT}")
    assert cdoc["slug"] == _CONCEPT

    tam = size_concept(reg, _CONCEPT)
    tdoc = read_resource_doc(reg, f"strata://tam/{tam.state_hash}")
    assert tdoc["state_hash"] == tam.state_hash


def test_resource_read_unknown_kind_raises(reg) -> None:
    with pytest.raises(KeyError):
        read_resource_doc(reg, "strata://nonsense/x")


# --- P2: one fence, both doors (#102) --------------------------------------


def test_fence_rejects_modeled_and_accepts_sourced(reg) -> None:
    # The fence is the SINGLE guard both the REST create path and the MCP
    # save_primitive path call (db.user_primitives re-exports it), so a parity
    # check on the guard itself proves both doors behave identically.
    modeled = next(
        (p for p in reg.atomic.values() if p.source.tier.value == "community-modeled"), None
    )
    sourced = next((p for p in reg.atomic.values() if p.source.tier.value == "regulator"), None)
    assert sourced is not None, "fixture needs at least one regulator-tier primitive"

    payload = sourced.model_dump(mode="json")
    fenced = validate_and_fence_primitive(payload, org_id="org-test")
    assert fenced["visibility"] == "private"
    assert fenced["org_id"] == "org-test"

    if modeled is not None:
        with pytest.raises(ModeledFenceError):
            validate_and_fence_primitive(modeled.model_dump(mode="json"), org_id="org-test")


# --- P5: chart spec builders -----------------------------------------------


def test_chart_builders_return_valid_specs(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    all_charts = charts.build_all_charts(tam)
    for kind in charts.VEGA_KINDS:
        assert kind in all_charts
        assert all_charts[kind]["format"] == "vega-lite"
        assert all_charts[kind]["spec"]["$schema"].startswith("https://vega")
    for kind in charts.MERMAID_KINDS:
        assert all_charts[kind]["format"] == "mermaid"
        assert all_charts[kind]["spec"]["diagram"].startswith("graph")
    assert charts.build_chart(tam, "no-such-kind") is None


# --- P4: premium report anatomy --------------------------------------------


def test_premium_report_sections_and_sources(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    pr = assemble_premium_report_for_tam(reg, tam)
    # Editorial headline + a defensible range bound to THIS tam.
    assert pr.concept_slug == _CONCEPT
    assert pr.state_hash == tam.state_hash
    assert pr.range_mid is not None
    # The $1M skeleton always leads with an executive summary.
    keys = [s.key for s in pr.sections]
    assert keys[0] == "executive_summary"
    assert "triangulation" in keys
    assert "sources_appendix" not in keys  # sources live in pr.sources, not a section
    # Sources appendix is deduped by primitive; limitations are honest, not empty filler.
    slugs = [p.primitive_slug for p in pr.sources]
    assert len(slugs) == len(set(slugs)), "sources appendix must dedup by primitive"
    # A section with no sourced answers is flagged a gap, never fabricated.
    for s in pr.sections:
        if s.is_gap:
            assert all(a.status == "gap" for a in s.answers)


def test_premium_report_unsizable_is_honest(reg) -> None:
    # build_premium_report with no TAM degrades to gaps, never invented figures.
    from strata.report import assemble_report, build_premium_report

    base = assemble_report(reg, _CONCEPT)
    pr = build_premium_report(None, base)
    assert pr.range_mid is None
    assert "unsizable" in pr.headline.lower()
    assert pr.limitations  # the unsizable caveat is surfaced
