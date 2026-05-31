#!/usr/bin/env python3
"""Pre-size the curated demo subset OFFLINE → data/demo/portfolio_demo.json.

This is the ONLY place the demo's numbers are produced, and it runs on the
operator's machine, never in a request handler (spec F3). It sizes each mapped
company registry-first via ``strata.sizing.service`` (no LLM/Exa) and writes a
deterministic cached artifact that the ``GET /portfolio`` route and the
``/portfolio`` page render straight from — so nothing a reviewer sees ever calls
Claude or Exa.

Usage (from backend/):
    uv run python scripts/presize_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from strata.loader import load_data_dir
from strata.models import CompanyRecord
from strata.registry import Registry
from strata.sizing.service import SizeOptions, size_company

_BACKEND = Path(__file__).resolve().parents[1]
_REPO = _BACKEND.parent
_DATA = _REPO / "data"
_SUBSET = _REPO / "portfolios" / "portfolio_demo_subset.yaml"
# Baked into the package so the wheel/Docker image always ships the cached demo
# (the GET /portfolio route reads it from here — F3-safe, no live calls).
_OUT = _BACKEND / "src" / "strata" / "sizing" / "portfolio_demo.json"


def main() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    subset = yaml.safe_load(_SUBSET.read_text())
    org = subset.get("org_id", "default")

    out: list[dict[str, object]] = []
    sized = unsizable = 0

    for entry in subset.get("sized", []):
        rec = CompanyRecord(
            org_id=org,
            name=entry["name"],
            domain=entry["domain"],
            vertical=entry.get("vertical"),
            market_concept_slug=entry["market"],
        )
        res = size_company(reg, rec, opts=SizeOptions())  # offline-safe
        if res.verdict != "sized":
            raise SystemExit(
                f"demo subset row {entry['name']!r} failed to size: {res.company.reason}"
            )
        sized += 1
        out.append(_row(res.company, res.tam.state_hash if res.tam else None))
        print(f"  sized   {rec.name:24} → {rec.market_concept_slug:34} ${rec.tam_value:,.0f}")

    for entry in subset.get("unsizable", []):
        rec = CompanyRecord(
            org_id=org,
            name=entry["name"],
            domain=entry["domain"],
            vertical=entry.get("vertical"),
            status="unsizable",
            reason=entry["reason"],
        )
        unsizable += 1
        out.append(_row(rec, None))
        print(f"  unsized {rec.name:24} → {(rec.reason or '')[:60]}")

    _OUT.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"\nwrote {len(out)} rows ({sized} sized, {unsizable} unsizable) → {_OUT.relative_to(_REPO)}"
    )


def _row(rec: CompanyRecord, state_hash: str | None) -> dict[str, object]:
    return {
        "org_id": rec.org_id,
        "name": rec.name,
        "domain": rec.domain,
        "vertical": rec.vertical,
        "market_concept_slug": rec.market_concept_slug,
        "status": rec.status,
        "tam_value": rec.tam_value,
        "reason": rec.reason,
        "state_hash": state_hash,
        "has_analyst_input": rec.has_analyst_input,
    }


if __name__ == "__main__":
    main()
