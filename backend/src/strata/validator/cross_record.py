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
from ..registry import Registry, RegistryError

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
    issues.extend(_secondary_lens_overlap_warning(registry))
    return issues


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
                try:
                    atomic = registry.get_atomic(primitive_slug)
                except RegistryError:
                    out.append(
                        CrossRecordIssue(
                            code="cross.variant_unknown_primitive",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} input {input_name!r} "
                                f"points at unknown atomic primitive {primitive_slug!r}"
                            ),
                        )
                    )
                    continue
                if not atomic.unit.is_compatible_with(input_def.unit_signature):
                    out.append(
                        CrossRecordIssue(
                            code="cross.unit_signature_mismatch",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} input {input_name!r}: "
                                f"primitive {primitive_slug!r} unit "
                                f"(kind={atomic.unit.kind.value}, "
                                f"dimension={atomic.unit.dimension.value}) "
                                f"incompatible with signature "
                                f"(kind={input_def.unit_signature.kind.value}, "
                                f"dimension={input_def.unit_signature.dimension.value})"
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
