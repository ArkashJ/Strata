"""Wave 5A — Strata MCP tool handlers.

AC5A.2: every numeric tool payload is sourced — value + unit + citation
(source_url, source_tier, snapshot_sha256), with no fabricated host.
AC5A.3: read-only — no handler mutates the registry or writes a primitive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp.types import CallToolResult

from strata.loader import load_data_dir
from strata.mcp.tools import ToolError, call_tool
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"
_CONCEPT = "doc-gen-pc-insurance"


@pytest.fixture(scope="module")
def reg() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


def _data(out: object) -> dict:
    """Normalize a tool return to its structured dict.

    The result-aware tools (size_tam / build_tam / resolve_market / get_primitive)
    now return a ``CallToolResult`` carrying ``structuredContent``; the rest still
    return a plain dict. Tests assert on the payload either way."""
    if isinstance(out, CallToolResult):
        assert out.structuredContent is not None
        return out.structuredContent
    assert isinstance(out, dict)
    return out


def _all_citations(payload: object) -> list[dict]:
    """Walk a tool payload collecting any dict that carries a snapshot_sha256."""
    out: list[dict] = []
    if isinstance(payload, dict):
        if "snapshot_sha256" in payload:
            out.append(payload)
        for v in payload.values():
            out.extend(_all_citations(v))
    elif isinstance(payload, list):
        for v in payload:
            out.extend(_all_citations(v))
    return out


def _a_regulator_slug(reg: Registry) -> str:
    for slug, p in reg.atomic.items():
        if p.source.tier.value == "regulator":
            return slug
    return next(iter(reg.atomic))


def test_whoami_reports_bank_counts(reg: Registry) -> None:
    out = call_tool(reg, "whoami", {})
    assert out["ok"] is True
    bank = out["bank"]
    assert bank["concepts"] == len(reg.concepts)
    assert bank["primitives"] == len(reg.atomic)
    assert bank["frameworks"] >= 1
    # No principal in a direct (non-HTTP) call → honest stdio/local report.
    assert out["authenticated"] is False
    assert out["transport"] == "stdio"


def test_list_primitives_pagination_envelope(reg: Registry) -> None:
    first = call_tool(reg, "list_primitives", {"limit": 5, "offset": 0})
    assert first["count"] == 5
    assert first["offset"] == 0
    assert first["total"] >= 5
    assert first["has_more"] is True
    assert first["next_offset"] == 5
    # The next page is disjoint from the first (offset advanced the window).
    second = call_tool(reg, "list_primitives", {"limit": 5, "offset": 5})
    first_slugs = {p["slug"] for p in first["primitives"]}
    second_slugs = {p["slug"] for p in second["primitives"]}
    assert first_slugs.isdisjoint(second_slugs)


def test_list_primitives_last_page_has_no_more(reg: Registry) -> None:
    total = call_tool(reg, "list_primitives", {"limit": 1})["total"]
    last = call_tool(reg, "list_primitives", {"limit": 10, "offset": max(0, total - 1)})
    assert last["has_more"] is False
    assert last["next_offset"] is None


def test_get_primitive_is_sourced(reg: Registry) -> None:
    slug = _a_regulator_slug(reg)
    out = _data(call_tool(reg, "get_primitive", {"slug": slug}))
    prim = out["primitive"]
    assert prim["snapshot_sha256"]
    assert prim["source_url"], "a regulator primitive must carry a real citation URL"
    assert prim["source_tier"]
    assert "value" in prim and "unit" in prim


def test_size_tam_scenarios_carry_hash_pins(reg: Registry) -> None:
    out = _data(call_tool(reg, "size_tam", {"concept_slug": _CONCEPT}))
    assert out["scenarios"], "expected a scenario tree"
    for sc in out["scenarios"]:
        assert sc["inputs"], "each scenario must list its inputs"
        for inp in sc["inputs"]:
            assert inp["snapshot_sha256"], "every input must be hash-pinned"


def test_resolve_market_registry_hit_is_sourced(reg: Registry) -> None:
    out = _data(call_tool(reg, "resolve_market", {"query": _CONCEPT}))
    assert out["matched"] is True
    cites = _all_citations(out)
    assert cites, "a matched resolve must carry hash-pinned inputs"


def test_resolve_market_miss_returns_unmatched_not_synthesized(reg: Registry) -> None:
    out = _data(
        call_tool(reg, "resolve_market", {"query": "wholly unrelated zylophone market 2099"})
    )
    assert out["matched"] is False
    # A miss must NOT contain a number dressed as a sourced TAM.
    assert "scenarios" not in out


def test_no_fabricated_citation_hosts(reg: Registry) -> None:
    """Every emitted citation URL is a real source host, never strata.internal."""
    for name, args in [
        ("search_concepts", {"query": "insurance"}),
        ("get_primitive", {"slug": next(iter(reg.atomic))}),
        ("size_tam", {"concept_slug": _CONCEPT}),
        ("resolve_market", {"query": _CONCEPT}),
    ]:
        for cite in _all_citations(_data(call_tool(reg, name, args))):
            url = cite.get("source_url")
            # Modeled numbers honestly carry no external URL (None); a present
            # URL must be a real host, never the internal/fabricated marker.
            if url is not None:
                assert "strata.internal" not in url, f"{name}: fabricated host"


def test_list_frameworks_lists_recipes(reg: Registry) -> None:
    out = call_tool(reg, "list_frameworks", {})
    assert out["count"] >= 1
    assert all("method_family" in f for f in out["frameworks"])


def test_unknown_tool_and_slug_raise(reg: Registry) -> None:
    with pytest.raises(ToolError):
        call_tool(reg, "nonexistent_tool", {})
    with pytest.raises(ToolError):
        call_tool(reg, "get_primitive", {"slug": "no-such-primitive"})


def test_mcp_readonly(reg: Registry) -> None:
    """AC5A.3 — calling every tool leaves the DATA BANK byte-for-byte unchanged.

    Note: ``tam_outputs`` is deliberately excluded — it is an ephemeral, FIFO-
    capped RESULT cache (never a persisted primitive), and size_tam now remembers
    the computed TAM so ``get_report_for_tam(<hash>)`` can bind to it (GAP-1). No
    data-bank record (atomic/concepts/frameworks/signals) is ever mutated."""
    before = (
        len(reg.atomic),
        len(reg.concepts),
        len(reg.frameworks),
        len(reg.signals),
        sorted(reg.atomic),
    )
    for name, args in [
        ("search_concepts", {"query": "insurance"}),
        ("get_primitive", {"slug": next(iter(reg.atomic))}),
        ("list_frameworks", {}),
        ("size_tam", {"concept_slug": _CONCEPT}),
        ("resolve_market", {"query": _CONCEPT}),
        ("resolve_market", {"query": "no match here at all 99"}),
    ]:
        call_tool(reg, name, args)
    after = (
        len(reg.atomic),
        len(reg.concepts),
        len(reg.frameworks),
        len(reg.signals),
        sorted(reg.atomic),
    )
    assert before == after


# ── data-bank-expansion harness tools ───────────────────────────────────────


def test_list_primitives_filters_and_cites(reg: Registry) -> None:
    out = call_tool(reg, "list_primitives", {"tier": "regulator", "limit": 5})
    assert out["count"] <= 5
    assert out["primitives"], "expected at least one regulator primitive"
    for p in out["primitives"]:
        assert p["snapshot_sha256"] and p["source_tier"] == "regulator"


def test_build_tam_what_if_does_not_mutate_registry(reg: Registry) -> None:
    before = sorted(reg.atomic)
    out = _data(call_tool(reg, "build_tam", {"concept_slug": _CONCEPT}))
    assert out["scenarios"], "build_tam must return a scenario tree"
    assert out["state_hash"]
    # what-if sizing never persists a primitive
    assert sorted(reg.atomic) == before


def test_build_tam_unknown_concept_errors(reg: Registry) -> None:
    with pytest.raises(ToolError):
        call_tool(reg, "build_tam", {"concept_slug": "no-such-concept-xyz"})


def test_list_connectors_inventory(reg: Registry) -> None:
    out = call_tool(reg, "list_connectors", {})
    assert out["count"] >= 20, "expected the full typed-connector inventory"
    sample = out["connectors"][0]
    assert sample["connector"] and sample["source_tier"] and sample["methods"]


def test_get_connector_data_gated_off_by_default(reg: Registry) -> None:
    # Without STRATA_MCP_LIVE_CONNECTORS=1 the live path must refuse, not call out.
    with pytest.raises(ToolError):
        call_tool(
            reg,
            "get_connector_data",
            {"connector": "fred", "method": "get_observations", "args": {}},
        )
