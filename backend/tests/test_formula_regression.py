"""Phase 2 byte-identical regression: the five legacy frameworks must produce
the exact same TAM ``state_hash`` and per-scenario values after the formula
engine replaced the hard-coded multiply fold."""

from __future__ import annotations

import json
import pathlib

import pytest

from strata.evaluator.engine import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry
from strata.validator.cross_record import cross_record_check

_DATA = pathlib.Path(__file__).resolve().parents[2] / "data"
_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "phase2_golden_tam_hashes.json"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


@pytest.fixture(scope="module")
def golden() -> dict[str, dict[str, object]]:
    return json.loads(_GOLDEN.read_text())


def test_golden_fixture_present(golden: dict[str, dict[str, object]]) -> None:
    assert golden["hashes"], "golden hash fixture is empty"


def test_all_legacy_tam_hashes_byte_identical(
    registry: Registry, golden: dict[str, dict[str, object]]
) -> None:
    drift: list[str] = []
    for slug, expected in golden["hashes"].items():
        tam = size_concept(registry, slug)
        if tam.state_hash != expected:
            drift.append(f"{slug}: {expected} -> {tam.state_hash}")
    assert not drift, "TAM state_hash drift after formula engine:\n" + "\n".join(drift)


def test_all_scenario_values_unchanged(
    registry: Registry, golden: dict[str, dict[str, object]]
) -> None:
    drift: list[str] = []
    for slug, expected in golden["scenario_values"].items():
        tam = size_concept(registry, slug)
        got = [round(s.value, 10) for s in tam.scenarios]
        if got != expected:
            drift.append(f"{slug}: {expected} -> {got}")
    assert not drift, "scenario value drift:\n" + "\n".join(drift)


def test_no_formula_coherence_errors_in_committed_frameworks(registry: Registry) -> None:
    issues = [i for i in cross_record_check(registry) if i.code.startswith("cross.formula")]
    assert not issues, "committed frameworks must pass formula coherence: " + str(
        [(i.code, i.slug) for i in issues]
    )


def test_no_eval_exec_in_formula_package() -> None:
    """Defense in depth: the formula package must contain no dynamic-exec call."""
    pkg = pathlib.Path(__file__).resolve().parents[1] / "src" / "strata" / "evaluator" / "formula"
    banned = ("eval(", "exec(", "compile(", "__import__", "literal_eval", "numexpr")
    for py in pkg.glob("*.py"):
        text = py.read_text()
        for token in banned:
            assert token not in text, f"{py.name} contains banned dynamic-exec token {token!r}"
