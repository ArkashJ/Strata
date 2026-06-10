"""The pure question assembler (PR4, engine layer 2).

``assemble_report(registry, concept_slug)`` walks the curated analysis-question
bank, filters to the questions applicable to one concept, and resolves each one
against already-sourced registry objects + the in-process evaluator. It is
**pure**: no LLM, no network, no Exa, no connectors, no ``source.url`` fetch —
only registry models and ``size_concept``.

Every emitted :class:`ResolvedAnswer` passes that model's runtime fence (a
numeric ``value`` needs provenance or a non-null ``synthesis``), so the
assembler physically cannot emit a number it did not pull from a registry
primitive or the computed ``TAMOutput`` (Q20). A concept the evaluator cannot
size degrades every numeric question to an honest gap with the question's
``resource_target`` — never a fabricated figure (the ``onchain-analytics-
software`` case).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..evaluator import EvaluatorError, size_concept
from ..models import (
    Aggregation,
    AnalysisQuestion,
    AnswerProvenance,
    AtomicPrimitive,
    Concept,
    ConceptMeasurementAnswer,
    ConceptQuestionReport,
    PrimitiveRoleAnswer,
    QualitativeAnswer,
    ResolvedAnswer,
    TamField,
    TamFieldAnswer,
)
from ..models._common import REQUIRED_PRIMITIVE_ROLES, AnalysisLens
from ..models.tam_output import InputUsed, TAMOutput
from ..registry import Registry, RegistryError

# ResolvedAnswer is the per-question row; ConceptQuestionReport is the document.
MarketReport = ConceptQuestionReport


@dataclass(frozen=True, slots=True)
class QuestionBank:
    """Indexed view of the registry's curated analysis questions."""

    by_id: dict[str, AnalysisQuestion]

    @classmethod
    def from_registry(cls, registry: Registry) -> QuestionBank:
        return cls(by_id=dict(registry.questions))

    def applicable_to(self, concept: Concept, registry: Registry) -> list[AnalysisQuestion]:
        """Filter the bank by each question's ``applies_when`` gate.

        Empty gate = always applicable. A lens gate matches if the concept
        declares (primary or secondary) any lens in ``lens_in``; a role gate
        requires every named role to be a valid role for one of the concept's
        lenses; a modifier gate requires the named modifiers to be present;
        ``requires_secondary_lens`` requires the concept to declare a secondary.
        """
        concept_lenses = _concept_lenses(concept)
        valid_roles = _valid_roles_for(concept_lenses)
        present_modifiers = _present_modifiers(concept)
        out: list[AnalysisQuestion] = []
        for q in self.by_id.values():
            if q.lenses and not (set(q.lenses) & concept_lenses):
                continue
            gate = q.applies_when
            if gate.lens_in and not (set(gate.lens_in) & concept_lenses):
                continue
            if gate.requires_secondary_lens and concept.analysis_lens.secondary is None:
                continue
            if not set(gate.requires_role).issubset(valid_roles):
                continue
            if not set(gate.requires_modifier).issubset(present_modifiers):
                continue
            out.append(q)
        return out


def _concept_lenses(concept: Concept) -> set[AnalysisLens]:
    lenses = {concept.analysis_lens.primary}
    if concept.analysis_lens.secondary is not None:
        lenses.add(concept.analysis_lens.secondary)
    return lenses


def _valid_roles_for(lenses: Iterable[AnalysisLens]) -> set[str]:
    roles: set[str] = set()
    for lens in lenses:
        roles.update(REQUIRED_PRIMITIVE_ROLES.get(lens, ()))
    return roles


def _present_modifiers(concept: Concept) -> set[str]:
    mods = concept.modifiers
    present: set[str] = set()
    if mods.opex_conversion is not None:
        present.add("opex_conversion")
    if mods.margin_capture is not None:
        present.add("margin_capture")
    if mods.regulatory_unlock is not None:
        present.add("regulatory_unlock")
    if mods.risk_transfer is not None:
        present.add("risk_transfer")
    return present


def assemble_report(registry: Registry, concept_slug: str) -> MarketReport:
    """Assemble the full question report for one concept (pure, no LLM).

    Sizes the concept once, then delegates to :func:`assemble_report_for_tam` so
    the concept-level entry and a TAM-bound entry share one resolution path. If
    the concept is unsizable the TAM is None and every numeric question degrades
    to an honest gap — never a fabrication."""
    concept = registry.get_concept(concept_slug)
    tam: TAMOutput | None
    try:
        tam = size_concept(registry, concept_slug)
    except (EvaluatorError, RegistryError):
        tam = None
    return _assemble(registry, concept, tam)


