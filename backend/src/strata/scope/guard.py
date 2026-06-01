"""The scope guard — does a primitive's true scope match the declared market?

Pure, deterministic, no network / no LLM (mirrors ``sizing/guard.py``). For each
scope dimension the guard classifies the *declared* scope (concept / user) against
the *actual* scope (primitive) into a :class:`Relationship`, and emits a
human-readable warning when they diverge. The displayed scope is always the
actual one — the UI binds tags to the truth behind the number, so a number can
never misrepresent its market.

Coded dimensions (vertical→NAICS, persona→SOC) compare by *significant-prefix*
hierarchy: strip separators and trailing hierarchy-padding zeros, then ``A`` is
broader-than-or-equal-to ``B`` iff ``sig(A)`` prefixes ``sig(B)``. Each dimension
holds a *set* of codes (a union), so the relationship aggregates over the sets.

Geo compares ISO-code sets (``global`` is a wildcard); segment compares
employee-count ranges by containment; product / include / exclude are free text
and display-only in v1 (advisory, never block).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from strata.models.scope import CodedTag, CodeSystem, FirmSizeBand, MarketScope, ScopeDimension


class Relationship(StrEnum):
    """How an actual scope relates to a declared scope on one dimension."""

    EXACT = "exact"
    NARROWER = "narrower"
    BROADER = "broader"
    PARTIAL = "partial"
    DISJOINT = "disjoint"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ScopeWarning:
    """One dimension where the primitive's scope diverges from what was declared."""

    dimension: ScopeDimension
    relationship: Relationship
    message: str


