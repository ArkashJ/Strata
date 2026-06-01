"""Market-scope consistency checking (sub-project 1, 2026-05-31 design).

``guard.classify_scope`` compares a declared ``MarketScope`` (what a concept or
the user says the market is) against an actual ``MarketScope`` (what a primitive
genuinely covers) and returns a ``ScopeMatch``: the snap-to-truth displayed
scope plus any mismatch warnings. Pure and deterministic — no network, no LLM.
"""

from __future__ import annotations

from .guard import (
    Relationship,
    ScopeMatch,
    ScopeWarning,
    classify_scope,
)
from .report import build_scope_report

__all__ = [
    "Relationship",
    "ScopeMatch",
    "ScopeWarning",
    "build_scope_report",
    "classify_scope",
]
