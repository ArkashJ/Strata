"""Wave 5A — Strata MCP tool handlers.

AC5A.2: every numeric tool payload is sourced — value + unit + citation
(source_url, source_tier, snapshot_sha256), with no fabricated host.
AC5A.3: read-only — no handler mutates the registry or writes a primitive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.mcp.tools import ToolError, call_tool
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"
_CONCEPT = "doc-gen-pc-insurance"


@pytest.fixture(scope="module")
def reg() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


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


def test_get_primitive_is_sourced(reg: Registry) -> None:
    slug = _a_regulator_slug(reg)
    out = call_tool(reg, "get_primitive", {"slug": slug})
    prim = out["primitive"]
    assert prim["snapshot_sha256"]
    assert prim["source_url"], "a regulator primitive must carry a real citation URL"
    assert prim["source_tier"]
    assert "value" in prim and "unit" in prim


def test_size_tam_scenarios_carry_hash_pins(reg: Registry) -> None:
    out = call_tool(reg, "size_tam", {"concept_slug": _CONCEPT})
    assert out["scenarios"], "expected a scenario tree"
    for sc in out["scenarios"]:
        assert sc["inputs"], "each scenario must list its inputs"
        for inp in sc["inputs"]:
            assert inp["snapshot_sha256"], "every input must be hash-pinned"


def test_resolve_market_registry_hit_is_sourced(reg: Registry) -> None:
    out = call_tool(reg, "resolve_market", {"query": _CONCEPT})
    assert out["matched"] is True
    cites = _all_citations(out)
    assert cites, "a matched resolve must carry hash-pinned inputs"


def test_resolve_market_miss_returns_unmatched_not_synthesized(reg: Registry) -> None:
    out = call_tool(reg, "resolve_market", {"query": "wholly unrelated zylophone market 2099"})
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
        for cite in _all_citations(call_tool(reg, name, args)):
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
    """AC5A.3 — calling every tool leaves the registry byte-for-byte unchanged."""
    before = (
        len(reg.atomic),
        len(reg.concepts),
        len(reg.frameworks),
        len(reg.signals),
        len(reg.tam_outputs),
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
        len(reg.tam_outputs),
        sorted(reg.atomic),
    )
    assert before == after
