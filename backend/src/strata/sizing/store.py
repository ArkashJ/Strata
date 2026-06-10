"""Company store — org-scoped portfolio persistence (spec §4, §7).

Two backends share one interface so the CLI, tests, and the demo never need
Postgres, while prod reuses the same records over the ``companies`` table:

* ``CompanyStore`` — JSON-file (or pure in-memory) store. Idempotent on
  ``CompanyRecord.key`` (normalized domain, falling back to name). This is the
  local/default-org path; CI/tests point it at a tmp file.
* ``strata.db.companies`` — the async Postgres path for the hosted surface.

Kept deliberately dumb: it stores and lists records; all sizing logic lives in
``strata.sizing.service``.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from strata.models import CompanyRecord, CompanyStatus

DEFAULT_STORE_PATH: Path = Path.home() / ".strata" / "portfolio.json"


class CompanyStore:
    """Idempotent JSON-backed company store, keyed by ``(org_id, key)``."""

    def __init__(self, path: Path | None = DEFAULT_STORE_PATH, *, org_id: str = "default") -> None:
        self.org_id = org_id
        self.path = path
        self._rows: dict[str, CompanyRecord] = {}
        # Rows belonging to OTHER orgs sharing this file — kept aside so a flush
        # re-serializes them too instead of silently wiping foreign tenants.
        self._foreign: list[CompanyRecord] = []
        self._load()

    # ── persistence ────────────────────────────────────────────────────────
    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        for item in raw:
            rec = CompanyRecord.model_validate(item)
            if rec.org_id == self.org_id:
                self._rows[rec.key] = rec
            else:
                self._foreign.append(rec)

    def _flush(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.model_dump(mode="json") for r in [*self._foreign, *self._rows.values()]]
        # Atomic replace so a crash mid-write can't leave a truncated store.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(payload, indent=2, sort_keys=True))
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    # ── writes ───────────────────────────────────────────────────────────────
    def upsert_many(self, rows: list[CompanyRecord]) -> tuple[int, int]:
        """Insert new rows, skip existing (idempotent). Returns (added, skipped)."""
        added = skipped = 0
        for rec in rows:
            rec.org_id = self.org_id
            if rec.key in self._rows:
                skipped += 1
                continue
            self._rows[rec.key] = rec
            added += 1
        # The idempotent no-op path must not rewrite the file.
        if added:
            self._flush()
        return added, skipped

    def add_company(
        self,
        rec: CompanyRecord,
        *,
        market: str | None,
        vertical: str | None,
    ) -> tuple[Literal["added", "updated", "existing"], CompanyRecord]:
        """Add-or-update one record, flushing at most once.

        Shared by the CLI and the MCP tool so add/update/existing semantics can't
        drift between surfaces (ADV-3): a re-add carrying NEW info (an explicit
        market or vertical) updates the stored row; a re-add with no new info is
        a no-op that never touches disk. Returns the resolved stored record so
        callers size/render the same object the store holds.
        """
        rec.org_id = self.org_id
        stored = self._rows.get(rec.key)
        if stored is None:
            self._rows[rec.key] = rec
            self._flush()
            return "added", rec
        changed = (market is not None and stored.market_concept_slug != market) or (
            vertical is not None and stored.vertical != vertical
        )
        if not changed:
            return "existing", stored
        if market is not None:
            stored.market_concept_slug = market
        if vertical is not None:
            stored.vertical = vertical
        self._flush()
        return "updated", stored

    def save(self, rec: CompanyRecord) -> None:
        """Upsert one record (used after sizing updates status/tam_value)."""
        rec.org_id = self.org_id
        self._rows[rec.key] = rec
        self._flush()

    # ── reads ────────────────────────────────────────────────────────────────
    def get(self, key: str) -> CompanyRecord | None:
        k = key.strip().lower()
        if k in self._rows:
            return self._rows[k]
        # Allow lookup by raw domain or name too.
        for rec in self._rows.values():
            if k in (rec.domain, rec.name.strip().lower()):
                return rec
        return None

    def list(
        self,
        *,
        status: CompanyStatus | None = None,
        vertical: str | None = None,
        limit: int | None = None,
    ) -> list[CompanyRecord]:
        rows = list(self._rows.values())
        if status is not None:
            rows = [r for r in rows if r.status == status]
        if vertical is not None:
            rows = [r for r in rows if (r.vertical or "").lower() == vertical.lower()]
        rows.sort(key=lambda r: (r.status, r.name.lower()))
        return rows[:limit] if limit else rows

    def counts(self) -> dict[str, int]:
        out = {"total": len(self._rows), "sized": 0, "unsized": 0, "unsizable": 0}
        for rec in self._rows.values():
            out[rec.status] = out.get(rec.status, 0) + 1
        return out
