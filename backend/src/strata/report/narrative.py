"""Token-fenced prose for the premium report (P4).

Every sentence here is built ONLY from values the evaluator already produced —
a TAM scenario value, a method-family count, an independence score — or from an
already-resolved :class:`ResolvedAnswer` (itself Q20-fenced). No number is
authored here and no LLM is called: the prose is a deterministic rendering of
sourced/derived figures, so it stays reproducible at ``/tam/<hash>``.
"""

from __future__ import annotations

import math


def compact_number(value: float) -> str:
    """A compact human figure (1.2B, 340M, 5.0K) — display only, never a source.

    Used for headline prose; the underlying figure stays the exact TAM value.
    """
    if value == 0 or math.isnan(value) or math.isinf(value):
        return "0"
    sign = "-" if value < 0 else ""
    n = abs(value)
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= threshold:
            return f"{sign}{n / threshold:.1f}{suffix}"
    return f"{sign}{n:,.0f}"


def usd(value: float) -> str:
    return f"${compact_number(value)}"


def executive_summary(
    *,
    concept_name: str,
    low: float | None,
    mid: float | None,
    high: float | None,
    n_method_families: int,
    independence_score: float,
    has_modeled: bool,
) -> str:
    """One-paragraph lede. All figures are TAM-derived (sourced or reproducible
    synthesis), so this is a rendering — not an authored claim."""
    if mid is None:
        return (
            f"{concept_name} could not be sized from the curated bank: no framework "
            f"resolves to sourced primitives for this market. Every numeric question "
            f"below is an honest gap rather than a fabricated figure."
        )
    triangulation = (
        f"triangulated across {n_method_families} independent method families "
        f"(independence {independence_score:.2f})"
        if n_method_families >= 2
        else "from a single method family (no independent cross-check yet)"
    )
    band = (
        f" The defensible range is {usd(low)} to {usd(high)}."
        if low is not None and high is not None
        else ""
    )
    caveat = (
        " Some inputs are modeled rather than externally sourced — see Limitations "
        "before citing the headline as a regulator-grade figure."
        if has_modeled
        else ""
    )
    return (
        f"{concept_name} is sized at approximately {usd(mid)}, {triangulation}.{band}"
        f"{caveat} Every figure traces to a sourced primitive or a reproducible "
        f"derivation at this TAM's permalink."
    )


def triangulation_note(
    *, n_method_families: int, low: float | None, high: float | None, spread_x: float | None
) -> str:
    """Why the methods (dis)agree — the #1 credibility marker for a premium report."""
    if n_method_families < 2 or low is None or high is None:
        return (
            "Only one method family sized this market, so there is no independent "
            "cross-check. Treat the figure as directional until a second, "
            "independently-sourced method is added."
        )
    spread = f"{spread_x:.1f}x" if spread_x is not None else "n/a"
    grade = "tight" if (spread_x or 0) <= 1.5 else "broad" if (spread_x or 0) <= 3 else "wide"
    return (
        f"{n_method_families} independent method families bracket the market at "
        f"{usd(low)} (lower) to {usd(high)} (higher) — a {grade} {spread} spread. "
        f"Where they diverge, the scope check explains why (a narrower vs broader "
        f"market definition), rather than hiding the disagreement."
    )
