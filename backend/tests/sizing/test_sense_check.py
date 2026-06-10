"""Unit + CLI tests for the market-share-implied TAM sense-check."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from strata.cli import app
from strata.sizing.sense_check import (
    Player,
    SenseCheckError,
    parse_money,
    parse_player,
    sense_check,
)

runner = CliRunner()
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


# ── parsing ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("31e9", 31e9),
        ("31000000000", 31e9),
        ("3.1b", 3.1e9),
        ("950m", 950e6),
        ("$1.2B", 1.2e9),
        ("12,000", 12000.0),
        ("2t", 2e12),
    ],
)
def test_parse_money(token: str, expected: float) -> None:
    assert parse_money(token) == pytest.approx(expected)


def test_parse_player_normalizes_share_and_money() -> None:
    p = parse_player("Gong|300m|15")  # 15 → 0.15 (percent)
    assert p.name == "Gong"
    assert p.revenue == pytest.approx(300e6)
    assert p.market_share == pytest.approx(0.15)
    assert parse_player("Clari|200m|0.10").market_share == pytest.approx(0.10)


def test_parse_player_bad_spec_raises() -> None:
    with pytest.raises(SenseCheckError):
        parse_player("only-two|300m")


# ── math ─────────────────────────────────────────────────────────────────────
def test_consistent_shares_imply_one_tam() -> None:
    # 300m@15% and 200m@10% both imply a $2.0B market → spread 1.0, clean.
    r = sense_check([Player("Gong", 300e6, 0.15), Player("Clari", 200e6, 0.10)])
    assert r.implied_tam == pytest.approx(2e9)  # 500m / 0.25
    assert r.revenue_floor == pytest.approx(500e6)
    assert r.combined_share == pytest.approx(0.25)
    assert r.spread_ratio == pytest.approx(1.0)


def test_inconsistent_shares_flag_spread() -> None:
    # 300m@15% → 2.0B but 200m@4% → 5.0B: a 2.5x disagreement is flagged.
    r = sense_check([Player("A", 300e6, 0.15), Player("B", 200e6, 0.04)])
    assert r.spread_ratio == pytest.approx(2.5)
    assert any("disagree" in w for w in r.warnings)


def test_combined_share_over_100pct_warns() -> None:
    r = sense_check([Player("A", 300e6, 0.6), Player("B", 200e6, 0.6)])
    assert r.combined_share == pytest.approx(1.2)
    assert any("100%" in w for w in r.warnings)


def test_modeled_revenue_warns_q20() -> None:
    r = sense_check([Player("A", 300e6, 0.15)])
    assert not r.all_revenue_sourced
    assert any("MODELED" in w for w in r.warnings)


def test_cross_check_verdict_within_above_below() -> None:
    scenarios = (1e9, 2e9, 3e9)  # sourced range 1B-3B, mid 2B
    assert (
        sense_check([Player("A", 4e8, 0.2)], sourced_scenarios=scenarios).verdict == "within"
    )  # 2B
    assert (
        sense_check([Player("A", 4e8, 0.05)], sourced_scenarios=scenarios).verdict == "above"
    )  # 8B
    assert (
        sense_check([Player("A", 4e8, 0.8)], sourced_scenarios=scenarios).verdict == "below"
    )  # 0.5B


def test_bad_inputs_raise() -> None:
    with pytest.raises(SenseCheckError):
        sense_check([])
    with pytest.raises(SenseCheckError):
        sense_check([Player("A", -1, 0.1)])
    with pytest.raises(SenseCheckError):
        sense_check([Player("A", 1e9, 1.2)])  # share > 1
    with pytest.raises(SenseCheckError):
        sense_check([Player("A", 1e9, 0.2)], share_tolerance=1.5)  # bad tolerance


# ── defensibility hardening ───────────────────────────────────────────────────
def test_sensitivity_band_brackets_the_point_estimate() -> None:
    r = sense_check([Player("A", 4e8, 0.2)], share_tolerance=0.25)  # 0.4/0.2 = 2.0B
    assert r.implied_low < r.implied_tam < r.implied_high
    assert r.implied_low == pytest.approx(4e8 / 0.25)  # share +25% -> 1.6B
    assert r.implied_high == pytest.approx(4e8 / 0.15)  # share -25% -> ~2.67B


def test_low_combined_share_flags_leverage() -> None:
    # 5% combined share → implied TAM is 20x the captured revenue → fragile.
    r = sense_check([Player("A", 1e8, 0.05)])
    assert r.leverage == pytest.approx(20.0)
    assert any("leveraged" in w for w in r.warnings)


def test_residual_is_implied_minus_floor() -> None:
    r = sense_check([Player("A", 3e8, 0.15), Player("B", 2e8, 0.10)])  # implied 2.0B, floor 0.5B
    assert r.residual == pytest.approx(r.implied_tam - r.revenue_floor)
    assert r.residual == pytest.approx(1.5e9)


def test_sourced_flag_parsed_and_counted() -> None:
    p = parse_player("Salesforce|10b|0.3|sourced")
    assert p.revenue_sourced is True
    r = sense_check([p, Player("Est", 1e9, 0.1)])
    assert r.n_sourced == 1
    assert not r.all_revenue_sourced


def test_result_carries_assumptions() -> None:
    r = sense_check([Player("A", 3e8, 0.15)])
    assert len(r.assumptions) >= 4
    assert any("revenue IN THIS MARKET" in a for a in r.assumptions)


# ── CLI ───────────────────────────────────────────────────────────────────────
def test_cli_sense_check_standalone() -> None:
    r = runner.invoke(
        app,
        ["sense-check", "--player", "Gong|300m|0.15", "--player", "Clari|200m|0.10"],
    )
    assert r.exit_code == 0, r.stdout
    assert "implied TAM" in r.stdout
    assert "2,000,000,000" in r.stdout


def test_cli_sense_check_against_curated_concept() -> None:
    # demo-ai-sales-ops-us has a sourced scenario range; the check should compare.
    r = runner.invoke(
        app,
        [
            "sense-check",
            "--concept",
            "demo-ai-sales-ops-us",
            "--player",
            "PlayerOne|2b|0.5",
            "-d",
            str(_DATA_DIR),
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "cross-check vs demo-ai-sales-ops-us" in r.stdout
    assert "verdict:" in r.stdout
