"""Cross-record validator.

Checks that span multiple records:
- concept↔primitive linkage
- framework ``applicable_to`` honored when set
- Q4 unit-signature compatibility between framework inputs and bound primitives
- Q39 lens-tag agreement between concept and framework
- variant ``scope`` resolves to a known concept (no silent typos)
- 30%-overlap warning between primary/secondary scenarios
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..evaluator.engine import EvaluatorError, size_concept
from ..evaluator.formula import FormulaSyntaxError, FormulaUnitError, identifiers, infer_unit, parse
from ..models import Unit
from ..registry import Registry, RegistryError


def _resolved_input_unit(registry: Registry, slug: str) -> Unit | None:
    """Return the unit a framework-input binding resolves to, or None if unknown.

    A binding may point at an atomic primitive or a composite (same-unit set
    op, Q3); the composite carries its own ``unit``. Returning None lets the
    caller emit a single 'unknown primitive' issue for either kind.
    """
    if slug in registry.atomic:
        return registry.atomic[slug].unit
    if slug in registry.composite:
        return registry.composite[slug].unit
    return None


# Two scenarios within this fraction of each other → the secondary lens isn't
# doing strategic work. Surfaced as a warning, not an error.
SECONDARY_LENS_OVERLAP_THRESHOLD = 0.30


class CrossRecordSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class CrossRecordIssue:
    code: str
    severity: CrossRecordSeverity
    slug: str
    message: str


def cross_record_check(registry: Registry) -> list[CrossRecordIssue]:
    issues: list[CrossRecordIssue] = []
    issues.extend(_concept_measurement_links(registry))
    issues.extend(_framework_variant_checks(registry))
    issues.extend(_framework_role_coverage(registry))
    issues.extend(_framework_formula_coherence(registry))
    issues.extend(_secondary_lens_overlap_warning(registry))
    issues.extend(_question_answers_resolvable(registry))
    return issues


def _framework_formula_coherence(registry: Registry) -> list[CrossRecordIssue]:
    """Phase 2: the ``Framework.formula`` is load-bearing, so validate it at load.

    Per framework: parse the formula (closed AST — never ``eval``), assert every
    identifier is a declared ``FrameworkInput.name``, and run the unit algebra.
    The dimensional output-unit match is deferred: a bare ``unit_signature``
    omits the implicit per-X denominator on intensive inputs, so a sound product
    dimension can't be derived yet (the unit algebra still rejects ``+``/``min``
    over mismatched units and ``logistic``/``curve`` over non-dimensionless
    operands)."""
    out: list[CrossRecordIssue] = []
    for fw in registry.frameworks.values():
        try:
            ast = parse(fw.formula)
        except FormulaSyntaxError as exc:
            out.append(
                CrossRecordIssue(
                    code="cross.formula_syntax_error",
                    severity=CrossRecordSeverity.ERROR,
                    slug=fw.slug,
                    message=f"formula {fw.formula!r} did not parse: {exc}",
                )
            )
            continue
        declared = {inp.name for inp in fw.inputs}
        unknown = sorted(identifiers(ast) - declared)
        if unknown:
            out.append(
                CrossRecordIssue(
                    code="cross.formula_unknown_identifier",
                    severity=CrossRecordSeverity.ERROR,
                    slug=fw.slug,
                    message=f"formula references undeclared input(s): {unknown}",
                )
            )
            continue
        inputs_by_name = {inp.name: inp for inp in fw.inputs}
        try:
            infer_unit(ast, inputs_by_name, fw.formula)
        except FormulaUnitError as exc:
            out.append(
                CrossRecordIssue(
                    code="cross.formula_unit_incoherent",
                    severity=CrossRecordSeverity.ERROR,
                    slug=fw.slug,
                    message=str(exc),
                )
            )
    return out


def _concept_measurement_links(registry: Registry) -> list[CrossRecordIssue]:
    out: list[CrossRecordIssue] = []
    for concept in registry.concepts.values():
        for slug in concept.measurements:
            try:
                registry.primitive(slug)
            except RegistryError:
                out.append(
                    CrossRecordIssue(
                        code="cross.concept_missing_measurement",
                        severity=CrossRecordSeverity.ERROR,
                        slug=concept.slug,
                        message=f"measurement {slug!r} not in registry",
                    )
                )
    return out


def _framework_variant_checks(registry: Registry) -> list[CrossRecordIssue]:
    """Per-variant: scope resolves to a concept; lens tag agrees with the
    concept; ``applicable_to`` honored; every bound primitive exists, is an
    atomic primitive, and matches the input's unit signature (Q4).
    """
    out: list[CrossRecordIssue] = []
    for fw in registry.iter_frameworks():
        inputs_by_name = {i.name: i for i in fw.inputs}
        for variant in fw.variants:
            concept = registry.concepts.get(variant.scope)
            if concept is None:
                # At v0.2 every variant scope is a concept slug. Region/sector
                # variants land later; until then a missing concept is a typo.
                out.append(
                    CrossRecordIssue(
                        code="cross.variant_unknown_scope",
                        severity=CrossRecordSeverity.ERROR,
                        slug=fw.slug,
                        message=(
                            f"variant scope={variant.scope!r} does not match any concept; "
                            f"region/sector variants are not yet supported"
                        ),
                    )
                )
                continue
            allowed = {concept.analysis_lens.primary}
            if concept.analysis_lens.secondary is not None:
                allowed.add(concept.analysis_lens.secondary)
            if fw.lens not in allowed:
                out.append(
                    CrossRecordIssue(
                        code="cross.lens_tag_mismatch",
                        severity=CrossRecordSeverity.ERROR,
                        slug=fw.slug,
                        message=(
                            f"framework lens={fw.lens.value} does not match concept "
                            f"{concept.slug!r} lens "
                            f"primary={concept.analysis_lens.primary.value}"
                            + (
                                f" / secondary={concept.analysis_lens.secondary.value}"
                                if concept.analysis_lens.secondary is not None
                                else ""
                            )
                        ),
                    )
                )
            if fw.applicable_to and concept.slug not in fw.applicable_to:
                out.append(
                    CrossRecordIssue(
                        code="cross.applicable_to_violation",
                        severity=CrossRecordSeverity.ERROR,
                        slug=fw.slug,
                        message=(
                            f"variant scope {concept.slug!r} not in applicable_to "
                            f"{list(fw.applicable_to)}"
                        ),
                    )
                )
            for input_name, primitive_slug in variant.default_inputs.items():
                input_def = inputs_by_name.get(input_name)
                if input_def is None:
                    out.append(
                        CrossRecordIssue(
                            code="cross.variant_unknown_input",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} binds unknown input "
                                f"name {input_name!r}; framework inputs are "
                                f"{sorted(inputs_by_name)}"
                            ),
                        )
                    )
                    continue
                bound_unit = _resolved_input_unit(registry, primitive_slug)
                if bound_unit is None:
                    out.append(
                        CrossRecordIssue(
                            code="cross.variant_unknown_primitive",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} input {input_name!r} "
                                f"points at unknown primitive {primitive_slug!r} "
                                f"(neither atomic nor composite)"
                            ),
                        )
                    )
                    continue
                if not bound_unit.is_compatible_with(input_def.unit_signature):
                    out.append(
                        CrossRecordIssue(
                            code="cross.unit_signature_mismatch",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} input {input_name!r}: "
                                f"primitive {primitive_slug!r} unit "
                                f"(kind={bound_unit.kind.value}, "
                                f"dimension={bound_unit.dimension.value}) "
                                f"incompatible with signature "
                                f"(kind={input_def.unit_signature.kind.value}, "
                                f"dimension={input_def.unit_signature.dimension.value})"
                            ),
                        )
                    )
    return out


def _framework_role_coverage(registry: Registry) -> list[CrossRecordIssue]:
    """Warn when a framework's input names don't cover all required roles for
    its declared lens (Q39 / REQUIRED_PRIMITIVE_ROLES).

    Surfaced as a WARNING, not an error, because v0.2 frameworks intentionally
    use simplified 2-input versions; full role coverage lands in later milestones.
    """
    from ..models._common import REQUIRED_PRIMITIVE_ROLES

    out: list[CrossRecordIssue] = []
    for fw in registry.iter_frameworks():
        required = REQUIRED_PRIMITIVE_ROLES.get(fw.lens)
        if required is None:
            continue
        input_names = {inp.name for inp in fw.inputs}
        missing = set(required) - input_names
        if missing:
            out.append(
                CrossRecordIssue(
                    code="cross.framework_missing_roles",
                    severity=CrossRecordSeverity.WARNING,
                    slug=fw.slug,
                    message=(
                        f"framework {fw.slug!r} lens={fw.lens.value} missing roles: "
                        f"{', '.join(sorted(missing))} "
                        f"(v0.2 simplification — full roles land later)"
                    ),
                )
            )
    return out


def _secondary_lens_overlap_warning(registry: Registry) -> list[CrossRecordIssue]:
    """When a concept declares a secondary lens, dry-run both lens scenarios
    and warn if they land within ``SECONDARY_LENS_OVERLAP_THRESHOLD`` of each
    other.

    Only ``EvaluatorError`` is caught (e.g. concept with no applicable variants
    — expected); any other exception is allowed to propagate so an evaluator
    regression doesn't silently disable this check.
    """
    out: list[CrossRecordIssue] = []
    for concept in registry.concepts.values():
        if concept.analysis_lens.secondary is None:
            continue
        try:
            tam = size_concept(registry, concept.slug)
        except (EvaluatorError, RegistryError):
            # Both are already reported by the per-variant checks above.
            continue
        primary_lens = concept.analysis_lens.primary
        secondary_lens = concept.analysis_lens.secondary
        primary_vals = [s.value for s in tam.scenarios if s.lens == primary_lens]
        secondary_vals = [s.value for s in tam.scenarios if s.lens == secondary_lens]
        if not (primary_vals and secondary_vals):
            continue
        p = primary_vals[0]
        s = secondary_vals[0]
        denom = max(abs(p), abs(s))
        if denom == 0:
            continue
        if abs(p - s) / denom < SECONDARY_LENS_OVERLAP_THRESHOLD:
            out.append(
                CrossRecordIssue(
                    code="cross.secondary_lens_low_strategic_work",
                    severity=CrossRecordSeverity.WARNING,
                    slug=concept.slug,
                    message=(
                        f"primary ({primary_lens.value}={p:,.0f}) and secondary "
                        f"({secondary_lens.value}={s:,.0f}) scenarios within "
                        f"{int(SECONDARY_LENS_OVERLAP_THRESHOLD * 100)}% of each other; "
                        f"secondary lens may not be doing real strategic work"
                    ),
                )
            )
    return out


def _question_answers_resolvable(registry: Registry) -> list[CrossRecordIssue]:
    """PR4 question fence + reachability.

    Two structural guarantees over the curated analysis-question bank:

    (a) THE Q20 FENCE — ERROR ``cross.question_resolves_to_signal``. No question's
        answer may resolve to a quarantined ``registry.signals`` primitive (a
        prediction-market number that must NEVER feed a sized answer). A
        ``concept_measurement`` answer reads ``concept.measurements`` slugs; a
        ``primitive_role`` answer resolves to framework-variant-bound primitive
        slugs. If any such slug is a signal, reject.

    (b) REACHABILITY — WARNING ``cross.question_never_resolves``. A question that
        resolves to a non-gap answer for no concept in the registry is dead
        wiring (a role no applicable framework binds, a measurement no concept
        declares). Surfaced as a warning so the bank can be authored ahead of
        the data it needs, while still flagging permanent typos.
    """
    from ..models import (
        ConceptMeasurementAnswer,
        PrimitiveRoleAnswer,
        QualitativeAnswer,
        TamFieldAnswer,
    )
    from ..report.assembler import assemble_report

    out: list[CrossRecordIssue] = []
    if not registry.questions:
        return out
    signal_slugs = set(registry.signals)

    # Pre-index every framework-variant-bound primitive slug, grouped by the
    # role name it binds — so a primitive_role answer's reach can be checked
    # without re-running the evaluator.
    role_to_slugs: dict[str, set[str]] = {}
    for fw in registry.iter_frameworks():
        for variant in fw.variants:
            for role_name, prim_slug in variant.default_inputs.items():
                role_to_slugs.setdefault(role_name, set()).add(prim_slug)

    # Assemble each concept's report ONCE, then collect the set of question ids
    # that resolved to a non-gap answer anywhere — reachability is membership.
    resolved_anywhere: set[str] = set()
    for concept in registry.concepts.values():
        report = assemble_report(registry, concept.slug)
        for ans in report.answers:
            if ans.status == "answered":
                resolved_anywhere.add(ans.question_id)

    for q in registry.questions.values():
        answer = q.answer
        # (a) Q20 fence — does any reachable target point into the signal quarantine?
        leaked: set[str] = set()
        if isinstance(answer, PrimitiveRoleAnswer):
            for role in answer.roles:
                leaked |= role_to_slugs.get(role, set()) & signal_slugs
        elif isinstance(answer, ConceptMeasurementAnswer):
            for concept in registry.concepts.values():
                leaked |= set(concept.measurements) & signal_slugs
        if leaked:
            out.append(
                CrossRecordIssue(
                    code="cross.question_resolves_to_signal",
                    severity=CrossRecordSeverity.ERROR,
                    slug=q.question_id,
                    message=(
                        f"question {q.question_id!r} could resolve to quarantined "
                        f"signal primitive(s) {sorted(leaked)}; a prediction-market "
                        f"number must never feed a sized answer (Q20)"
                    ),
                )
            )

        # (b) Reachability — tam_field/qualitative answers are concept-data
        # independent (always resolvable in principle), so only the registry-
        # binding strategies are checked for dead wiring.
        if not isinstance(answer, PrimitiveRoleAnswer | ConceptMeasurementAnswer):
            assert isinstance(answer, TamFieldAnswer | QualitativeAnswer)
            continue
        if q.question_id not in resolved_anywhere:
            out.append(
                CrossRecordIssue(
                    code="cross.question_never_resolves",
                    severity=CrossRecordSeverity.WARNING,
                    slug=q.question_id,
                    message=(
                        f"question {q.question_id!r} resolves to a gap for every "
                        f"concept; its role/measurement target is not bound by any "
                        f"applicable framework variant or concept (dead wiring)"
                    ),
                )
            )
    return out
