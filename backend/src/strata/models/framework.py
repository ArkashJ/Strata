"""Framework record (Q3, Q15-Q18, Q39).

Frameworks are the only place unit-crossing arithmetic lives (Q3). Every
input is a primitive slug — no scalar defaults (Q15). Each framework declares
exactly one ``lens`` (Q39); the validator enforces lens-tag agreement against
consuming concepts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import AnalysisLens, Slug
from .unit import Unit


class MethodFamily(StrEnum):
    """Q7 method families. Independence scoring warns when triangulation
    uses two frameworks from the same family.
    """

    TOP_DOWN_SPEND = "top_down_spend"
    BOTTOMS_UP_SEATS = "bottoms_up_seats"
    COMPARABLE_REVENUE = "comparable_revenue"
    ANALOG_PENETRATION = "analog_penetration"
    VALUE_CHAIN = "value_chain"


class InputRole(StrEnum):
    """Q6 input roles. Distinct from Q39 lens role names: a framework input
    has both a ``name`` (matching a Q39 lens role like ``persona_pool``) and
    a ``role`` (the Q6 time-travel role like ``base_value``).
    """

    BASE_VALUE = "base_value"
    GROWTH_INDEX = "growth_index"
    REGIME_MODIFIER = "regime_modifier"
    CONDITIONAL_ADJUSTMENT = "conditional_adjustment"


class HorizonClass(StrEnum):
    SNAPSHOT = "snapshot"
    SHORT_EXTRAPOLATION = "short_extrapolation"
    LONG_EXTRAPOLATION = "long_extrapolation"


class FrameworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: InputRole
    unit_signature: Unit
    required: bool = True


class FrameworkVariant(BaseModel):
    """Q17 declared variant. v0.2 uses ``scope`` to bind the framework to a
    concept; sector/region variants land at later milestones.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str
    default_inputs: dict[str, Slug] = Field(default_factory=dict[str, Slug])


class Framework(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["framework"]
    slug: Slug
    schema_version: int = Field(ge=1)
    name: str
    method_family: MethodFamily

    # Q39 lens tag. The validator enforces concept.analysis_lens ∋ framework.lens.
    lens: AnalysisLens

    inputs: tuple[FrameworkInput, ...]
    formula: str
    output_unit: Unit

    applicable_to: tuple[Slug, ...] = ()
    not_applicable_to: tuple[Slug, ...] = ()
    requires_clearance: tuple[str, ...] = ()

    variants: tuple[FrameworkVariant, ...] = ()

    expansion_stage_parameter: bool = False
    horizon_class: HorizonClass = HorizonClass.SNAPSHOT

    def variant_for(self, scope: str) -> FrameworkVariant | None:
        for v in self.variants:
            if v.scope == scope:
                return v
        return None
