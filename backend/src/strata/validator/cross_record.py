"""Cross-record validator.

Checks that span multiple records: concept↔primitive linkage, framework
``applicable_to``, lens-tag agreement between concept and framework, and the
30%-overlap warning between primary/secondary scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..registry import Registry, RegistryError


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
    issues.extend(_framework_lens_tag(registry))
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


def _framework_lens_tag(registry: Registry) -> list[CrossRecordIssue]:
    """For every framework variant scoped to a concept, the framework's lens
    must equal that concept's primary or secondary lens.
    """
    out: list[CrossRecordIssue] = []
    for fw in registry.iter_frameworks():
        for variant in fw.variants:
            concept = registry.concepts.get(variant.scope)
            if concept is None:
                # Variant scope might be a region/sector — skip silently.
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
                            f"{concept.slug!r} lens primary={concept.analysis_lens.primary.value}"
                            + (
                                f" / secondary={concept.analysis_lens.secondary.value}"
                                if concept.analysis_lens.secondary is not None
                                else ""
                            )
                        ),
                    )
                )
            # applicable_to honored: when set, the concept must be listed.
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
                try:
                    registry.primitive(primitive_slug)
                except RegistryError:
                    out.append(
                        CrossRecordIssue(
                            code="cross.variant_unknown_primitive",
                            severity=CrossRecordSeverity.ERROR,
                            slug=fw.slug,
                            message=(
                                f"variant scope={variant.scope!r} input {input_name!r} "
                                f"points at unknown primitive {primitive_slug!r}"
                            ),
                        )
                    )
    return out


def _secondary_lens_overlap_warning(registry: Registry) -> list[CrossRecordIssue]:
    """When a concept declares a secondary lens, dry-run both lens scenarios
    and warn if they land within 30% of each other.

    Importing the evaluator here would create a cycle; instead we do a thin
    local multiplication mirroring evaluator.engine.size.
    """
    from ..evaluator.engine import size_concept

    out: list[CrossRecordIssue] = []
    for concept in registry.concepts.values():
        if concept.analysis_lens.secondary is None:
            continue
        try:
            tam = size_concept(registry, concept.slug)
        except Exception:
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
        if abs(p - s) / denom < 0.30:
            out.append(
                CrossRecordIssue(
                    code="cross.secondary_lens_low_strategic_work",
                    severity=CrossRecordSeverity.WARNING,
                    slug=concept.slug,
                    message=(
                        f"primary ({primary_lens.value}={p:,.0f}) and secondary "
                        f"({secondary_lens.value}={s:,.0f}) scenarios within 30% "
                        f"of each other; secondary lens may not be doing real strategic work"
                    ),
                )
            )
    return out
