"""Resolver unit guard (Wave 1 / AC1.6).

The novel fallback multiplies sourced inputs into a TAM. Multiplying inputs with
incompatible unit signatures (e.g. two currency factors → money squared, or zero
currency factors → a unitless TAM) is a silent correctness bug. This guard makes
that multiply *fail loudly* before any number is emitted: a valid TAM product has
exactly one currency-bearing factor (population × WTP, seats × cost/seat,
volume × take-rate, …) and the rest dimensionless/count multipliers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class UnitMismatchError(ValueError):
    """A resolver multiply combined unit signatures that can't yield a TAM."""


def _dimension(unit: Any) -> str | None:
    if isinstance(unit, dict):
        d = unit.get("dimension")
        return str(d) if d is not None else None
    return str(getattr(unit, "dimension", "") or "") or None


def assert_multipliable(units: Iterable[Any]) -> None:
    """Raise ``UnitMismatchError`` unless exactly one factor carries the currency
    dimension (the others being dimensionless / count multipliers)."""
    dims = [_dimension(u) for u in units]
    currency_factors = sum(1 for d in dims if d == "currency")
    if currency_factors == 0:
        raise UnitMismatchError(
            f"resolver multiply has no currency factor — product is not a TAM (dims={dims})"
        )
    if currency_factors > 1:
        raise UnitMismatchError(
            f"resolver multiply has {currency_factors} currency factors — "
            f"money is double-counted (dims={dims})"
        )