@dataclass(frozen=True, slots=True)
class ScopeMatch:
    """Result of comparing a declared scope against an actual (primitive) scope.

    ``displayed`` is always the actual scope (snap-to-truth). ``warnings`` is
    empty when every checked dimension is EXACT (or unconstrained on the declared
    side); otherwise each entry explains a divergence the reader should see.
    """

    displayed: MarketScope
    warnings: tuple[ScopeWarning, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.warnings


# ── code hierarchy ───────────────────────────────────────────────────────────


def _sig(code: str) -> str:
    """Significant prefix of a NAICS/SOC code: digits only, trailing hierarchy
    zeros stripped. ``"41-4012"`` → ``"414012"``; ``"41-4000"`` → ``"414"``;
    ``"541110"`` → ``"54111"``; ``"5411"`` → ``"5411"``. Empty when the code has
    no digits.

    Stripping *all* trailing zeros is correct — and load-bearing — for real
    NAICS/SOC codes: significant digits at every level are 1-9 (NAICS sectors
    never end in 0; SOC detailed occupations end 1-9), so a trailing zero is
    always aggregation padding (SOC minor ``41-4000`` = the whole ``41-4xxx``
    group; NAICS 6-digit ``541110`` = the 5-digit industry ``54111``). Do NOT
    switch to "strip separators only": that would make ``41-4000`` stop covering
    ``41-4012`` and break the wholesale-vs-all narrower-scope detection.
    ``rstrip`` keeps *internal* zeros (``41-4010`` → ``41401``), so broad-group
    codes still compare correctly."""
    digits = re.sub(r"\D", "", code)
    return digits.rstrip("0")


def _covers(broad: CodedTag, narrow: CodedTag) -> bool:
    """True when ``broad`` is an ancestor of (or equal to) ``narrow`` — i.e. the
    space ``broad`` describes contains the space ``narrow`` describes."""
    if broad.system != narrow.system:
        return False
    if broad.system == CodeSystem.CUSTOM:
        return broad.code == narrow.code
    bsig, nsig = _sig(broad.code), _sig(narrow.code)
    if not bsig or not nsig:
        # Malformed / digit-free code — fall back to exact match, never wildcard.
        return broad.code == narrow.code
    return nsig.startswith(bsig)


def _overlap(x: CodedTag, y: CodedTag) -> bool:
    return _covers(x, y) or _covers(y, x)


def _covered_by_set(code: CodedTag, codes: tuple[CodedTag, ...]) -> bool:
    return any(_covers(c, code) for c in codes)


def _classify_codes(
    declared: tuple[CodedTag, ...], actual: tuple[CodedTag, ...]
) -> tuple[Relationship, tuple[CodedTag, ...]]:
    """Classify two code sets. Returns the relationship and, for NARROWER/PARTIAL,
    the declared codes the actual set does not overlap at all (the "excluded
    entirely" list that powers the wholesale-vs-all message)."""
    if not actual:
        # Primitive declares nothing on this dimension: unverified when the user
        # constrained it, otherwise both sides are simply unconstrained → clean.
        return (Relationship.UNKNOWN, ()) if declared else (Relationship.EXACT, ())
    if not declared:
        # User left this dimension open; the primitive's scope merely informs the
        # displayed tag. Not a violation.
        return Relationship.EXACT, ()

    actual_in_declared = all(_covered_by_set(a, declared) for a in actual)
    declared_in_actual = all(_covered_by_set(d, actual) for d in declared)
    zero_overlap = tuple(d for d in declared if not any(_overlap(d, a) for a in actual))

    if actual_in_declared and declared_in_actual:
        return Relationship.EXACT, ()
    if actual_in_declared:
        return Relationship.NARROWER, zero_overlap
    if declared_in_actual:
        return Relationship.BROADER, ()
    if any(_overlap(d, a) for d in declared for a in actual):
        return Relationship.PARTIAL, zero_overlap
    return Relationship.DISJOINT, declared


# ── geo + segment ────────────────────────────────────────────────────────────


def _classify_geo(declared: tuple[str, ...], actual: tuple[str, ...]) -> Relationship:
    """ISO-code set comparison. ``global`` is a wildcard covering every geo."""
    if not declared:
        return Relationship.EXACT  # unconstrained on the declared side
    if not actual:
        return Relationship.UNKNOWN

    d_all = "global" in declared
    a_all = "global" in actual
    d, a = set(declared) - {"global"}, set(actual) - {"global"}

    if d_all and a_all:
        return Relationship.EXACT
    if a_all and not d_all:
        return Relationship.BROADER
    if d_all and not a_all:
        return Relationship.NARROWER

    if a == d:
        return Relationship.EXACT
    if a < d:
        return Relationship.NARROWER
    if a > d:
        return Relationship.BROADER
    if a & d:
        return Relationship.PARTIAL
    return Relationship.DISJOINT


def _band_bounds(band: FirmSizeBand) -> tuple[float, float]:
    lo = float(band.min_emp) if band.min_emp is not None else 0.0
    hi = float(band.max_emp) if band.max_emp is not None else float("inf")
    return lo, hi


def _classify_segment(declared: FirmSizeBand | None, actual: FirmSizeBand | None) -> Relationship:
    if declared is None:
        return Relationship.EXACT  # unconstrained on the declared side
    dlo, dhi = _band_bounds(declared)
    # A primitive with no firm-size restriction covers every firm size → an open
    # band. So it reads EXACT against an explicit "all employer firms" declaration
    # but BROADER against a narrower declared band (the mid-market overcount).
    alo, ahi = _band_bounds(actual) if actual is not None else (0.0, float("inf"))
    if (alo, ahi) == (dlo, dhi):
        return Relationship.EXACT
    if alo >= dlo and ahi <= dhi:
        return Relationship.NARROWER
    if dlo >= alo and dhi <= ahi:
        return Relationship.BROADER
    if ahi < dlo or alo > dhi:
        return Relationship.DISJOINT
    return Relationship.PARTIAL


# ── message building ─────────────────────────────────────────────────────────


def _fmt(tags: tuple[CodedTag, ...]) -> str:
    return ", ".join(f"{t.system.value} {t.code} ({t.label})" for t in tags) or "—"


def _coded_warning(
    dimension: ScopeDimension,
    declared: tuple[CodedTag, ...],
    actual: tuple[CodedTag, ...],
    rel: Relationship,
    zero_overlap: tuple[CodedTag, ...],
) -> ScopeWarning | None:
    if not declared:
        return None  # nothing declared on this dimension → nothing to violate
    if rel is Relationship.EXACT:
        return None
    if rel is Relationship.UNKNOWN:
        msg = (
            f"Source declares no {dimension.value} scope — unverified against the "
            f"declared market ({_fmt(declared)})."
        )
    elif rel is Relationship.NARROWER:
        msg = (
            f"Source covers {_fmt(actual)} — narrower than the declared "
            f"{_fmt(declared)}; undercounts the market."
        )
        if zero_overlap:
            msg += f" Excludes {_fmt(zero_overlap)} entirely."
    elif rel is Relationship.BROADER:
        msg = (
            f"Source covers {_fmt(actual)} — broader than the declared "
            f"{_fmt(declared)}; may overcount."
        )
    elif rel is Relationship.PARTIAL:
        msg = (
            f"Source covers {_fmt(actual)} — only partially overlaps the declared {_fmt(declared)}."
        )
        if zero_overlap:
            msg += f" Misses {_fmt(zero_overlap)}."
    else:  # DISJOINT
        msg = (
            f"Source scope {_fmt(actual)} does not match the declared market "
            f"{_fmt(declared)} — wrong population."
        )
    return ScopeWarning(dimension=dimension, relationship=rel, message=msg)


def _geo_warning(
    declared: tuple[str, ...], actual: tuple[str, ...], rel: Relationship
) -> ScopeWarning | None:
    if not declared:
        return None  # nothing declared → nothing to violate (self-consistent with _coded_warning)
    if rel is Relationship.EXACT:
        return None
    d, a = ", ".join(declared) or "—", ", ".join(actual) or "—"
    if rel is Relationship.UNKNOWN:
        msg = f"Source declares no geography — unverified against declared geo ({d})."
    elif rel is Relationship.NARROWER:
        msg = f"Source geography {a} is narrower than declared {d}; undercounts."
    elif rel is Relationship.BROADER:
        msg = f"Source geography {a} is broader than declared {d}; may overcount."
    elif rel is Relationship.PARTIAL:
        msg = f"Source geography {a} only partially overlaps declared {d}."
    else:
        msg = f"Source geography {a} does not match declared {d} — wrong region."
    return ScopeWarning(dimension=ScopeDimension.GEO, relationship=rel, message=msg)


def _segment_warning(
    declared: FirmSizeBand | None, actual: FirmSizeBand | None, rel: Relationship
) -> ScopeWarning | None:
    if declared is None:
        return None  # nothing declared → nothing to violate (self-consistent with _coded_warning)
    if rel is Relationship.EXACT:
        return None
    dlabel = declared.label if declared else "all firms"
    alabel = actual.label if actual else "all firm sizes (no restriction)"
    if rel is Relationship.NARROWER:
        msg = f"Source is limited to {alabel} — narrower than declared {dlabel}; undercounts."
    elif rel is Relationship.BROADER:
        msg = f"Source covers {alabel} — broader than declared {dlabel}; may overcount."
    elif rel is Relationship.PARTIAL:
        msg = f"Source firm-size band {alabel} only partially overlaps declared {dlabel}."
    else:
        msg = f"Source firm-size band {alabel} does not match declared {dlabel}."
    return ScopeWarning(dimension=ScopeDimension.SEGMENT, relationship=rel, message=msg)


# ── public entry point ───────────────────────────────────────────────────────


def classify_scope(declared: MarketScope, actual: MarketScope) -> ScopeMatch:
    """Compare a declared market scope against a primitive's actual scope.

    The displayed scope is always ``actual`` (snap-to-truth); warnings flag every
    dimension where the actual scope is narrower / broader / partial / disjoint /
    unverified relative to what was declared."""
    warnings: list[ScopeWarning] = []

    v_rel, v_zero = _classify_codes(declared.vertical, actual.vertical)
    if w := _coded_warning(
        ScopeDimension.VERTICAL, declared.vertical, actual.vertical, v_rel, v_zero
    ):
        warnings.append(w)

    p_rel, p_zero = _classify_codes(declared.persona, actual.persona)
    if w := _coded_warning(ScopeDimension.PERSONA, declared.persona, actual.persona, p_rel, p_zero):
        warnings.append(w)

    s_rel = _classify_segment(declared.segment, actual.segment)
    if w := _segment_warning(declared.segment, actual.segment, s_rel):
        warnings.append(w)

    # Geo: the demand side is what a TAM addresses; check supply too when declared.
    for d_codes, a_codes in (
        (declared.geo_demand, actual.geo_demand),
        (declared.geo_supply, actual.geo_supply),
    ):
        g_rel = _classify_geo(d_codes, a_codes)
        if w := _geo_warning(d_codes, a_codes, g_rel):
            warnings.append(w)

    return ScopeMatch(displayed=actual, warnings=tuple(warnings))
