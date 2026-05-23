"""TAM Output record (Q1, Q38).

TAMs are scenario trees, never scalars + error bars (Q1). Each scenario pins
every primitive it consumes by ``snapshot_sha256`` (Q5) so the result is
reproducible from `/tam/<hash>`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import AnalysisLens, Sha256Hex, Slug
from .framework import InputRole
from .unit import Unit


class ExpansionStage(StrEnum):
    WEDGE = "wedge"
    ADJACENT = "adjacent"
    PLATFORM = "platform"
    NOT_APPLICABLE = "n/a"


class TAMTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concept: Slug
    geo: str | None = None
    time: str | None = None
    expansion_stage: ExpansionStage = ExpansionStage.NOT_APPLICABLE


class InputUsed(BaseModel):
    """One row of `inputs_used` on a scenario. Pinned by snapshot_sha256
    (Q5) so the scenario is reproducible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_name: str  # Q39 lens role (e.g., persona_pool); FrameworkInput.name
    role: InputRole  # Q6 role tag
    primitive_slug: Slug
    snapshot_sha256: Sha256Hex


class ScenarioBanner(BaseModel):
    """Banner attached to a scenario when it consumes a primitive with a
    qualifier (Q20 synthetic, Q40 paraphrase, etc.).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str  # e.g., "analyst-paraphrase", "synthetic", "modeled"
    message: str


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    definition: str
    lens: AnalysisLens
    framework: Slug
    framework_variant: str | None = None

    value: float
    unit: Unit

    inputs_used: tuple[InputUsed, ...]
    assumptions: dict[str, str] = Field(default_factory=dict[str, str])
    banners: tuple[ScenarioBanner, ...] = ()


class TAMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["tam_output"]
    slug: Slug  # hash-based permanent URL (Q38)
    schema_version: int = Field(ge=1)
    created_by: Slug
    created_at: datetime

    target: TAMTarget
    scenarios: tuple[Scenario, ...]

    method_families_used: tuple[str, ...] = ()
    independence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uses_synthetic_primitives: bool = False
    uses_modeled_composites: bool = False
