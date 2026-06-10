"""Registry-first concept matching (Wave 0 / AC0.2).

Before paying for an LLM round-trip, the resolver asks: does this free-form
query already name a curated concept? An exact slug match wins immediately; a
fuzzy match over concept slugs + names wins above a similarity threshold.
Returns the concept slug on a hit, else ``None`` so the caller falls through to
the novel synthesis path.

Pure Python — no network, no LLM — so a registry hit is deterministic and free.

Matching is *token*-driven, not character-driven. A raw character-ratio
(``SequenceMatcher`` over whole strings) treats incidental letter overlap as
similarity: "market research tools" scored 0.61 against "ai legal research us"
and "pet insurance" scored 0.67 against "doc-gen-pc-insurance" — both garbage
matches that cleared a 0.6 char-ratio bar on the strength of a single shared
word ("research", "insurance"). A wrong concept presented as a sourced TAM is
the worst outcome this project can produce, so the match must turn on shared
*meaningful tokens*, and a lone generic overlap must not carry a hit.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..registry import Registry


def _ratio(a: str, b: str) -> float:
    """Per-token similarity in [0, 1], Rust-backed (rapidfuzz).

    Replaces ``difflib.SequenceMatcher(...).ratio()`` with rapidfuzz's
    ``fuzz.ratio`` (Indel-based, the same character-edit notion) divided by 100,
    so the coverage + head-token thresholds below are unchanged. rapidfuzz is the
    faster C/Rust implementation; the score for short tokens is equivalent for the
    typo-tolerance the matcher relies on ("insurnce" → "insurance").
    """
    return fuzz.ratio(a, b) / 100.0


# Above this token-coverage score, a fuzzy query is treated as the concept.
# Coverage is fraction-of-tokens-shared (see ``_similarity``), so 0.6 means a
# clear majority of one side's words must line up — "doc gen pc insurance"
# fully covers "doc-gen-pc-insurance" (1.0) while "pet insurance" covers it only
# 0.25 and is rejected.
_FUZZY_THRESHOLD = 0.6

# A query token counts as matching a candidate token at or above this per-token
# ratio — exact words plus light typo tolerance ("insurnce" → "insurance"),
# without letting unrelated words ("ops" vs "operations", 0.46) leak through.
_TOKEN_MATCH_RATIO = 0.85

# Grammatical filler only. Deliberately NOT domain words ("market", "tools",
# "software", "ai"): stripping those would shrink "market research tools" to
# the bare token "research" and reintroduce the false match against legal
# *research*. Filler carries no market meaning and only inflates token counts.
_STOPWORDS = frozenset(
    {"the", "a", "an", "of", "for", "in", "on", "and", "to", "with", "by", "at", "as"}
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(text: str) -> list[str]:
    """Normalized, filler-stripped tokens. Single-char tokens (e.g. the standalone
    ``p`` and ``c`` left when "P & C" tokenizes with spaces) are dropped — they
    match too freely. ("pc" in ``doc-gen-pc-insurance`` survives; it is 2 chars.)"""
    return [t for t in _normalize(text).split() if len(t) > 1 and t not in _STOPWORDS]


def _shared_count(q_tokens: list[str], c_tokens: list[str]) -> int:
    """Number of query tokens that find a distinct candidate token (exact or
    near-exact). Greedy 1:1 so two query words can't both claim one candidate."""
    claimed: set[int] = set()
    shared = 0
    for qt in q_tokens:
        best_i, best_r = -1, 0.0
        for i, ct in enumerate(c_tokens):
            if i in claimed:
                continue
            r = 1.0 if qt == ct else _ratio(qt, ct)
            if r > best_r:
                best_i, best_r = i, r
        if best_i >= 0 and best_r >= _TOKEN_MATCH_RATIO:
            claimed.add(best_i)
            shared += 1
    return shared


def _similarity(query: str, candidate: str) -> float:
    """Token-coverage similarity in [0, 1].

    ``max`` of the two coverage ratios so either a query that names the whole
    concept ("doc gen pc insurance" → covers the candidate) or a verbose query
    the concept name sits inside ("AI legal research software for US law firms"
    → candidate is covered) scores high, while a one-word coincidence does not.
    """
    q_tokens, c_tokens = _tokens(query), _tokens(candidate)
    if not q_tokens or not c_tokens:
        return 0.0

    shared = _shared_count(q_tokens, c_tokens)
    if shared == 0:
        return 0.0

    cov_q = shared / len(q_tokens)
    cov_c = shared / len(c_tokens)
    score = max(cov_q, cov_c)

    # A lone shared token must not carry a match unless it is the candidate's
    # *identifying head* — a brand/leading word like "Kyber" in
    # "kyber-pc-doc-gen". An incidental middle word does not qualify: "pet
    # insurance" ∩ "doc gen pc insurance" = {insurance} (head is "doc"), and
    # "test" ∩ "skyramp ai test automation" = {test} (head is "skyramp") are
    # both rejected, while bare "Kyber" still resolves.
    # NOTE: the guard is skipped for a single-token candidate (no head to
    # distinguish). That is safe only while no concept's slug/name reduces to one
    # generic word ("insurance", "research") — such a concept would false-match
    # any query containing that word. Keep concept names multi-token.
    if shared == 1 and len(c_tokens) > 1:
        head_matches = _shared_count(q_tokens, c_tokens[:1]) == 1
        if not head_matches:
            score = min(score, _FUZZY_THRESHOLD - 0.01)

    return score


# Public names for sibling modules (suggest.py): near-miss suggestions must use
# the SAME token-coverage notion as matching so the two can never disagree on
# what "close" means.
FUZZY_THRESHOLD = _FUZZY_THRESHOLD
token_similarity = _similarity


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
