"""Strata sizing service — productized portfolio company → TAM pipeline.

See ``docs/superpowers/specs/2026-05-31-portfolio-sizing-company-layer-design.md``.

The two load-bearing units are the verbatim guard (``guard``) — the Q20 wall
that keeps LLM-produced numbers out of the bank — and the sizing service
(``service``). Everything else is plumbing around them.
"""

from __future__ import annotations

from .guard import GuardVerdict, parse_magnitude, scan_magnitudes, verbatim_guard
from .importer import parse_portfolio_csv
from .service import SizeOptions, SizeResult, size_company
from .source import SourcedInput, source_via_exa
from .store import CompanyStore

__all__ = [
    "CompanyStore",
    "GuardVerdict",
    "SizeOptions",
    "SizeResult",
    "SourcedInput",
    "parse_magnitude",
    "parse_portfolio_csv",
    "scan_magnitudes",
    "size_company",
    "source_via_exa",
    "verbatim_guard",
]
