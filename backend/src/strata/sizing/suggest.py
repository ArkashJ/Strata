"""Near-miss concept-slug suggestions for explicit ``--market`` validation.

An explicit slug the user typed must NEVER be fuzzy-rerouted to a different
market (ADV-1) — a wrong market sized confidently is worse than an error. So a
miss is an honest failure, and this helper only DECORATES that failure with up
to a few likely intended slugs (substring hits first, then difflib closeness).
"""

from __future__ import annotations

import difflib

from strata.registry import Registry


def near_miss_slugs(reg: Registry, slug: str, *, limit: int = 3) -> list[str]:
    """Up to ``limit`` concept slugs the caller probably meant."""
    needle = slug.strip().lower()
    candidates = sorted(reg.concepts)
    substring = [c for c in candidates if needle and (needle in c or c in needle)]
    close = difflib.get_close_matches(needle, candidates, n=limit, cutoff=0.5)
    out: list[str] = []
    for c in [*substring, *close]:
        if c not in out:
            out.append(c)
    return out[:limit]
