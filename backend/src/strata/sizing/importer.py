"""Portfolio CSV → CompanyRecord rows (spec §7).

The real ``Cos list.csv`` has a BOM and the header ``Name,Website,Industry
Vertical`` with many blank-website / blank-vertical rows. Parsing is tolerant:
blank verticals become ``None``, blank websites fall back to the name for the
idempotency key, and obviously-junk names (a lone quote char) are skipped.
"""

from __future__ import annotations

import csv
from pathlib import Path

from strata.models import CompanyRecord


def _clean(value: str | None) -> str:
    return (value or "").strip().strip("﻿").strip('"').strip("“”").strip()


def parse_portfolio_csv(path: Path, *, org_id: str = "default") -> list[CompanyRecord]:
    """Parse a ``Name,Website,Industry Vertical`` CSV into company records."""
    rows: list[CompanyRecord] = []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    for raw in reader:
        # DictReader keys can carry the BOM/whitespace; normalize lookups.
        lookup = {(_clean(k) or "").lower(): v for k, v in raw.items()}
        name = _clean(lookup.get("name"))
        website = _clean(lookup.get("website"))
        vertical = _clean(lookup.get("industry vertical")) or None
        if not name or len(name) < 2:
            continue
        rows.append(CompanyRecord(org_id=org_id, name=name, domain=website, vertical=vertical))
    return rows
