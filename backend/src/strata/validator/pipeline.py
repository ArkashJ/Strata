"""Top-level validator pipeline: structural → semantic → cross-record.

Returns a ``ValidationReport`` rather than raising so the CLI can render
errors and warnings together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ..loader import LoadedRecords, LoaderError, load_data_dir
from ..registry import Registry, RegistryError
from .cross_record import CrossRecordSeverity, cross_record_check
from .semantic import semantic_check
from .structural import structural_check


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    layer: str
    code: str
    severity: Severity
    slug: str
    message: str


@dataclass(slots=True)
class ValidationReport:
    findings: list[ValidationFinding] = field(default_factory=list[ValidationFinding])
    registry: Registry | None = None

    @property
    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(data_dir: Path) -> ValidationReport:
    report = ValidationReport()
    try:
        records: LoadedRecords = load_data_dir(data_dir)
    except LoaderError as exc:
        report.findings.append(
            ValidationFinding(
                layer="structural",
                code="loader",
                severity=Severity.ERROR,
                slug=str(exc.path),
                message=exc.detail,
            )
        )
        return report

    for err in structural_check(records):
        report.findings.append(
            ValidationFinding(
                layer="structural",
                code=err.code,
                severity=Severity.ERROR,
                slug="",
                message=err.message,
            )
        )
    if report.errors:
        return report

    for serr in semantic_check(records):
        report.findings.append(
            ValidationFinding(
                layer="semantic",
                code=serr.code,
                severity=Severity.ERROR,
                slug=serr.slug,
                message=serr.message,
            )
        )
    if report.errors:
        return report

    try:
        registry = Registry.from_loaded(records)
    except RegistryError as exc:
        report.findings.append(
            ValidationFinding(
                layer="structural",
                code="registry",
                severity=Severity.ERROR,
                slug="",
                message=str(exc),
            )
        )
        return report
    report.registry = registry

    for cerr in cross_record_check(registry):
        sev = Severity.ERROR if cerr.severity == CrossRecordSeverity.ERROR else Severity.WARNING
        report.findings.append(
            ValidationFinding(
                layer="cross_record",
                code=cerr.code,
                severity=sev,
                slug=cerr.slug,
                message=cerr.message,
            )
        )
    return report
