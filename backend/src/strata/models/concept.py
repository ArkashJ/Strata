"""Concept record + Q39 lens schema delta.

A Concept is the curated identity object (Q9, Q10). It declares its
``analysis_lens`` (Q39), optional ``modifiers``, and the measurements
(primitive slugs) that compete to size it.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._common import AnalysisLens, Slug


class ConceptKind(StrEnum):
    CONCEPT = "concept"
    # MARKETPLACE_CONCEPT and COMPANY_CONCEPT are v0.5 features — deferred until
    # the corresponding Pydantic model classes and loader discriminator land.
    # Adding them here would cause the loader to crash if any YAML uses those
    # kind values, since no model handles them yet.


class OpexConversionModifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pricing_premium: float


class MarginCaptureModifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    middleman: Slug


class RegulatoryUnlockModifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    driver: Slug
    effective_date: date


class RiskTransferModifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    loss_basis: Slug


class ConceptModifiers(BaseModel):
    """Four composable modifiers (Q39).

    Each modifier is a field, not a separate lens; they layer onto whichever
    primary lens the concept declares.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    opex_conversion: OpexConversionModifier | None = None
    margin_capture: MarginCaptureModifier | None = None
    regulatory_unlock: RegulatoryUnlockModifier | None = None
    risk_transfer: RiskTransferModifier | None = None


class ConceptAnalysisLens(BaseModel):
    """Primary + optional secondary lens (Q39).

    The validator warns when scenarios from the two lenses land within 30% of
    each other (means secondary isn't doing strategic work).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: AnalysisLens
    secondary: AnalysisLens | None = None

    @model_validator(mode="after")
    def _secondary_differs_from_primary(self) -> Self:
        if self.secondary is not None and self.secondary == self.primary:
            raise ValueError(
                f"analysis_lens.secondary ({self.secondary.value}) must differ from "
                f"primary; a meaningful secondary expresses a distinct math shape"
            )
        return self


class Concept(BaseModel):
    """Default concept record. ``Marketplace`` and ``Company`` variants extend
    this with extra mandatory fields (Q19, Q21) — out of scope for the v0.2
    lens-aware slice but the schema leaves room.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["concept"]
    slug: Slug
    schema_version: int = Field(ge=1)
    name: str
    definition: str

    analysis_lens: ConceptAnalysisLens
    modifiers: ConceptModifiers = ConceptModifiers()

    measurements: tuple[Slug, ...] = ()
    competing_concepts: tuple[Slug, ...] = ()

    requires_clearance: tuple[str, ...] = ()
