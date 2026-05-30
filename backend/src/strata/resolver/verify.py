"""Resolver verifier / critic pass (Wave 1 / AC1.4).

Every *novel* (synthesized) resolve runs through cheap, deterministic checks
before its number is trusted: unit compatibility (no money² / unitless TAM) and
input plausibility (no non-positive or absurd-magnitude factor). Any flag turns
the result into a ``dark_estimate`` — surfaced honestly so the reader treats it
as an unverified back-of-envelope, not a sourced figure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .events import ResolverResult
from .units import UnitMismatchError, assert_multipliable

# A single TAM input factor above this is almost certainly an extraction error
# (no real seat-count / unit-cost / spend pool is > 10^13 in base units).
_IMPLAUSIBLE_MAGNITUDE = 1e13


@dataclass(frozen=True, slots=True)
class Flag:
    kind: str
    message: str


def verify(result: ResolverResult) -> list[Flag]:
    flags: list[Flag] = []

    units = [p.get("unit") for p in result.primitives_used]
    if units:
        try:
            assert_multipliable(units)
        except UnitMismatchError as exc:
            flags.append(Flag("unit_mismatch", str(exc)))

    for p in result.primitives_used:
        raw = p.get("value")
        try:
            v = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            flags.append(Flag("outlier", f"input {p.get('slug')!r} has non-numeric value {raw!r}"))
            continue
        if not math.isfinite(v) or v <= 0:
            flags.append(Flag("outlier", f"input {p.get('slug')!r} has implausible value {v!r}"))
        elif v > _IMPLAUSIBLE_MAGNITUDE:
            flags.append(
                Flag("outlier", f"input {p.get('slug')!r} value {v:g} exceeds plausible magnitude")
            )

    return flags


def apply_verifier(result: ResolverResult) -> ResolverResult:
    """Run the verifier and, on any flag, stamp a ``dark_estimate`` banner.

    Only the synthesized (``fallback``) path is downgraded — registry-sourced
    results are already trusted (every input is hash-pinned)."""
    if result.via != "fallback":
        return result
    flags = verify(result)
    if flags:
        reasons = "; ".join(f.message for f in flags)
        result.banner = f"dark_estimate — unverified synthesis flagged: {reasons}"
    return result


def has_dark_estimate(result: ResolverResult) -> bool:
    return bool(result.banner and result.banner.startswith("dark_estimate"))
