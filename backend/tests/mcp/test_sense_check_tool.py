"""MCP `sense_check` tool tests — agent parity with `strata sense-check`.

All pure / offline: edgar_ticker resolution is env-gated and the live path is
monkeypatched. The payload must ALWAYS carry the machine-readable MODELED (Q20)
marker, mirror the CLI result structurally, and suppress the band when shares
overlap past 100%.
"""

from __future__ import annotations

import pytest

from strata.mcp.errors import CODE_INVALID_INPUT, CODE_LIVE_DISABLED, ToolError
from strata.mcp.sense_check_tool import sense_check_tool
from strata.mcp.server import load_registry
from strata.mcp.tools import TOOLS, call_tool


@pytest.fixture
def reg():
    return load_registry()


def test_tool_is_registered() -> None:
    spec = TOOLS["sense_check"]
    assert spec["inputSchema"]["required"] == ["players"]
    assert "MODELED" in spec["description"]


def test_basic_payload_shape_and_unconditional_modeled(reg) -> None:
    out = sense_check_tool(
        reg,
        players=[
            {"name": "Gong", "revenue": 300e6, "market_share": 0.15},
            {"name": "Clari", "revenue": 200e6, "market_share": 0.10},
        ],
    )
    assert out["modeled"] is True  # machine-readable Q20 marker
    assert "MODELED" in out["modeled_label"]
    assert out["implied_tam"] == pytest.approx(2e9)
    assert out["revenue_floor"] == pytest.approx(500e6)
    assert out["implied_low"] is not None and out["implied_high"] is not None
    assert out["leverage"] == pytest.approx(4.0)
    assert out["residual"] == pytest.approx(1.5e9)
    assert len(out["per_player"]) == 2
    assert out["assumptions"]
    assert any("MODELED" in w for w in out["warnings"])


def test_all_sourced_payload_still_modeled(reg, monkeypatch: pytest.MonkeyPatch) -> None:
    # Even when every revenue is an EDGAR filing, shares are analyst estimates —
    # the modeled marker must not disappear (Q20).
    import strata.mcp.sense_check_tool as mod
    from strata.sizing.revenue_lookup import ResolvedRevenue

    monkeypatch.setenv("STRATA_MCP_LIVE_CONNECTORS", "1")

    def _fake_resolve(ticker: str, **_kw: object) -> ResolvedRevenue:
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik="0000000001",
            entity_name=f"{ticker} Corp",
            revenue=1_000_000_000,
            fiscal_year=2024,
            concept="Revenues",
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?CIK=0000000001",
        )

    monkeypatch.setattr(mod, "resolve_revenue", _fake_resolve)
    out = sense_check_tool(
        reg,
        players=[
            {"name": "Alpha", "edgar_ticker": "AAA", "market_share": 0.10},
            {"name": "Beta", "edgar_ticker": "BBB", "market_share": 0.20},
        ],
    )
    assert out["all_revenue_sourced"] is True
    assert out["modeled"] is True
    assert any("MODELED" in w for w in out["warnings"])
    # EDGAR figures are whole-company: tagged + caveated, never unmarked.
    assert all(p["revenue_note"] == "filing, total-co" for p in out["per_player"])
    assert any("TOTAL company revenue" in w for w in out["warnings"])


def test_edgar_ticker_gated_like_live_connectors(reg, monkeypatch: pytest.MonkeyPatch) -> None:
    # Same env gate as get_connector_data: no STRATA_MCP_LIVE_CONNECTORS=1, no
    # live SEC call — an honest CODE_LIVE_DISABLED error, never a silent fetch.
    import strata.mcp.sense_check_tool as mod

    monkeypatch.delenv("STRATA_MCP_LIVE_CONNECTORS", raising=False)

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("resolve_revenue must not be called when the live gate is off")

    monkeypatch.setattr(mod, "resolve_revenue", _boom)
    with pytest.raises(ToolError) as exc_info:
        sense_check_tool(
            reg, players=[{"name": "Alpha", "edgar_ticker": "AAA", "market_share": 0.10}]
        )
    assert exc_info.value.code == CODE_LIVE_DISABLED


def test_overflow_shares_null_band(reg) -> None:
    out = sense_check_tool(
        reg,
        players=[
            {"name": "A", "revenue": 300e6, "market_share": 0.6},
            {"name": "B", "revenue": 200e6, "market_share": 0.6},
        ],
    )
    assert out["implied_low"] is None
    assert out["implied_high"] is None
    assert out["leverage"] is None
    assert out["residual"] is None
    assert out["revenue_floor"] == pytest.approx(500e6)
    assert any("100%" in w for w in out["warnings"])


def test_concept_cross_reference(reg) -> None:
    slug = "doc-gen-pc-insurance"  # a known sizable curated concept
    out = sense_check_tool(
        reg,
        players=[{"name": "A", "revenue": 2e9, "market_share": 0.5}],
        concept_slug=slug,
    )
    assert out["concept"] == slug
    assert out["sourced_range"] is not None
    assert out["verdict"] in {"within", "above", "below"}


def test_unknown_concept_is_honest_error(reg) -> None:
    with pytest.raises(ToolError):
        sense_check_tool(
            reg,
            players=[{"name": "A", "revenue": 2e9, "market_share": 0.5}],
            concept_slug="no-such-concept-zzz",
        )


def test_bad_player_rows_raise_invalid_input(reg) -> None:
    with pytest.raises(ToolError) as e1:
        sense_check_tool(reg, players=[{"name": "A", "market_share": 0.5}])  # no revenue source
    assert e1.value.code == CODE_INVALID_INPUT
    with pytest.raises(ToolError) as e2:
        sense_check_tool(
            reg,
            players=[{"name": "A", "revenue": 1e9, "edgar_ticker": "AAA", "market_share": 0.5}],
        )
    assert e2.value.code == CODE_INVALID_INPUT


def test_call_tool_dispatch(reg) -> None:
    out = call_tool(
        reg,
        "sense_check",
        {"players": [{"name": "A", "revenue": 4e8, "market_share": 0.2}]},
    )
    assert isinstance(out, dict)
    assert out["modeled"] is True
    assert out["implied_tam"] == pytest.approx(2e9)
