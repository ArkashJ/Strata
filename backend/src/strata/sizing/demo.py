"""Cached demo portfolio loader (spec F3/F5).

Reads the deterministic, pre-sized artifact baked into the package by
``scripts/presize_demo.py``. The ``GET /portfolio`` route and the ``/portfolio``
page render straight from this — no live LLM/Exa, ever. If the file is absent
(it is committed, so it normally is not), callers get an empty list rather than
an error.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DEMO_JSON = Path(__file__).resolve().parent / "portfolio_demo.json"


@lru_cache(maxsize=1)
def load_demo_portfolio() -> list[dict[str, object]]:
    """The cached, pre-sized demo subset rows (20 sized + 5 unsizable)."""
    if not _DEMO_JSON.exists():
        return []
    return json.loads(_DEMO_JSON.read_text())


def demo_counts() -> dict[str, int]:
    rows = load_demo_portfolio()
    out = {"total": len(rows), "sized": 0, "unsized": 0, "unsizable": 0}
    for r in rows:
        status = str(r.get("status", "unsized"))
        out[status] = out.get(status, 0) + 1
    return out
