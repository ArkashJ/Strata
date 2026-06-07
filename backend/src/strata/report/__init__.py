"""Question-driven market report (PR4, engine layer 2).

The report layer turns a curated bank of :class:`AnalysisQuestion` records into
:class:`ResolvedAnswer` rows for one concept — purely from the registry and the
in-process evaluator, never an LLM or the network. The fence lives in the model
layer (`models/question.py`): every answer is either a sourced number (with
provenance), a TAM-field synthesis (reproducible at `/tam/<hash>`), a sourced
narrative, or an honest gap. An unsourced number is structurally impossible.
"""

from __future__ import annotations

from .assembler import assemble_report, assemble_report_for_tam
from .sections import (
    PremiumReport,
    ReportSection,
    assemble_premium_report_for_tam,
    build_premium_report,
)

__all__ = [
    "PremiumReport",
    "ReportSection",
    "assemble_premium_report_for_tam",
    "assemble_report",
    "assemble_report_for_tam",
    "build_premium_report",
]
