"""Geo type (Q8).

v0.2 collapses Q8's two-parallel-fields design into a single ``geo: Geo``
field plus a ``GeoPerspective`` enum (supply / demand / mixed / unknown) on
each primitive. This works for the doc-gen slice where each primitive cleanly
picks one perspective; restoring the parallel-fields shape is on the v0.3
backlog when a primitive needs to declare both supply and demand geos
simultaneously.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GeoLevel(StrEnum):
    COUNTRY = "country"
    SUBNATIONAL = "subnational"
    SUPRANATIONAL = "supranational"
    GLOBAL = "global"


class GeoAggregationRule(StrEnum):
    UNION = "union"
    SUM = "sum"
    ALLOCATED_BY = "allocated_by"


class GeoPerspective(StrEnum):
    SUPPLY = "supply"
    DEMAND = "demand"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class Geo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: GeoLevel
    codes: tuple[str, ...]
    aggregate: str | None = None
    aggregation_rule: GeoAggregationRule | None = None
    # Used when aggregation_rule=allocated_by — points at a primitive slug.
    allocator_primitive: str | None = None
