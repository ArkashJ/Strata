"""Structured units (Q4).

Every primitive declares a Unit; every framework input declares a
unit_signature (a Unit-shaped template). Currency is stored nominal — the
query-time path normalizes when needed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class UnitKind(StrEnum):
    STOCK = "stock"
    FLOW = "flow"
    INTENSIVE = "intensive"
    DIMENSIONLESS = "dimensionless"


class UnitDimension(StrEnum):
    PEOPLE = "people"
    CURRENCY = "currency"
    TRANSACTIONS = "transactions"
    EVENTS = "events"
    PERCENT = "percent"
    TOKENS = "tokens"
    IMPRESSIONS = "impressions"
    ORGANIZATIONS = "organizations"
    SEATS = "seats"


class UnitBasis(StrEnum):
    NOMINAL = "nominal"


class Unit(BaseModel):
    """Structured unit per Q4.

    `denominator` carries the "per-X" axis (per-year, per-seat, per-policy);
    `currency` is set only when `dimension` is currency-bearing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: UnitKind
    dimension: UnitDimension
    denominator: str | None = None
    currency: str | None = None
    basis: UnitBasis = UnitBasis.NOMINAL

    def is_compatible_with(self, signature: Unit) -> bool:
        """Loose compatibility used for unit_signature validation.

        A signature with `currency=None` accepts any currency; an unset
        denominator on the signature accepts any denominator. Dimensions must
        match exactly.
        """
        if self.dimension != signature.dimension:
            return False
        if self.kind != signature.kind:
            return False
        if signature.denominator is not None and signature.denominator != self.denominator:
            return False
        return not (signature.currency is not None and signature.currency != self.currency)
