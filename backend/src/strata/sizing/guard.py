"""The verbatim guard — the Q20 wall (spec §6 + F1).

Decides whether a number an LLM *claims* it extracted from a fetched page is a
faithful, corroborated extraction of a real sourced figure (eligible to persist)
or a hallucination / format-mismatch (rejected). Pure and deterministic — no
network, no LLM. Two gates in series:

    GATE 1  semantic magnitude match + role-keyword locality
            the claimed magnitude must appear as a numeric surface form whose
            local window mentions the requested quantity role (revenue ≠ market cap)
    GATE 2  corroboration
            the same magnitude must appear in ≥1 OTHER role-matched span, or in a
            second independent source. Single mention → org-private only.

A substring scan alone is both falsely-trippable and trivially defeated; the two
gates make persistence require real, role-correct, corroborated evidence.

Verdicts:
    verbatim_corroborated  eligible for PUBLIC persistence
    verbatim_single        eligible for ORG-PRIVATE persistence only
    semantic_mismatch      magnitude wrong / role wrong → REJECT
    absent                 magnitude not on the page → REJECT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Scale words → multiplier. Longest keys first so "billion" wins over "b".
_SCALES: dict[str, float] = {
    "trillion": 1e12,
    "billion": 1e9,
    "million": 1e6,
    "thousand": 1e3,
    "tn": 1e12,
    "bn": 1e9,
    "mn": 1e6,
    "tr": 1e12,
    "t": 1e12,
    "b": 1e9,
    "m": 1e6,
    "k": 1e3,
}

# A numeric surface form: optional currency marker, digits with optional comma
# grouping / decimal, optional scale suffix word or single letter.
_NUM_RE = re.compile(
    r"""
    (?:[$€£]|USD|EUR|GBP)?            # optional currency marker
    \s*
    (?P<num>\d[\d,]*(?:\.\d+)?)       # the number, with comma grouping / decimal
    \s*
    (?P<scale>trillion|billion|million|thousand|tn|bn|mn|tr|[tbmk])?  # scale
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Clause boundaries for gate-1 locality: a role keyword only counts if it sits
# in the SAME clause as the number. Sentence terminators, common contrastive
# connectives, and commas that are NOT inside a digit group all end a clause.
# (A number's own grouping commas — "4,200,000,000" — must not split it.)
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?<!\d)[.](?!\d)"  # period, but not a decimal point inside a number
    r"|[;:!?\n]"
    r"|\b(?:while|whilst|whereas|but|although|though|however|separately|meanwhile)\b"
    r"|(?<!\d),(?!\d)",  # comma, but not a digit-grouping comma inside a number
    re.IGNORECASE,
)


def _no_spans() -> list[str]:
    return []


@dataclass(frozen=True, slots=True)
class Magnitude:
    """One numeric surface form found in a page, with its location."""

    value: float
    offset: int
    span: str


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    verdict: str  # verbatim_corroborated | verbatim_single | semantic_mismatch | absent
    value: float | None
    matched_span: str | None
    offset: int | None
    unit_keyword: str | None
    corroborating_spans: list[str] = field(default_factory=_no_spans)

    @property
    def eligible_public(self) -> bool:
        return self.verdict == "verbatim_corroborated"

    @property
    def eligible_private(self) -> bool:
        return self.verdict in {"verbatim_corroborated", "verbatim_single"}


def parse_magnitude(surface: str) -> float | None:
    """Parse a single surface form (``$4.2B``, ``4.2 billion``, ``4,200,000,000``)
    into its magnitude. Returns ``None`` when no number is present."""
    m = _NUM_RE.search(surface)
    if m is None:
        return None
    return _resolve(m.group("num"), m.group("scale"))


def _resolve(num: str, scale: str | None) -> float | None:
    try:
        base = float(num.replace(",", ""))
    except ValueError:
        return None
    if scale:
        base *= _SCALES[scale.lower()]
    return base


