"""Regression: EDGAR _parse_fact must tolerate present-but-null fy/fp.

Real SEC XBRL companyconcept facts frequently carry "fy": null / "fp": null
(key present, value None). The original guard keyed on `"fy" in raw`, so
int(None) crashed the parse on live data. Guard on the value instead.
"""

from __future__ import annotations

from strata.connectors.edgar import _parse_fact


def test_parse_fact_tolerates_null_fy_fp() -> None:
    fact = _parse_fact(
        {"val": 34_900_000_000, "form": "10-K", "filed": "2024-03-01", "fy": None, "fp": None}
    )
    assert fact.value == 34_900_000_000
    assert fact.fiscal_year is None
    assert fact.fiscal_period is None


def test_parse_fact_reads_real_fy_fp() -> None:
    fact = _parse_fact({"val": 1.0, "form": "10-K", "filed": "2024-03-01", "fy": 2023, "fp": "FY"})
    assert fact.fiscal_year == 2023
    assert fact.fiscal_period == "FY"


def test_parse_fact_carries_period_start_end() -> None:
    # fy/fp describe the FILING; only start/end identify the period a
    # comparative fact actually covers — they must survive the parse.
    fact = _parse_fact(
        {
            "val": 1.0,
            "form": "10-K",
            "filed": "2025-03-01",
            "fy": 2025,
            "start": "2023-02-01",
            "end": "2024-01-31",
        }
    )
    assert fact.start == "2023-02-01"
    assert fact.end == "2024-01-31"


def test_parse_fact_tolerates_missing_or_null_period() -> None:
    fact = _parse_fact({"val": 1.0, "form": "10-K", "filed": "2024-03-01"})
    assert fact.start == ""
    assert fact.end == ""
    fact = _parse_fact({"val": 1.0, "form": "10-K", "filed": "2024-03-01", "end": None})
    assert fact.end == ""
