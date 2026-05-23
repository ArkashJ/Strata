"""Geo type (Q8). Two parallel fields — geo_supply / geo_demand — live on the
primitive; this module models the shared ``Geo`` record and the perspective
enum.
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
