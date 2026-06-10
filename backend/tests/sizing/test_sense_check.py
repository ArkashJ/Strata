"""Unit + CLI tests for the market-share-implied TAM sense-check."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from strata.cli import app
from strata.sizing.sense_check import (
    NOTE_BASIS_UNSPECIFIED,
    NOTE_UNDATED,
    Player,
    SenseCheckError,
    parse_as_of,
    parse_money,
    parse_player,
    parse_share_basis,
    sense_check,
    share_token_warning,
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


def test_combined_share_over_100pct_warns_and_suppresses_band() -> None:
    # Σshare > 100%: a band would exclude its own point estimate, leverage < 1
    # is meaningless, residual negative — all suppressed; floor + warning remain.
    r = sense_check([Player("A", 300e6, 0.6), Player("B", 200e6, 0.6)])
    assert r.combined_share == pytest.approx(1.2)
    assert any("100%" in w for w in r.warnings)
    assert r.implied_low is None
    assert r.implied_high is None
    assert r.leverage is None
    assert r.residual is None
    assert r.revenue_floor == pytest.approx(500e6)


def test_modeled_revenue_warns_q20() -> None:
    r = sense_check([Player("A", 300e6, 0.15)])
    assert not r.all_revenue_sourced
    assert any("MODELED" in w for w in r.warnings)


def test_all_sourced_run_is_still_modeled_q20() -> None:
    # Shares are ALWAYS analyst estimates, so even an all-sourced-revenue run
    # carries the MODELED marker — the label is unconditional (Q20).
    r = sense_check(
        [
            Player("A", 300e6, 0.15, revenue_sourced=True),
            Player("B", 200e6, 0.10, revenue_sourced=True),
        ]
    )
    assert r.all_revenue_sourced
    assert any("MODELED" in w for w in r.warnings)
    assert any("analyst estimates" in w for w in r.warnings)


def test_share_token_warning_flags_the_1_trap() -> None:
    assert share_token_warning("1", 1.0) is not None  # bare '1' → 100%: warn
    assert share_token_warning("100", 1.0) is not None  # bare '100' → 100%: warn
    assert share_token_warning("1.0", 1.0) is None  # explicit decimal: intended
    assert share_token_warning("0.15", 0.15) is None
    assert share_token_warning("15", 0.15) is None


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


# ── time-match guardrail (cofounder feedback: AI coding tools) ────────────────
def test_time_mismatch_warning_fires_past_six_months() -> None:
    # The real case: Cursor's Feb-2026 ARR over its mid-2025 share (~8 months
    # apart) inflated the implied market ~2x — the mismatch must warn.
    r = sense_check([Player("Cursor", 2e9, 0.18, revenue_as_of="2026-02", share_as_of="2025-06")])
    assert any("time-match" in w and "Cursor" in w for w in r.warnings)


def test_time_match_within_six_months_is_clean() -> None:
    r = sense_check([Player("A", 1e9, 0.2, revenue_as_of="2026-02", share_as_of="2025-10")])
    assert not any("time-match" in w for w in r.warnings)


def test_year_only_dates_anchor_mid_year() -> None:
    # A bare year anchors to June: 2025 (→ Jun-2025) vs Feb-2026 is 8 months.
    r = sense_check([Player("A", 1e9, 0.2, revenue_as_of="2026-02", share_as_of="2025")])
    assert any("time-match" in w for w in r.warnings)


def test_absent_dates_note_assumed_time_matched() -> None:
    r = sense_check([Player("A", 1e9, 0.2)])
    assert NOTE_UNDATED in r.assumptions
    # Warnings stay quiet — un-dated inputs soften the output, never shout.
    assert not any("time-match" in w for w in r.warnings)


def test_fully_dated_players_drop_the_undated_note() -> None:
    r = sense_check([Player("A", 1e9, 0.2, revenue_as_of="2026-01", share_as_of="2026-01")])
    assert NOTE_UNDATED not in r.assumptions


def test_bad_as_of_tokens_rejected() -> None:
    with pytest.raises(SenseCheckError):
        parse_as_of("Feb 2026")
    with pytest.raises(SenseCheckError):
        parse_as_of("2026-13")  # month out of range
    with pytest.raises(SenseCheckError):
        sense_check([Player("A", 1e9, 0.2, revenue_as_of="garbage")])
    assert parse_as_of("2026") == "2026"
    assert parse_as_of("2026-02") == "2026-02"
    assert parse_as_of("2026-02-15") == "2026-02-15"


# ── share-basis guardrail (cofounder feedback: Copilot seat-share) ────────────
def test_usage_share_basis_fires_strong_warning() -> None:
    # Copilot's 42% seat-share is not a revenue share — dividing revenue by it
    # understates the implied market.
    r = sense_check([Player("Copilot", 1e9, 0.42, share_basis="usage")])
    assert any("REVENUE share" in w and "understates" in w for w in r.warnings)


def test_revenue_share_basis_is_clean_and_drops_the_note() -> None:
    r = sense_check([Player("A", 1e9, 0.2, share_basis="revenue")])
    assert not any("understates" in w for w in r.warnings)
    assert NOTE_BASIS_UNSPECIFIED not in r.assumptions


def test_unspecified_basis_notes_revenue_assumption() -> None:
    r = sense_check([Player("A", 1e9, 0.2)])
    assert NOTE_BASIS_UNSPECIFIED in r.assumptions


def test_bad_share_basis_rejected() -> None:
    with pytest.raises(SenseCheckError):
        parse_share_basis("seats")
    with pytest.raises(SenseCheckError):
        sense_check([Player("A", 1e9, 0.2, share_basis="mindshare")])


# ── DSL / CSV round-trips for the guardrail fields ────────────────────────────
def test_parse_player_kv_suffixes_round_trip() -> None:
    p = parse_player("Cursor|2b|0.18|rev_date=2026-02|share_date=2025-06|share_basis=usage")
    assert p.revenue == pytest.approx(2e9)
    assert p.revenue_as_of == "2026-02"
    assert p.share_as_of == "2025-06"
    assert p.share_basis == "usage"
    assert p.revenue_sourced is False


def test_parse_player_sourced_flag_coexists_with_kv() -> None:
    p = parse_player("Filer|10b|0.3|sourced|share_basis=revenue|share_date=2026")
    assert p.revenue_sourced is True
    assert p.share_basis == "revenue"
    assert p.share_as_of == "2026"


def test_parse_player_old_specs_unchanged() -> None:
    # Backward compat: the 3- and 4-field shapes parse exactly as before.
    p3 = parse_player("Gong|300m|15")
    assert (p3.revenue_as_of, p3.share_as_of, p3.share_basis) == ("", "", "")
    p4 = parse_player("Salesforce|10b|0.3|sourced")
    assert p4.revenue_sourced is True
    assert (p4.revenue_as_of, p4.share_as_of, p4.share_basis) == ("", "", "")


def test_parse_player_rejects_bad_kv() -> None:
    with pytest.raises(SenseCheckError):
        parse_player("A|1b|0.1|frobnicate=2026")  # unknown key
    with pytest.raises(SenseCheckError):
        parse_player("A|1b|0.1|rev_date=2026|rev_date=2025")  # duplicate key
    with pytest.raises(SenseCheckError):
        parse_player("A|1b|0.1|share_basis=seats")  # bad basis
    with pytest.raises(SenseCheckError):
        parse_player("A|1b|0.1|rev_date=Feb 2026")  # bad date
    with pytest.raises(SenseCheckError):
        parse_player("A|1b|0.1|sourced|bogus")  # bare token past position 4


# ── CLI ───────────────────────────────────────────────────────────────────────
def test_cli_sense_check_standalone() -> None:
    r = runner.invoke(
        app,
        ["sense-check", "--player", "Gong|300m|0.15", "--player", "Clari|200m|0.10"],
    )
    assert r.exit_code == 0, r.stdout
    assert "implied TAM" in r.stdout
    assert "$2.0B" in r.stdout  # money renders via the repo-wide usd() formatter


def test_cli_edgar_token_resolves_sourced_revenue(monkeypatch: pytest.MonkeyPatch) -> None:
    # Monkeypatch the EDGAR lookup so the CLI path stays offline + deterministic.
    import strata.cli as cli
    from strata.sizing.revenue_lookup import ResolvedRevenue

    def _fake_resolve(ticker: str, **_kw: object) -> ResolvedRevenue:
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik="0000320193",
            entity_name="Salesforce, Inc.",
            revenue=34_900_000_000,
            fiscal_year=2023,
            concept="Revenues",
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?CIK=0000320193",
        )

    monkeypatch.setattr(cli, "resolve_revenue", _fake_resolve)
    r = runner.invoke(app, ["sense-check", "--player", "Salesforce|edgar:CRM|0.30"])
    assert r.exit_code == 0, r.stdout
    assert "resolved Salesforce revenue" in r.stdout
    assert "1/1 revenues sourced" in r.stdout  # EDGAR figure counts as sourced
    # The figure is whole-company revenue: caveat inline + a marked player line.
    assert "TOTAL company revenue" in r.stdout
    assert "(filing, total-co)" in r.stdout


def test_cli_edgar_token_blocked_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    import strata.cli as cli

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("resolve_revenue must not be called when STRATA_OFFLINE=1")

    monkeypatch.setattr(cli, "resolve_revenue", _boom)
    monkeypatch.setenv("STRATA_OFFLINE", "1")
    r = runner.invoke(app, ["sense-check", "--player", "Salesforce|edgar:CRM|0.30"])
    assert r.exit_code == 2  # offline guard fired before any live lookup


def test_cli_overflow_share_prints_floor_only() -> None:
    # Σshare = 120%: no implied-TAM headline, band, leverage, or residual lines —
    # only the revenue floor and the overlap warning are defensible.
    r = runner.invoke(app, ["sense-check", "--player", "A|300m|60", "--player", "B|200m|60"])
    assert r.exit_code == 0, r.stdout
    assert "revenue floor" in r.stdout
    assert "only the revenue floor" in r.stdout  # the >100% warning
    assert "implied TAM     $" not in r.stdout
    assert "sensitivity" not in r.stdout
    assert "leverage" not in r.stdout
    assert "residual" not in r.stdout


def test_cli_share_token_one_warns() -> None:
    # The '1' trap: a bare integer share token landing on exactly 100% warns.
    r = runner.invoke(app, ["sense-check", "--player", "Solo|300m|1"])
    assert r.exit_code == 0, r.stdout
    assert "parsed as 100%" in r.stdout


def test_cli_edgar_spec_enforces_field_count() -> None:
    # The edgar branch must reject malformed specs as loudly as the plain branch.
    r = runner.invoke(app, ["sense-check", "--player", "Salesforce|edgar:CRM"])
    assert r.exit_code == 2
    r = runner.invoke(app, ["sense-check", "--player", "A|edgar:CRM|0.3|x|y"])
    assert r.exit_code == 2


def test_cli_csv_players_parse_directly(tmp_path: Path) -> None:
    # CSV fields go straight into Player — a '|' in a company name must not
    # inject extra pipe-DSL fields, and the optional sourced column is honored.
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "name,revenue,market_share,sourced\nAcme|Pipes Inc,300m,15,\nFiler Co,200m,10,sourced\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["sense-check", "--players-file", str(csv_path)])
    assert r.exit_code == 0, r.stdout
    assert "Acme|Pipes Inc" in r.stdout
    assert "1/2 revenues sourced" in r.stdout
    assert "$2.0B" in r.stdout  # 500m / 25%, via the repo-wide usd() formatter


def test_cli_csv_edgar_rows_share_one_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import strata.cli as cli
    from strata.sizing.revenue_lookup import ResolvedRevenue

    seen_clients: list[object] = []

    def _fake_resolve(ticker: str, **kw: object) -> ResolvedRevenue:
        seen_clients.append(kw.get("client"))
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik="0000000001",
            entity_name=f"{ticker} Corp",
            revenue=1_000_000_000,
            fiscal_year=2024,
            concept="Revenues",
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?CIK=0000000001",
        )

    monkeypatch.setattr(cli, "resolve_revenue", _fake_resolve)
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "name,revenue,market_share\nAlpha,edgar:AAA,10\nBeta,edgar:BBB,20\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["sense-check", "--players-file", str(csv_path)])
    assert r.exit_code == 0, r.stdout
    assert len(seen_clients) == 2
    assert seen_clients[0] is not None
    assert seen_clients[0] is seen_clients[1]  # ONE EDGARClient across rows


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


def test_cli_time_mismatch_and_usage_basis_warn() -> None:
    r = runner.invoke(
        app,
        [
            "sense-check",
            "--player",
            "Cursor|2b|0.18|rev_date=2026-02|share_date=2025-06",
            "--player",
            "Copilot|1b|0.42|share_basis=usage",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "time-match" in r.stdout  # 8-month gap fires the warning
    assert "understates" in r.stdout  # usage-basis strong warning
    assert NOTE_UNDATED in r.stdout  # Copilot is un-dated → assumptions note
    assert NOTE_BASIS_UNSPECIFIED in r.stdout  # Cursor's basis unspecified


def test_cli_edgar_period_end_threads_into_revenue_as_of(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The filing already knows WHEN its revenue is measured — a stale share date
    # against it must fire the time-match warning with no rev_date typed.
    import strata.cli as cli
    from strata.sizing.revenue_lookup import ResolvedRevenue

    def _fake_resolve(ticker: str, **_kw: object) -> ResolvedRevenue:
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik="0000000001",
            entity_name="Cursor Listed Twin Inc.",
            revenue=2_000_000_000,
            fiscal_year=2026,
            concept="Revenues",
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?CIK=0000000001",
            period_end="2026-01-31",
        )

    monkeypatch.setattr(cli, "resolve_revenue", _fake_resolve)
    r = runner.invoke(app, ["sense-check", "--player", "Cursor|edgar:CRSR|0.18|share_date=2025-06"])
    assert r.exit_code == 0, r.stdout
    assert "2026-01-31" in r.stdout and "time-match" in r.stdout


def test_cli_edgar_rejects_explicit_rev_date(monkeypatch: pytest.MonkeyPatch) -> None:
    import strata.cli as cli

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("conflict must be rejected before any live lookup")

    monkeypatch.setattr(cli, "resolve_revenue", _boom)
    r = runner.invoke(app, ["sense-check", "--player", "A|edgar:CRM|0.3|rev_date=2026-02"])
    assert r.exit_code == 2
    assert "fiscal-period end" in r.output


def test_cli_csv_guardrail_columns_round_trip(tmp_path: Path) -> None:
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "name,revenue,market_share,sourced,revenue_as_of,share_as_of,share_basis\n"
        "Cursor,2b,18,,2026-02,2025-06,revenue\n"
        "Copilot,1b,42,,,,usage\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["sense-check", "--players-file", str(csv_path)])
    assert r.exit_code == 0, r.stdout
    assert "time-match" in r.stdout  # Cursor's 8-month gap
    assert "understates" in r.stdout  # Copilot's usage basis
    assert NOTE_UNDATED in r.stdout  # Copilot has no dates
