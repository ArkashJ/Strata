"""Per-key usage metering (Wave 3 / AC3.3).

Every metered request bumps an in-process counter keyed by ``(org_id, route)``;
``GET /usage`` returns the caller's org totals. The in-process store is the
active source of truth (tests + single-container deploys). The ``usage_events``
Postgres table (migration 003) is forward scaffolding for durable, cross-process
metering — appending to it is a follow-up, not yet wired.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class UsageMeter:
    def __init__(self) -> None:
        self._counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = Lock()

    def record(self, org_id: str, route: str) -> None:
        with self._lock:
            self._counts[org_id][route] += 1

    def usage_for(self, org_id: str) -> dict[str, int]:
        with self._lock:
            return dict(self._counts.get(org_id, {}))

    def total_for(self, org_id: str) -> int:
        return sum(self.usage_for(org_id).values())

    def snapshot(self) -> dict[str, dict[str, int]]:
        """A copy of all counters (for the /metrics export)."""
        with self._lock:
            return {org: dict(routes) for org, routes in self._counts.items()}

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


_meter = UsageMeter()


def get_meter() -> UsageMeter:
    return _meter
