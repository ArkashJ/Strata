"""Wave 1 / AC1.5 — the resolver eval harness has ≥20 golden cases and the
current resolver clears the CI baseline (≥0.8 pass-rate)."""

from __future__ import annotations

from pathlib import Path

from strata.evals.resolver_eval import _GOLDEN_PATH, load_golden, run_eval
from strata.loader import load_data_dir
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"
_BASELINE = 0.8


def test_golden_set_has_at_least_twenty() -> None:
    assert len(load_golden(_GOLDEN_PATH)) >= 20


def test_resolver_clears_ci_baseline() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    golden = load_golden(_GOLDEN_PATH)
    pass_rate, results = run_eval(reg, golden)
    failures = [f"{r.case.query}: {r.reason}" for r in results if not r.passed]
    assert pass_rate >= _BASELINE, f"resolver eval {pass_rate:.2%} < {_BASELINE:.0%}: {failures}"
