"""Near-miss concept-slug suggestions for explicit slug validation.

An explicit slug the user typed must NEVER be fuzzy-rerouted to a different
market (ADV-1) — a wrong market sized confidently is worse than an error. So a
miss is an honest failure, and this helper only DECORATES that failure with up
to a few likely intended slugs.

Lives beside ``match.py`` because it reuses its token-coverage similarity: a raw
character-ratio (difflib) treated incidental letter overlap as closeness and
suggested garbage like "doc-gen-pc-insurance" for "pet insurance".
"""

from __future__ import annotations

from ..registry import Registry
from .match import FUZZY_THRESHOLD, token_similarity


def near_miss_slugs(reg: Registry, slug: str, *, limit: int = 3) -> list[str]:
    """Up to ``limit`` concept slugs the caller probably meant.

    Substring hits first (a truncated slug is the common typo), then candidates
    clearing the same token-coverage bar the resolver's matcher uses.
    """
    needle = slug.strip().lower()
    candidates = sorted(reg.concepts)
    substring = [c for c in candidates if needle and (needle in c or c in needle)]
    scored = [(c, token_similarity(needle, c)) for c in candidates]
    close = [c for c, s in sorted(scored, key=lambda cs: -cs[1]) if s >= FUZZY_THRESHOLD]
    return list(dict.fromkeys([*substring, *close]))[:limit]
