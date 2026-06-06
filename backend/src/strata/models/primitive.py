"""Atomic + composite primitives (Q2, Q3).

- Atomic: one source, one number, reproducible.
- Composite: same-unit-in/same-unit-out set operations only (union, intersection,
  filter, restrict_by_tag). Unit-crossing arithmetic belongs in a framework.
"""

from __future__ import annotations

import math
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._common import Slug
from .geo import Geo, GeoPerspective
from .scope import MarketScope
from .source import Source, SourceTier
from .unit import Unit, UnitDimension


class ProvenanceClass(StrEnum):
    """Phase 4 — whether a committed number is a real sourced measurement or a
    hand-seeded estimate. Derived from ``source.tier`` so the two can never
    disagree (the soft tiers are modeled; everything else is sourced)."""

    SOURCED = "sourced"
    MODELED = "modeled"


# The three soft tiers that are estimates, not sourced measurements (Q40).
_MODELED_TIERS: frozenset[SourceTier] = frozenset(
    {SourceTier.COMMUNITY_MODELED, SourceTier.ANALYST_PARAPHRASE, SourceTier.ANALYST}
)


class DistributionShape(StrEnum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    POWER_LAW = "power_law"
    BIMODAL = "bimodal"
    OTHER = "other"


class DeliveryMode(StrEnum):
    DIRECT = "direct"
    EMBEDDED = "embedded"
    BUNDLED = "bundled"
    PLATFORM_PASSTHROUGH = "platform_passthrough"
    NOT_APPLICABLE = "n/a"


class Uncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    range: tuple[float, float]
    basis: str

    def model_post_init(self, _context: object) -> None:
        low, high = self.range
        if low > high:
            raise ValueError(f"uncertainty.range low ({low}) > high ({high})")


class SetOperation(StrEnum):
    UNION = "union"
    INTERSECTION = "intersection"
    FILTER = "filter"
    RESTRICT_BY_TAG = "restrict_by_tag"


class AtomicPrimitive(BaseModel):
    """One sourced number tied to a concept (Q2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["atomic_primitive"]
    slug: Slug
    schema_version: int = Field(ge=1)
    concept_slug: Slug
    name: str
    description: str

    value: float
    unit: Unit

    as_of: date
    expiry: date | None = None

    geo: Geo
    geo_perspective: GeoPerspective

    # The primitive's own true scope (sub-project 1). Defaults empty so existing
    # records load unchanged; the scope guard reads this as the "actual" side and
    # the UI snaps the displayed tag to it.
    scope: MarketScope = MarketScope()

    distribution_shape: DistributionShape = DistributionShape.UNIFORM
    delivery_mode: DeliveryMode = DeliveryMode.NOT_APPLICABLE

    uncertainty: Uncertainty | None = None

    source: Source

    derives_from: tuple[Slug, ...] = ()

    # Wave 5B — visibility. "public" (default) primitives are the curated/seed
    # bank; "private" primitives come from a tenant's connected SaaS data, are
    # org-scoped, never appear in /browse or public seed, and surface a PRIVATE
    # banner downstream. ``org_id`` is set only on private primitives.
    visibility: Literal["public", "private"] = "public"
    org_id: str | None = None

    # Phase 4 — soft-data fence. ``provenance_class`` and ``needs_resourcing``
    # are DERIVED from ``source.tier`` (see ``_derive_provenance``) so a hand-
    # authored YAML can never label a modeled estimate as sourced. They are
    # governance/display metadata — NOT part of the state hash. ``resource_target``
    # is the optional re-sourcing candidate (``connector:method``); ``None`` = an
    # honest gap with no public source (kept, flagged, never fabricated — Q20).
    provenance_class: ProvenanceClass = ProvenanceClass.SOURCED
    needs_resourcing: bool = False
    resource_target: str | None = None

    @model_validator(mode="after")
    def _derive_provenance(self) -> Self:
        expected = (
            ProvenanceClass.MODELED
            if self.source.tier in _MODELED_TIERS
            else ProvenanceClass.SOURCED
        )
        # Frozen model: bypass with object.__setattr__ to keep the derived fields
        # authoritative regardless of what (if anything) the YAML declared.
        if self.provenance_class is not expected:
            object.__setattr__(self, "provenance_class", expected)
        want_resourcing = expected is ProvenanceClass.MODELED
        if self.needs_resourcing is not want_resourcing:
            object.__setattr__(self, "needs_resourcing", want_resourcing)
        return self

    @model_validator(mode="after")
    def _value_must_be_finite(self) -> Self:
        if not math.isfinite(self.value):
            raise ValueError(
                f"atomic_primitive {self.slug!r} value={self.value!r} is not finite "
                f"(NaN/inf would propagate silently through every TAM consuming it)"
            )
        if self.value < 0 and self.unit.dimension != UnitDimension.PERCENT:
            raise ValueError(
                f"atomic_primitive {self.slug!r} value={self.value} negative for "
                f"non-percent unit; reject at construction"
            )
        return self


class CompositePrimitive(BaseModel):
    """Same-unit set op over atomic primitives (Q3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["composite_primitive"]
    slug: Slug
    schema_version: int = Field(ge=1)
    concept_slug: Slug
    name: str
    description: str

    inputs: tuple[Slug, ...]
    set_operation: SetOperation
    tag_filter: str | None = None

    as_of: date
    unit: Unit
    geo: Geo
    geo_perspective: GeoPerspective
