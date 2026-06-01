"""Market scope — the structured, checkable definition of *which market* a
number sizes (sub-project 1, 2026-05-31 design).

A ``MarketScope`` sits in three places: a ``Concept`` declares its canonical
scope, an ``AtomicPrimitive`` declares its own *true* scope, and a build state
carries the user's live refinement. The scope guard (``strata.scope.guard``)
compares declared against actual so a displayed scope tag can always tell the
truth about the primitive behind a number.

Both new model fields default to an empty ``MarketScope()`` so existing YAML
loads unchanged.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class CodeSystem(StrEnum):
    """Classification system a coded scope tag references.

    ``NAICS`` (industry) and ``SOC`` (occupation) are hierarchical and the guard
    compares them by significant-prefix containment. ``CUSTOM`` carries a
    human label with no machine hierarchy — the guard treats it as unverifiable
    (``UNKNOWN``) unless two custom tags match exactly.
    """

    NAICS = "NAICS"
    SOC = "SOC"
    CUSTOM = "custom"


class ScopeDimension(StrEnum):
    """The dimension a guard warning refers to (for UI grouping).

    ``VERTICAL``, ``PERSONA``, ``SEGMENT`` and ``GEO`` are code/range-anchored and
    the guard emits warnings for them. ``PRODUCT`` (and the free-text
    ``include`` / ``exclude`` rules) are display-only in v1 — the guard never
    emits a ``PRODUCT`` warning yet, because comparing free-text product
    taxonomies is deferred to a later milestone. It is enumerated here so the UI
    can group the product scope chips it renders.
    """

    VERTICAL = "vertical"
    PERSONA = "persona"
    SEGMENT = "segment"
    GEO = "geo"
    PRODUCT = "product"


class CodedTag(BaseModel):
    """One scope tag: a classification code plus a human label.

    Multiple tags per dimension express a union — e.g. B2B sales reps as SOC
    ``41-3000`` (services) + ``41-4000`` (wholesale & manufacturing).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    system: CodeSystem
    # For NAICS/SOC this is the classification code ("5411", "41-4012"); for
    # CUSTOM it is a free identifier. Never empty.
    code: str
    label: str

    @model_validator(mode="after")
    def _code_non_empty(self) -> Self:
        if not self.code.strip():
            raise ValueError("CodedTag.code must be non-empty")
        return self


class FirmSizeBand(BaseModel):
    """A firm-size segment, e.g. mid-market = 100-999 employees.

    ``None`` on either bound means open-ended (``min_emp=None`` → from 0;
    ``max_emp=None`` → no upper limit). An all-firms scope is the absence of a
    band (``segment=None`` on the scope), not a band with both bounds open.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_emp: int | None = None
    max_emp: int | None = None
    label: str

    @model_validator(mode="after")
    def _bounds_ordered(self) -> Self:
        if self.min_emp is not None and self.max_emp is not None and self.min_emp > self.max_emp:
            raise ValueError(f"FirmSizeBand min_emp ({self.min_emp}) > max_emp ({self.max_emp})")
        return self


class MarketScope(BaseModel):
    """The structured definition of a market (sub-project 1 design).

    Every field defaults empty so an unscoped record is valid; the guard treats
    an empty dimension as "unconstrained" on that side.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    vertical: tuple[CodedTag, ...] = ()
    persona: tuple[CodedTag, ...] = ()
    segment: FirmSizeBand | None = None
    geo_supply: tuple[str, ...] = ()
    geo_demand: tuple[str, ...] = ()
    product: tuple[str, ...] = ()
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when no dimension is declared — an unscoped record."""
        return not (
            self.vertical
            or self.persona
            or self.segment
            or self.geo_supply
            or self.geo_demand
            or self.product
            or self.include
            or self.exclude
        )
