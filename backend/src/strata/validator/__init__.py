"""Layered validator pipeline (Q29). structural → semantic → cross-record."""

from __future__ import annotations

from .cross_record import CrossRecordIssue, cross_record_check
from .pipeline import Severity, ValidationFinding, ValidationReport, validate
from .semantic import SemanticError, semantic_check
from .structural import StructuralError, structural_check

__all__ = [
    "CrossRecordIssue",
    "SemanticError",
    "Severity",
    "StructuralError",
    "ValidationFinding",
    "ValidationReport",
    "cross_record_check",
    "semantic_check",
    "structural_check",
    "validate",
]