def assemble_report_for_tam(registry: Registry, tam: TAMOutput) -> MarketReport:
    """Assemble the report BOUND to a specific TAM (GAP-1 fix).

    Resolves every answer from THIS ``tam`` — its scenarios, method families,
    independence score, scope — with **no re-evaluation**. So a report assembled
    for a what-if TAM (an overridden ``build_tam`` result) reflects the steered
    numbers, not a fresh size of the live concept. The concept is looked up only
    for its non-numeric metadata (definition, modifiers, applicable questions);
    every figure comes off the passed TAM."""
    concept = registry.get_concept(tam.target.concept)
    return _assemble(registry, concept, tam)


def _assemble(registry: Registry, concept: Concept, tam: TAMOutput | None) -> MarketReport:
    bank = QuestionBank.from_registry(registry)
    answers = tuple(
        _resolve(question, concept, registry, tam)
        for question in bank.applicable_to(concept, registry)
    )
    return MarketReport(
        concept_slug=concept.slug,
        concept_name=concept.name,
        answers=answers,
    )


def _resolve(
    question: AnalysisQuestion,
    concept: Concept,
    registry: Registry,
    tam: TAMOutput | None,
) -> ResolvedAnswer:
    answer = question.answer
    if isinstance(answer, PrimitiveRoleAnswer):
        return _resolve_primitive_role(question, answer, tam)
    if isinstance(answer, ConceptMeasurementAnswer):
        return _resolve_concept_measurement(question, answer, concept, registry)
    if isinstance(answer, TamFieldAnswer):
        return _resolve_tam_field(question, answer, tam)
    # Exhaustive over the discriminated union — the remainder is QualitativeAnswer.
    return _resolve_qualitative(question, answer, concept, registry)


# --- gap helper ------------------------------------------------------------


def _gap(question: AnalysisQuestion) -> ResolvedAnswer:
    return ResolvedAnswer(
        question_id=question.question_id,
        prompt=question.prompt,
        category=question.category,
        status="gap",
        narrative=question.gap_text,
        resource_target=question.resource_target,
    )


# --- provenance helpers ----------------------------------------------------


def _provenance_from_input(iu: InputUsed) -> AnswerProvenance:
    return AnswerProvenance(
        primitive_slug=iu.primitive_slug,
        source_url=iu.source_url,
        source_tier=iu.source_tier,
        snapshot_sha256=iu.snapshot_sha256,
        as_of=None,  # InputUsed carries no as_of; left honest-None.
    )


def _provenance_from_atomic(p: AtomicPrimitive) -> AnswerProvenance:
    return AnswerProvenance(
        primitive_slug=p.slug,
        source_url=p.source.url,
        source_tier=p.source.tier.value,
        snapshot_sha256=p.source.snapshot_sha256,
        as_of=p.as_of,
    )


def _safe_render(template: str, ctx: Mapping[str, object]) -> str | None:
    """Render a narrative template over a whitelisted context.

    Returns ``None`` if the template names a token the context does not carry,
    so the caller degrades to a gap rather than printing a literal ``{token}``.
    """
    try:
        return template.format_map(_StrictMap(ctx))
    except KeyError:
        return None


class _StrictMap(dict[str, object]):
    def __missing__(self, key: str) -> object:
        raise KeyError(key)


# --- primitive_role --------------------------------------------------------


def _resolve_primitive_role(
    question: AnalysisQuestion,
    answer: PrimitiveRoleAnswer,
    tam: TAMOutput | None,
) -> ResolvedAnswer:
    if tam is None:
        return _gap(question)
    wanted = set(answer.roles)
    matches: list[InputUsed] = []
    seen: set[str] = set()
    for scenario in tam.scenarios:
        for iu in scenario.inputs_used:
            if iu.role_name in wanted and iu.primitive_slug not in seen:
                matches.append(iu)
                seen.add(iu.primitive_slug)
    matches = [iu for iu in matches if iu.value is not None]
    if not matches:
        return _gap(question)

    provenance = tuple(_provenance_from_input(iu) for iu in matches)
    if answer.aggregation in (Aggregation.VALUE,):
        iu = matches[0]
        value = iu.value
        display = _fmt(value)
        ctx = {
            "value": display,
            "source_name": iu.primitive_slug,
            "source_tier": iu.source_tier or "",
            "snapshot": iu.snapshot_sha256[:12],
        }
    elif answer.aggregation is Aggregation.COUNT:
        value = float(len(matches))
        display = str(len(matches))
        ctx = {"value": display, "count": len(matches)}
    else:  # SPREAD or LIST → low/high across the matched sourced values
        values = sorted(iu.value for iu in matches if iu.value is not None)
        low, high = values[0], values[-1]
        value = high  # representative figure; spread carried in display/ctx
        display = f"{_fmt(low)} - {_fmt(high)}"
        ctx = {
            "value": display,
            "low": _fmt(low),
            "high": _fmt(high),
            "spread": display,
            "count": len(values),
        }

    narrative = _safe_render(question.narrative_template, ctx)
    if narrative is None:
        return _gap(question)
    return ResolvedAnswer(
        question_id=question.question_id,
        prompt=question.prompt,
        category=question.category,
        status="answered",
        value=value,
        display=display,
        narrative=narrative,
        provenance=provenance,
        resource_target=question.resource_target,
    )