def scan_magnitudes(text: str) -> list[Magnitude]:
    """Every numeric surface form in ``text`` resolved to a magnitude."""
    out: list[Magnitude] = []
    for m in _NUM_RE.finditer(text):
        val = _resolve(m.group("num"), m.group("scale"))
        if val is None:
            continue
        out.append(Magnitude(value=val, offset=m.start(), span=m.group(0).strip()))
    return out


def _tol(value: float) -> float:
    """Tolerance for magnitude equality: ±0.5% of the value, floored at 0.5 so
    integer counts match exactly without float noise."""
    return max(abs(value) * 0.005, 0.5)


def _matches(target: float, candidate: float) -> bool:
    return abs(candidate - target) <= _tol(target)


def _clause_bounds(text: str, offset: int) -> tuple[int, int]:
    """The [lo, hi) span of the clause containing ``offset`` — delimited by the
    nearest clause boundaries on either side (or the text ends)."""
    lo, hi = 0, len(text)
    for b in _CLAUSE_BOUNDARY_RE.finditer(text):
        if b.end() <= offset:
            lo = b.end()
        elif b.start() > offset:
            hi = b.start()
            break
    return lo, hi


def _role_ok(text: str, offset: int, role_keywords: list[str] | None) -> bool:
    """Gate-1 locality: does the *clause* containing ``offset`` mention the role?
    No role keywords supplied → locality check is skipped (always ok)."""
    if not role_keywords:
        return True
    lo, hi = _clause_bounds(text, offset)
    clause = text[lo:hi].lower()
    return any(kw.lower() in clause for kw in role_keywords)


def _sentence_index(text: str, offset: int) -> int:
    """Cheap sentence id: count sentence terminators before ``offset``. Two
    mentions in different sentences corroborate; two in one do not."""
    return len(re.findall(r"[.!?\n]", text[:offset]))


def verbatim_guard(
    value: float,
    text: str,
    *,
    role_keywords: list[str] | None = None,
    second_source_text: str | None = None,
) -> GuardVerdict:
    """Run both gates and classify ``value`` against ``text`` (spec §6 + F1)."""
    magnitudes = scan_magnitudes(text)

    # Any magnitude on the page within tolerance, regardless of role — used to
    # distinguish "absent" (not there at all) from "semantic_mismatch" (there,
    # but wrong role / wrong number nearby).
    any_magnitude_present = any(_matches(value, m.value) for m in magnitudes)

    # Gate 1: role-matched occurrences only.
    role_matched = [
        m
        for m in magnitudes
        if _matches(value, m.value) and _role_ok(text, m.offset, role_keywords)
    ]

    if not role_matched:
        # The number isn't on the page at all → absent. It is, but never for the
        # requested role (or a different number sits where the role is) → mismatch.
        verdict = "semantic_mismatch" if any_magnitude_present or magnitudes else "absent"
        return GuardVerdict(
            verdict=verdict,
            value=None,
            matched_span=None,
            offset=None,
            unit_keyword=None,
        )

    primary = role_matched[0]
    unit_keyword = role_keywords[0] if role_keywords else None

    # Gate 2: corroboration. Distinct role-matched sentences in the same page,
    # or a role-match in a second independent source.
    primary_sentence = _sentence_index(text, primary.offset)
    corroborating: list[str] = [
        m.span for m in role_matched[1:] if _sentence_index(text, m.offset) != primary_sentence
    ]
    if second_source_text:
        second = scan_magnitudes(second_source_text)
        corroborating.extend(
            m.span
            for m in second
            if _matches(value, m.value) and _role_ok(second_source_text, m.offset, role_keywords)
        )

    verdict = "verbatim_corroborated" if corroborating else "verbatim_single"
    return GuardVerdict(
        verdict=verdict,
        value=primary.value,
        matched_span=primary.span,
        offset=primary.offset,
        unit_keyword=unit_keyword,
        corroborating_spans=corroborating,
    )
