"""End-to-end: ``strata size doc-gen-pc-insurance`` produces two reproducible
scenarios.

Verifies the contract from the lens-aware concept slice: two lens-tagged
scenarios; both pin every input by ``snapshot_sha256``; the analyst-paraphrase
primitive carries the "verify against full text" banner; the TAM hash is
deterministic across reruns.
"""

from __future__ import annotations

from pathlib import Path

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.models import AnalysisLens
from strata.registry import Registry

REPO_DATA = Path(__file__).resolve().parents[2] / "data"


def _registry() -> Registry:
    return Registry.from_loaded(load_data_dir(REPO_DATA))


def test_two_scenarios_one_per_lens() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    assert len(tam.scenarios) == 2
    lenses = {s.lens for s in tam.scenarios}
    assert lenses == {AnalysisLens.COST_EFFICIENCY, AnalysisLens.REVENUE_GENERATION}


def test_each_scenario_pins_inputs_by_snapshot_hash() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    for s in tam.scenarios:
        assert s.inputs_used, f"{s.framework} has no inputs_used"
        for iu in s.inputs_used:
            assert len(iu.snapshot_sha256) == 64, iu.snapshot_sha256
            int(iu.snapshot_sha256, 16)  # raises if not hex


def test_paraphrase_scenario_carries_banner() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    rev_gen = next(s for s in tam.scenarios if s.lens == AnalysisLens.REVENUE_GENERATION)
    assert any(b.kind == "analyst-paraphrase" for b in rev_gen.banners)
    banner = next(b for b in rev_gen.banners if b.kind == "analyst-paraphrase")
    assert "Gartner" in banner.message
    assert "verify against full text" in banner.message


def test_cost_efficiency_scenario_has_no_paraphrase_banner() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    cost_eff = next(s for s in tam.scenarios if s.lens == AnalysisLens.COST_EFFICIENCY)
    assert all(b.kind != "analyst-paraphrase" for b in cost_eff.banners)


def test_tam_hash_is_stable_across_runs() -> None:
    a = size_concept(_registry(), "doc-gen-pc-insurance")
    b = size_concept(_registry(), "doc-gen-pc-insurance")
    assert a.slug == b.slug


def test_independence_score_one_when_method_families_distinct() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    # bottoms_up_seats vs top_down_spend → fully independent.
    assert tam.independence_score == 1.0
    assert set(tam.method_families_used) == {"bottoms_up_seats", "top_down_spend"}
