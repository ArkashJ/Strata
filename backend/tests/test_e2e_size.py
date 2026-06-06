"""End-to-end: ``strata size doc-gen-pc-insurance`` produces two reproducible
scenarios.

Verifies the contract from the lens-aware concept slice: two lens-tagged
scenarios; both pin every input by ``snapshot_sha256``; the analyst-paraphrase
primitive carries the "verify against full text" banner; the TAM hash is
deterministic across reruns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import EvaluatorError, size_concept
from strata.loader import load_data_dir
from strata.models import AnalysisLens, BannerKind, MethodFamily
from strata.registry import Registry

REPO_DATA = Path(__file__).resolve().parents[2] / "data"


def _registry() -> Registry:
    return Registry.from_loaded(load_data_dir(REPO_DATA))


def test_two_scenarios_pinned_to_expected_frameworks() -> None:
    # PR5 added many cost-efficiency / revenue variants that also apply here, so
    # the concept now lands >2 scenarios. The contract that matters: the two
    # original lens-tagged frameworks are still present, each on the right lens,
    # so the paraphrase banner cannot drift onto the wrong scenario.
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    by_framework = {s.framework: s for s in tam.scenarios}
    assert "bottoms-up-cost-efficiency" in by_framework
    assert "top-down-revenue-capture" in by_framework
    assert by_framework["bottoms-up-cost-efficiency"].lens == AnalysisLens.COST_EFFICIENCY
    assert by_framework["top-down-revenue-capture"].lens == AnalysisLens.REVENUE_GENERATION


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
    banner = next(b for b in rev_gen.banners if b.kind == BannerKind.ANALYST_PARAPHRASE)
    assert "Gartner" in banner.message
    assert "verify against full text" in banner.message


def test_cost_efficiency_scenario_has_no_paraphrase_banner() -> None:
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    cost_eff = next(s for s in tam.scenarios if s.lens == AnalysisLens.COST_EFFICIENCY)
    assert all(b.kind != BannerKind.ANALYST_PARAPHRASE for b in cost_eff.banners)


def test_tam_hash_is_stable_across_runs() -> None:
    a = size_concept(_registry(), "doc-gen-pc-insurance")
    b = size_concept(_registry(), "doc-gen-pc-insurance")
    assert a.state_hash == b.state_hash


def test_independence_score_when_method_families_distinct() -> None:
    # PR5's added variants pull in more scenarios (incl. an adoption_curve
    # family), so the score is no longer a clean 1.0; what must hold is that the
    # two original distinct families are still both present and contributing.
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    families = set(tam.method_families_used)
    assert MethodFamily.BOTTOMS_UP_SEATS in families
    assert MethodFamily.TOP_DOWN_SPEND in families
    assert len(families) >= 2
    assert 0.0 < tam.independence_score <= 1.0


def test_inputs_used_carry_enrichment_fields() -> None:
    """InputUsed must have value, name, and unit populated by the evaluator."""
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    for s in tam.scenarios:
        for iu in s.inputs_used:
            assert iu.value is not None, f"{iu.primitive_slug} has no value"
            assert iu.name is not None, f"{iu.primitive_slug} has no name"
            assert iu.unit is not None, f"{iu.primitive_slug} has no unit"


def test_tam_target_carries_concept_name() -> None:
    """TAMTarget.concept_name must be populated by the evaluator."""
    tam = size_concept(_registry(), "doc-gen-pc-insurance")
    assert tam.target.concept_name is not None
    assert len(tam.target.concept_name) > 0


def test_unknown_concept_raises_evaluator_error() -> None:
    with pytest.raises(EvaluatorError):
        size_concept(_registry(), "no-such-concept-slug")
