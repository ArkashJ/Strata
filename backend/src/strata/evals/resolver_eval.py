"""Resolver regression eval harness (Wave 1 / AC1.5).

Runs a golden set of market queries through the registry-first resolver
(deterministic, no LLM / network needed — ``match_concept`` + ``size_concept``)
and scores each against an expected concept, lens, and order-of-magnitude.
Reports a pass-rate; CI fails when it drops below a baseline.

    uv run python -m strata.evals.resolver_eval --assert-baseline 0.8

The golden expectations are *derived from the current evaluator* (see
``golden.yaml``), so this is a true regression guard: a change that silently
re-routes a query, flips a lens, or moves a TAM by an order of magnitude drops
the pass-rate and fails the gate.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..evaluator import size_concept
from ..loader import load_data_dir
from ..registry import Registry
from ..resolver.match import match_concept


@dataclass(frozen=True, slots=True)
class GoldenCase:
    query: str
    expected_concept: str
    expected_lens: str | None
    magnitude: int | None  # floor(log10(tam midpoint))


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: GoldenCase
    matched_concept: str | None
    passed: bool
    reason: str


def _magnitude(value: float) -> int | None:
    return math.floor(math.log10(value)) if value > 0 else None


def evaluate_case(reg: Registry, case: GoldenCase) -> CaseResult:
    matched = match_concept(reg, case.query)
    if matched != case.expected_concept:
        return CaseResult(case, matched, False, f"concept {matched!r} != {case.expected_concept!r}")
    try:
        # matched == case.expected_concept (a str) here, post the guard above.
        tam = size_concept(reg, case.expected_concept)
    except Exception as exc:  # evaluator regression
        return CaseResult(case, matched, False, f"size_concept raised: {exc.__class__.__name__}")

    if case.expected_lens is not None:
        lenses = {s.lens.value for s in tam.scenarios}
        if case.expected_lens not in lenses:
            return CaseResult(case, matched, False, f"lens {case.expected_lens!r} not in {lenses}")

    if case.magnitude is not None:
        mid = sum(s.value for s in tam.scenarios) / max(1, len(tam.scenarios))
        got = _magnitude(mid)
        # Allow ±1 order of magnitude (triangulation spread is real).
        if got is None or abs(got - case.magnitude) > 1:
            return CaseResult(case, matched, False, f"magnitude {got} != {case.magnitude}±1")

    return CaseResult(case, matched, True, "ok")


def load_golden(path: Path) -> list[GoldenCase]:
    raw: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
    return [
        GoldenCase(
            query=c["query"],
            expected_concept=c["expected_concept"],
            expected_lens=c.get("expected_lens"),
            magnitude=c.get("magnitude"),
        )
        for c in raw
    ]


def run_eval(reg: Registry, golden: list[GoldenCase]) -> tuple[float, list[CaseResult]]:
    results = [evaluate_case(reg, c) for c in golden]
    passed = sum(1 for r in results if r.passed)
    return (passed / len(results) if results else 0.0), results


_GOLDEN_PATH = Path(__file__).resolve().parent / "golden.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strata.evals.resolver_eval", description=__doc__)
    parser.add_argument("--assert-baseline", type=float, default=None)
    parser.add_argument(
        "--data-dir", type=Path, default=Path(__file__).resolve().parents[4] / "data"
    )
    parser.add_argument("--golden", type=Path, default=_GOLDEN_PATH)
    args = parser.parse_args(argv)

    reg = Registry.from_loaded(load_data_dir(args.data_dir))
    golden = load_golden(args.golden)
    pass_rate, results = run_eval(reg, golden)

    print(f"Resolver eval — {len(golden)} cases, pass-rate {pass_rate:.2%}")
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"  [{mark}] {r.case.query[:48]:48} {r.reason}")

    if args.assert_baseline is not None and pass_rate < args.assert_baseline:
        print(f"FAILED baseline: {pass_rate:.2%} < {args.assert_baseline:.2%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
