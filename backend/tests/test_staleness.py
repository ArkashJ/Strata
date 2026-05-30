"""Wave 1 / AC1.7 — staleness from the source freshness SLA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from strata.staleness import is_stale, staleness_days


@dataclass
class _Src:
    freshness_sla_days: int | None


def test_no_sla_is_never_stale() -> None:
    assert is_stale(date(2020, 1, 1), _Src(None), date(2026, 1, 1)) is False


def test_within_sla_is_fresh() -> None:
    assert is_stale(date(2025, 12, 1), _Src(365), date(2026, 1, 1)) is False


def test_past_sla_is_stale() -> None:
    assert is_stale(date(2024, 1, 1), _Src(365), date(2026, 1, 1)) is True
    assert staleness_days(date(2024, 1, 1), date(2026, 1, 1)) > 365
