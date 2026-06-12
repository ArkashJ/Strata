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
from .scope import ScopeReport
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
    # Source tier of the underlying primitive (or "mixed" for a composite) so the
    # TAM artifact can show a per-input provenance breakdown.
    source_tier: str | None = None
    # The atomic primitive's source URL — lets the UI hyperlink the number
    # itself to the source behind it (number-level provenance, sub-project 3).
    # None for composites: a union of members has no single source of its own.
    # Display enrichment only — the state-hash payload projects
    # name/primitive/hash per input, so this can never re-mint a permalink.
    source_url: str | None = None


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


class Convergence(BaseModel):
    """Bottoms-up vs tops-down cross-check (MV2). When a concept is sized by ≥2
    *independent* method families, the two family medians are compared head to
    head: the agreement ratio (high/low) is the triangulation signal a VC would
    otherwise assemble by hand. This is pure synthesis of already-sourced
    scenario values — no new number is invented. ``None`` (the default) means the
    concept has a single method family, so there is nothing to converge and the
    UI must NOT manufacture a second method."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    low_family: MethodFamily
    high_family: MethodFamily
    low_value: float
    high_value: float
    # high_value / low_value. 1.0 = perfect agreement; the further from 1, the
    # wider the methods disagree. Labelled "method agreement", never "confidence".
    ratio: float = Field(ge=1.0)
    unit: Unit


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
    # Bottoms-up vs tops-down agreement (MV2). Present only when ≥2 independent
    # method families sized this concept; None otherwise (don't fake a method).
    convergence: Convergence | None = None
    independence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uses_synthetic_primitives: bool = False
    uses_modeled_composites: bool = False
    # Wave 4 — promoted TAMs are the public, indexable growth surface: they show
    # in /browse and the sitemap. Separate from the auto-mint state hash (U6).
    is_promoted: bool = False
    # Sub-project 1 — per-input scope check (declared vs each primitive's true
    # scope, snap-to-truth). Populated by the evaluator; None on TAMs persisted
    # before scope landed. Derived, not part of the state hash.
    scope: ScopeReport | None = None


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


class ProjectionPoint(BaseModel):
    """One anchored point on a today→future projection.

    ``kind`` distinguishes the *realized* base-year market (a sized,
    sourced figure) from the *projected* horizon-year market (the base
    compounded by a sourced growth rate). The UI/exports MUST label them
    differently — a projected number is not a measurement.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    value: float
    kind: Literal["realized", "projected"]


class TAMProjection(BaseModel):
    """Today market + future market for a concept (temporal sizing).

    A projection is pure arithmetic over already-sourced inputs: the today
    TAM midpoint compounded by a **sourced** growth primitive (a CAGR), exactly
    the unit-crossing math frameworks already own (Q3). It is NEVER synthesized
    — when a concept has no sourced growth primitive the evaluator returns
    ``None`` and no projection is shown (the honest gap, mirroring
    :class:`Convergence` returning ``None`` for single-method concepts, Q20).

    The growth primitive's provenance rides the projection: ``cagr_source_tier``
    + ``cagr_snapshot_sha256`` pin it (Q5), and a modeled-tier rate carries a
    ``MODELED`` banner in ``banners`` so a projected-from-modeled future number is
    never silently presented as sourced (Q37). Derived, not part of the TAM state
    hash.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_slug: Slug
    concept_name: str | None = None
    unit: Unit

    base_year: int
    horizon_year: int
    # Compound annual growth rate as a fraction (0.18 == 18%/yr), straight off
    # the sourced growth primitive — never inferred by the engine.
    cagr: float
    cagr_primitive: Slug
    cagr_source_tier: str | None = None
    cagr_snapshot_sha256: Sha256Hex

    today: ProjectionPoint
    horizon: ProjectionPoint

    banners: tuple[ScenarioBanner, ...] = ()
