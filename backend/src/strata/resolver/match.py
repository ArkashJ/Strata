"""Registry-first concept matching (Wave 0 / AC0.2).

Before paying for an LLM round-trip, the resolver asks: does this free-form
query already name a curated concept? An exact slug match wins immediately; a
fuzzy match over concept slugs + names wins above a similarity threshold.
Returns the concept slug on a hit, else ``None`` so the caller falls through to
the novel synthesis path.

Pure Python — no network, no LLM — so a registry hit is deterministic and free.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..registry import Registry

# Above this token-aware similarity, a fuzzy query is treated as the concept.
# Tuned so "doc gen for P&C insurance" matches "doc-gen-pc-insurance" but an
# unrelated market does not.
_FUZZY_THRESHOLD = 0.6


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _similarity(query: str, candidate: str) -> float:
    q, c = _normalize(query), _normalize(candidate)
    if not q or not c:
        return 0.0
    ratio = SequenceMatcher(None, q, c).ratio()
    # Jaccard token bonus: rewards word-for-word overlap (ordering/filler
    # insensitive) without the precision hole of a min() denominator, where a
    # 1-word query like "test" would score 1.0 against any multi-word name
    # containing that word. Union denominator keeps a lone shared token modest.
    q_tokens, c_tokens = set(q.split()), set(c.split())
    union = q_tokens | c_tokens
    if union:
        jaccard = len(q_tokens & c_tokens) / len(union)
        ratio = max(ratio, jaccard)
    return ratio


def match_concept(reg: Registry, query: str) -> str | None:
    """Return the slug of the curated concept the query names, or ``None``.

    Exact slug match (after normalization) short-circuits; otherwise the best
    fuzzy match over (slug, name) is returned when it clears the threshold.
    """
    norm_query = _normalize(query)
    if not norm_query:
        return None

    # Exact normalized slug or name match wins outright.
    for slug, concept in reg.concepts.items():
        if norm_query in (_normalize(slug), _normalize(concept.name)):
            return slug

    best_slug: str | None = None
    best_score = 0.0
    for slug, concept in reg.concepts.items():
        score = max(_similarity(query, slug), _similarity(query, concept.name))
        if score > best_score:
            best_score, best_slug = score, slug

    return best_slug if best_score >= _FUZZY_THRESHOLD else None
