"""Primitive freshness / staleness (Wave 1 / AC1.7).

A sourced number ages: when a primitive's data period (``as_of``) is older than
its source's declared ``freshness_sla_days``, the UI renders a `stale` chip so a
reader never quotes a number past its shelf life without seeing it. The frontend
`StaleChip` mirrors this rule off the serialized fields.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def staleness_days(as_of: date, reference: date) -> int:
    return (reference - as_of).days


def is_stale(as_of: date, source: Any, reference: date) -> bool:
    """True when ``as_of`` is older than the source's freshness SLA. Sources with
    no declared SLA are never auto-flagged."""
    sla = getattr(source, "freshness_sla_days", None)
    if sla is None:
        return False
    return staleness_days(as_of, reference) > int(sla)
