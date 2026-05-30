"""TAM Output record (Q1, Q38).

TAMs are scenario trees, never scalars + error bars (Q1). Each scenario pins
every primitive it consumes by ``snapshot_sha256`` (Q5) so the result is
reproducible from `/tam/<hash>`.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import AnalysisLens, Sha256Hex, Slug
from .framework import InputRole, MethodFamily
from .unit import Unit


class ExpansionStage(StrEnum):
    WEDGE = "wedge"
    ADJACENT = "adjacent"
    PLATFORM = "platform"
    NOT_APPLICABLE = "n/a"


class BannerKind(StrEnum):
    """Banner taxonomy. Surfaces in the UI (U10) and in PDF/markdown exports
    as footnotes.

    `analyst_paraphrase` covers Q40; `synthetic` and `modeled` cover Q20;
    `subsidy` covers regime-modifier frameworks (e.g. IRA); `regulated` covers
    Q36 clearance-gated outputs; `dark_estimate` flags low-confidence
    primitives. `user_override` flags a transient what-if scalar the user typed
    in the `/build` UI — never a sourced/persisted primitive (Strata Live).
    """

    SYNTHETIC = "synthetic"
    MODELED = "modeled"
    SUBSIDY = "subsidy"
    REGULATED = "regulated"
    DARK_ESTIMATE = "dark-estimate"
    ANALYST_PARAPHRASE = "analyst-paraphrase"
    USER_OVERRIDE = "user_override"
    # Wave 5B — a private, org-scoped first-party primitive (connected SaaS
    # data); flags that the TAM is sharpened by data only this tenant can see.
    PRIVATE = "private"


class TAMTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concept: Slug
    concept_name: str | None = None  # human-readable name; populated by evaluator
    geo: str | None = None
    time: str | None = None
    expansion_stage: ExpansionStage = ExpansionStage.NOT_APPLICABLE


class InputUsed(BaseModel):
    """One row of `inputs_used` on a scenario. Pinned by snapshot_sha256
    (Q5) so the scenario is reproducible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_name: str
    role: InputRole
    primitive_slug: Slug
    snapshot_sha256: Sha256Hex
    # Display enrichment — populated by evaluator, absent in stored YAML
    value: float | None = None
    name: str | None = None
    unit: Unit | None = None


class ScenarioBanner(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: BannerKind
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

    # True when a transient what-if scalar override fed this scenario (Strata
    # Live). Carries the synthetic flag down to the per-scenario level so the
    # UI can mark the affected node, not just the whole TAM.
    uses_synthetic_primitives: bool = False


class TAMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["tam_output"]
    # Hash-based permanent URL (Q38). The CLI renders `/tam/<state_hash>`.
    state_hash: Sha256Hex
    schema_version: int = Field(ge=1)
    created_by: Slug
    created_at: datetime

    target: TAMTarget
    scenarios: tuple[Scenario, ...] = Field(min_length=1)

    method_families_used: tuple[MethodFamily, ...] = ()
    independence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uses_synthetic_primitives: bool = False
    uses_modeled_composites: bool = False


class TrajectoryPoint(BaseModel):
    """One data point in a TAM-over-time trajectory.

    `value` is the triangulated midpoint of all satisfiable scenarios at this
    snapshot date; `low`/`high` are the min/max of those scenario values.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: date
    value: float
    low: float
    high: float
    method_families: list[str]
    scenarios_n: int


class TAMTrajectory(BaseModel):
    """TAM-over-time series derived from primitive ``as_of`` dates.

    Each point represents the evaluator output at a distinct ``as_of``
    date — using only the primitives available at or before that date. Points
    where no framework is fully satisfiable are omitted; ``points: []`` means
    the concept has no resolvable history at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_slug: Slug
    concept_name: str
    unit: Unit
    points: list[TrajectoryPoint]
