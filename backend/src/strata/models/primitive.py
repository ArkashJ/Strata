"""Atomic + composite primitives (Q2, Q3).

- Atomic: one source, one number, reproducible.
- Composite: same-unit-in/same-unit-out set operations only (union, intersection,
  filter, restrict_by_tag). Unit-crossing arithmetic belongs in a framework.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import Slug
from .geo import Geo, GeoPerspective
from .source import Source
from .unit import Unit


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

    distribution_shape: DistributionShape = DistributionShape.UNIFORM
    delivery_mode: DeliveryMode = DeliveryMode.NOT_APPLICABLE

    uncertainty: Uncertainty | None = None

    source: Source

    derives_from: tuple[Slug, ...] = ()


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
