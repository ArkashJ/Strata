"""PR4 — the load-bearing Q20 fence around the question-report assembler.

Two structural guarantees are pinned here:

1. THE PROVENANCE FENCE (assembler). Every numeric answer in a sized concept's
   report carries either ``provenance`` (≥1 registry row) or a non-null
   ``synthesis`` (a reproducible TAM-field derivation). The assembler physically
   cannot emit an authored number — this test asserts that for EVERY numeric
   answer across a concept's whole report.

2. THE SIGNAL FENCE (validator). A question whose answer would resolve to a
   quarantined ``registry.signals`` (prediction-market) primitive is rejected by
   ``validate`` as an ERROR — a Kalshi probability must never feed a sized answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.models import AnalysisQuestion, ConceptMeasurementAnswer
from strata.models.question import AnswerStrategy, QuestionCategory
from strata.registry import Registry
from strata.report.assembler import assemble_report
from strata.validator.cross_record import CrossRecordSeverity, cross_record_check

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SIZED_CONCEPT = "demo-ai-sales-ops-us"  # triangulated, both method families present


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def test_every_numeric_answer_in_a_report_is_sourced_or_synthesized(registry: Registry) -> None:
    """The fence: no numeric answer may be unsourced (Q20 — no authored numbers)."""
    report = assemble_report(registry, _SIZED_CONCEPT)

    numeric = [a for a in report.answers if a.status == "answered" and a.value is not None]
    # The sized demo concept must actually exercise the fence (not vacuously pass).
    assert numeric, "expected at least one numeric answer for a sized concept"

    violations = [a.question_id for a in numeric if not a.provenance and a.synthesis is None]
    assert violations == [], (
        f"numeric answers without provenance or synthesis (authored numbers leaked): {violations}"
    )

    # And the inverse half of the fence: every gap carries no value and no provenance.
    for ans in report.answers:
        if ans.status == "gap":
            assert ans.value is None
            assert ans.provenance == ()


def test_question_resolving_to_a_signal_is_rejected_by_validate(registry: Registry) -> None:
    """A question whose answer would reach a quarantined signal is an ERROR."""
    assert registry.signals, "fixture must have quarantined signals to exercise the fence"
    signal_slug = next(iter(registry.signals))

    # Taint one real concept so its measurements include a prediction-market signal,
    # then add a concept_measurement question that would read it. The validator must
    # refuse it as a hard error — the signal can never feed a sized answer.
    cslug, concept = next(iter(registry.concepts.items()))
    registry.concepts[cslug] = concept.model_copy(
        update={"measurements": (*concept.measurements, signal_slug)}
    )
    registry.questions["Q-SIG-999"] = AnalysisQuestion(
        kind="analysis_question",
        question_id="Q-SIG-999",
        prompt="What do the competing measurements say?",
        category=QuestionCategory.MARKET_SIZE,
        answer=ConceptMeasurementAnswer(strategy=AnswerStrategy.CONCEPT_MEASUREMENT),
        narrative_template="Measurements span {low} to {high}.",
        gap_text="No sourced measurements for this concept.",
        schema_version=1,
    )

    issues = cross_record_check(registry)
    signal_errors = [
        i
        for i in issues
        if i.code == "cross.question_resolves_to_signal" and i.severity is CrossRecordSeverity.ERROR
    ]
    assert any(i.slug == "Q-SIG-999" for i in signal_errors), (
        "validate did not reject a question that resolves to a quarantined signal"
    )