# --- concept_measurement ---------------------------------------------------


def _resolve_concept_measurement(
    question: AnalysisQuestion,
    answer: ConceptMeasurementAnswer,
    concept: Concept,
    registry: Registry,
) -> ResolvedAnswer:
    # Only atomic measurements carry a single sourced value; a composite is a
    # set op with no source of its own, so it cannot back a numeric claim here.
    atomics: list[AtomicPrimitive] = []
    for slug in concept.measurements:
        try:
            prim = registry.primitive(slug)
        except RegistryError:
            continue
        if isinstance(prim, AtomicPrimitive):
            atomics.append(prim)
    if not atomics:
        return _gap(question)

    provenance = tuple(_provenance_from_atomic(p) for p in atomics)
    values = sorted(p.value for p in atomics)
    low, high = values[0], values[-1]

    if answer.aggregation is Aggregation.SPREAD and len(values) >= 2:
        value = high
        display = f"{_fmt(low)} - {_fmt(high)}"
        ctx = {
            "value": display,
            "low": _fmt(low),
            "high": _fmt(high),
            "spread": display,
            "ratio": _ratio(low, high),
            "count": len(values),
        }
    elif answer.aggregation is Aggregation.COUNT:
        value = float(len(values))
        display = str(len(values))
        ctx = {"value": display, "count": len(values)}
    else:  # VALUE / LIST / SPREAD-with-one → a single sourced figure
        value = values[0]
        display = _fmt(value)
        ctx = {
            "value": display,
            "source_name": atomics[0].slug,
            "source_tier": atomics[0].source.tier.value,
            "count": len(values),
        }

    narrative = _safe_render(question.narrative_template, ctx)
    if narrative is None:
        return _gap(question)
    return ResolvedAnswer(
        question_id=question.question_id,
        prompt=question.prompt,
        category=question.category,
        status="answered",
        value=value,
        display=display,
        narrative=narrative,
        provenance=provenance,
        resource_target=question.resource_target,
    )


# --- tam_field -------------------------------------------------------------


def _resolve_tam_field(
    question: AnalysisQuestion,
    answer: TamFieldAnswer,
    tam: TAMOutput | None,
) -> ResolvedAnswer:
    if tam is None:
        return _gap(question)
    derived = _tam_field_value(answer.field, tam)
    if derived is None:
        return _gap(question)
    value, display = derived

    n = len(tam.scenarios)
    n_families = len(set(tam.method_families_used))
    synthesis = (
        f"triangulated from {n} sourced scenario(s) across "
        f"{n_families} method famil{'y' if n_families == 1 else 'ies'}, "
        # The web /tam page is retired — the API artifact is the durable ref.
        f"reproducible via GET /tam/{tam.state_hash}"
    )
    ctx = {
        "value": display,
        "low": _fmt(_min_scenario(tam)),
        "high": _fmt(_max_scenario(tam)),
        "count": n,
        "n_methods": n_families,
        "ratio": _ratio(_min_scenario(tam), _max_scenario(tam)),
    }
    narrative = _safe_render(question.narrative_template, ctx)
    if narrative is None:
        return _gap(question)
    # synthesis is non-null → the ResolvedAnswer fence accepts the numeric value.
    return ResolvedAnswer(
        question_id=question.question_id,
        prompt=question.prompt,
        category=question.category,
        status="answered",
        value=value,
        display=display,
        narrative=narrative,
        synthesis=synthesis,
        resource_target=question.resource_target,
    )


def _scenario_values(tam: TAMOutput) -> list[float]:
    return [s.value for s in tam.scenarios]


def _min_scenario(tam: TAMOutput) -> float:
    return min(_scenario_values(tam))


def _max_scenario(tam: TAMOutput) -> float:
    return max(_scenario_values(tam))


def _midpoint(tam: TAMOutput) -> float:
    # Triangulated midpoint = mean of the scenario-value extremes (the same
    # low/high triangulation the UI shows), a pure synthesis of sourced values.
    return (_min_scenario(tam) + _max_scenario(tam)) / 2.0


def _tam_field_value(field: TamField, tam: TAMOutput) -> tuple[float, str] | None:
    """Select one allowlisted field off the computed TAM as ``(value, display)``.

    Every branch reads an already-computed scenario figure — no number is
    invented. Returns ``None`` when the field is not present (e.g. no
    convergence object), so the caller degrades to an honest gap.
    """
    if field is TamField.TRIANGULATED_MID:
        v = _midpoint(tam)
        return v, _fmt(v)
    if field is TamField.RANGE_LOW:
        v = _min_scenario(tam)
        return v, _fmt(v)
    if field is TamField.RANGE_HIGH:
        v = _max_scenario(tam)
        return v, _fmt(v)
    if field is TamField.RANGE_SPREAD_RATIO:
        lo, hi = _min_scenario(tam), _max_scenario(tam)
        if lo <= 0:
            return None
        v = hi / lo
        return v, f"{v:.2f}×"
    if field is TamField.METHOD_FAMILIES_COUNT:
        v = float(len(set(tam.method_families_used)))
        return v, str(int(v))
    if field is TamField.INDEPENDENCE_SCORE:
        return tam.independence_score, f"{tam.independence_score:.2f}"
    if field is TamField.SCENARIO_COUNT:
        v = float(len(tam.scenarios))
        return v, str(int(v))
    if field is TamField.USES_MODELED_INPUTS:
        flag = tam.uses_modeled_composites or tam.uses_synthetic_primitives
        return (1.0 if flag else 0.0), ("yes" if flag else "no")
    # The convergence fields exist only when ≥2 independent families sized it.
    if field is TamField.CONVERGENCE_RATIO:
        if tam.convergence is None:
            return None
        return tam.convergence.ratio, f"{tam.convergence.ratio:.2f}×"
    if field is TamField.CONVERGENCE_LOW:
        if tam.convergence is None:
            return None
        return tam.convergence.low_value, _fmt(tam.convergence.low_value)
    if field is TamField.CONVERGENCE_HIGH:
        if tam.convergence is None:
            return None
        return tam.convergence.high_value, _fmt(tam.convergence.high_value)
    return None  # pragma: no cover - exhaustive over TamField


# --- qualitative -----------------------------------------------------------


def _resolve_qualitative(
    question: AnalysisQuestion,
    answer: QualitativeAnswer,
    concept: Concept,
    registry: Registry,
) -> ResolvedAnswer:
    text = _qualitative_text(answer, concept, registry)
    if text is None:
        return _gap(question)
    # A qualitative answer makes no numeric claim (value=None), so the fence
    # permits empty provenance. The narrative is the sourced text itself.
    return ResolvedAnswer(
        question_id=question.question_id,
        prompt=question.prompt,
        category=question.category,
        status="answered",
        narrative=text,
        resource_target=question.resource_target,
    )


def _qualitative_text(
    answer: QualitativeAnswer,
    concept: Concept,
    registry: Registry,
) -> str | None:
    if answer.source == "definition":
        return concept.definition or None
    if answer.source == "modifier":
        return _modifier_text(answer.modifier_kind, concept)
    if answer.source == "annotation":
        return _annotation_text(concept, registry)
    return None  # pragma: no cover


def _modifier_text(modifier_kind: str | None, concept: Concept) -> str | None:
    mods = concept.modifiers
    if modifier_kind == "regulatory_unlock" and mods.regulatory_unlock is not None:
        m = mods.regulatory_unlock
        return f"Regulatory unlock driven by {m.driver}, effective {m.effective_date.isoformat()}."
    if modifier_kind == "risk_transfer" and mods.risk_transfer is not None:
        return f"Risk transfer on loss basis {mods.risk_transfer.loss_basis}."
    if modifier_kind == "opex_conversion" and mods.opex_conversion is not None:
        return f"Opex conversion with pricing premium {mods.opex_conversion.pricing_premium}."
    if modifier_kind == "margin_capture" and mods.margin_capture is not None:
        return f"Margin capture from middleman {mods.margin_capture.middleman}."
    return None


def _annotation_text(concept: Concept, registry: Registry) -> str | None:
    for ann in registry.annotations.values():
        target = getattr(ann, "target_slug", None) or getattr(ann, "target", None)
        if target == concept.slug:
            body = getattr(ann, "body", None) or getattr(ann, "text", None)
            if isinstance(body, str) and body:
                return body
    return None


# --- formatting ------------------------------------------------------------


def _fmt(value: float | None) -> str:
    """Compact, human display for a sourced figure (display-only)."""
    if value is None:
        return ""
    av = abs(value)
    if av >= 1e12:
        return f"{value / 1e12:.2f}T"
    if av >= 1e9:
        return f"{value / 1e9:.2f}B"
    if av >= 1e6:
        return f"{value / 1e6:.2f}M"
    if av >= 1e3:
        return f"{value / 1e3:.2f}K"
    return f"{value:,.2f}"


def _ratio(low: float, high: float) -> str:
    if low <= 0:
        return ""
    return f"{high / low:.2f}×"


__all__ = ["MarketReport", "QuestionBank", "assemble_report", "assemble_report_for_tam"]
