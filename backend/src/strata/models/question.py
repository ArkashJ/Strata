"""Analysis-question records + the runtime answer fence (PR4).

An :class:`AnalysisQuestion` is a curated, loadable YAML record that pairs a
human prompt ("what's the growth rate?") with an *answer strategy* that resolves
the prompt against already-sourced registry objects — never against an authored
number or an LLM. The fence is **structural**: every variant of
:data:`AnswerSpec` may reference only registry selectors (role names, concept
slugs by way of measurements, allowlisted TAM fields) and carries NO numeric
field, so a literal figure cannot be smuggled into the bank (Q20).

The second half of the fence is :class:`ResolvedAnswer`, the assembler's runtime
output (never loaded from YAML): its ``model_validator`` forbids a numeric
``value`` unless that value is backed by registry provenance or a reproducible
TAM-field synthesis — mirroring ``AtomicPrimitive._derive_provenance``. Together
the two make an unsourced number impossible at the type boundary.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from ._common import AnalysisLens, Sha256Hex, Slug

# Question ids look like ``Q-MS-001`` — a category mnemonic + a zero-padded
# sequence. Lower-cased it doubles as the file slug (``q-ms-001.yaml``).
QUESTION_ID_PATTERN = r"^Q-[A-Z]+-\d{3}$"

# The whitelisted placeholder tokens a narrative_template / gap_text may use.
# A typo'd token must fail at load (validator), not silently render ``{value}``.
TEMPLATE_TOKENS: frozenset[str] = frozenset(
    {
        "value",
        "source_name",
        "source_tier",
        "as_of",
        "snapshot",
        "spread",
        "ratio",
        "low",
        "high",
        "count",
        "n_methods",
    }
)

_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


class QuestionCategory(StrEnum):
    """The spec's 10 analysis buckets, verbatim."""

    MARKET_SIZE = "market_size"
    GROWTH_RATE = "growth_rate"
    SEGMENTATION = "segmentation"
    GEOGRAPHY = "geography"
    COMPETITION_SHARE = "competition_share"
    REGULATION = "regulation"
    ADOPTION = "adoption"
    UNIT_ECONOMICS = "unit_economics"
    RISKS = "risks"
    METHODOLOGY = "methodology"


class AnswerStrategy(StrEnum):
    """How an answer resolves a prompt against the registry."""

    PRIMITIVE_ROLE = "primitive_role"
    CONCEPT_MEASUREMENT = "concept_measurement"
    TAM_FIELD = "tam_field"
    QUALITATIVE = "qualitative"


class TamField(StrEnum):
    """Safe allowlist of ``TAMOutput`` fields a ``tam_field`` answer may read.

    Each is a pure synthesis of already-sourced scenario values (NEVER a
    fabricated number). The assembler reads the named field off the *computed*
    ``TAMOutput`` — the field name here is just a selector, so no literal number
    ever lives in YAML.
    """

    TRIANGULATED_MID = "triangulated_mid"
    RANGE_LOW = "range_low"
    RANGE_HIGH = "range_high"
    RANGE_SPREAD_RATIO = "range_spread_ratio"
    METHOD_FAMILIES_COUNT = "method_families_count"
    INDEPENDENCE_SCORE = "independence_score"
    CONVERGENCE_RATIO = "convergence_ratio"
    CONVERGENCE_LOW = "convergence_low"
    CONVERGENCE_HIGH = "convergence_high"
    USES_MODELED_INPUTS = "uses_modeled_inputs"
    SCENARIO_COUNT = "scenario_count"


class Aggregation(StrEnum):
    """How a primitive_role / concept_measurement answer collapses matches."""

    VALUE = "value"
    SPREAD = "spread"
    LIST = "list"
    COUNT = "count"


class Applicability(BaseModel):
    """The ``applies_when`` gate. Empty = the question always applies.

    Role strings are validated downstream against ``REQUIRED_PRIMITIVE_ROLES``
    (roles are per-lens, not a global enum), not here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lens_in: tuple[AnalysisLens, ...] = ()
    requires_role: tuple[str, ...] = ()
    requires_modifier: tuple[str, ...] = ()
    requires_secondary_lens: bool = False


# --- AnswerSpec: the load-bearing fence -----------------------------------
# Four frozen variants discriminated on ``strategy``. Each STRUCTURALLY forbids
# a literal number — no float/int value field exists on any branch; only
# registry selectors. Mirrors source.py's TypeAdapter + Field(discriminator=...)
# pattern (discriminated unions are typing constructs, not models).


class _AnswerBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrimitiveRoleAnswer(_AnswerBase):
    """Resolve a role → the framework-variant binding → a sourced primitive."""

    strategy: Literal[AnswerStrategy.PRIMITIVE_ROLE]
    roles: tuple[str, ...] = Field(min_length=1)
    aggregation: Aggregation = Aggregation.VALUE


class ConceptMeasurementAnswer(_AnswerBase):
    """Read the concept's competing measurements.

    Defaults to ``spread`` because ≥2 disagreeing measurements are the point —
    "disagreement gets a page, not a footnote".
    """

    strategy: Literal[AnswerStrategy.CONCEPT_MEASUREMENT]
    aggregation: Aggregation = Aggregation.SPREAD


class TamFieldAnswer(_AnswerBase):
    """Read ONE allowlisted field off the computed ``TAMOutput``."""

    strategy: Literal[AnswerStrategy.TAM_FIELD]
    field: TamField


class QualitativeAnswer(_AnswerBase):
    """Sourced narrative (regulation / risk), no numeric claim."""

    strategy: Literal[AnswerStrategy.QUALITATIVE]
    source: Literal["modifier", "annotation", "definition"]
    modifier_kind: str | None = None


AnswerSpec = Annotated[
    PrimitiveRoleAnswer | ConceptMeasurementAnswer | TamFieldAnswer | QualitativeAnswer,
    Field(discriminator="strategy"),
]

# Module-level adapter so callers validate raw answer payloads per the
# Pydantic-v2 rule (a discriminated union is a typing construct, not a model).
ANSWER_SPEC_ADAPTER: TypeAdapter[
    PrimitiveRoleAnswer | ConceptMeasurementAnswer | TamFieldAnswer | QualitativeAnswer
] = TypeAdapter(AnswerSpec)


def _template_tokens(template: str) -> set[str]:
    return {m.group(1) for m in _PLACEHOLDER_RE.finditer(template)}


class AnalysisQuestion(BaseModel):
    """A loadable ``analysis_question`` YAML record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["analysis_question"]
    question_id: str = Field(pattern=QUESTION_ID_PATTERN)
    prompt: str = Field(min_length=1)
    category: QuestionCategory
    # Empty = cross-cutting (applies to all lenses).
    lenses: tuple[AnalysisLens, ...] = ()
    applies_when: Applicability = Applicability()
    answer: AnswerSpec
    narrative_template: str = Field(min_length=1)
    gap_text: str = Field(min_length=1)
    # ``connector:method`` hint surfaced when the answer resolves to a gap,
    # reusing the AtomicPrimitive.resource_target convention.
    resource_target: str | None = None
    schema_version: int = Field(ge=1)

    @model_validator(mode="after")
    def _templates_use_known_tokens(self) -> Self:
        # Every {placeholder} in narrative_template must be a known token, so a
        # typo fails at load, not silently at render. (No literal-number check is
        # needed: AnswerSpec carries no numeric field, so a figure cannot leak
        # in by construction — this only guards template wiring.)
        unknown = _template_tokens(self.narrative_template) - TEMPLATE_TOKENS
        if unknown:
            raise ValueError(
                f"narrative_template uses unknown placeholder(s) "
                f"{sorted(unknown)}; allowed tokens are {sorted(TEMPLATE_TOKENS)}"
            )
        return self


# --- ResolvedAnswer: the assembler's runtime output (NOT loaded from YAML) --


class AnswerProvenance(BaseModel):
    """One provenance row behind a resolved answer (InputUsed shape semantics).

    ``source_url`` is ``None`` for composites (a union of members has no single
    source of its own) — honest, never fabricated.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    primitive_slug: Slug
    source_url: str | None = None
    source_tier: str | None = None
    snapshot_sha256: Sha256Hex
    as_of: date | None = None


class ResolvedAnswer(BaseModel):
    """The assembler's output. The runtime half of the Q20 fence.

    A numeric ``value`` is structurally impossible unless it is backed by a
    registry primitive (``provenance``) or a reproducible TAM-field derivation
    (``synthesis``). All numbers here come ONLY from registry primitives or the
    computed ``TAMOutput`` scenarios — never authored, never LLM.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    prompt: str
    category: QuestionCategory
    status: Literal["answered", "gap"]

    value: float | None = None
    display: str | None = None
    narrative: str

    provenance: tuple[AnswerProvenance, ...] = ()
    # Set only for tam_field answers: names the reproducible derivation, e.g.
    # "high/low across 2 method families at /tam/<hash>".
    synthesis: str | None = None
    resource_target: str | None = None

    @model_validator(mode="after")
    def _no_unsourced_number(self) -> Self:
        if self.status == "gap":
            if self.value is not None:
                raise ValueError("a gap answer must have value=None")
            if self.provenance:
                raise ValueError("a gap answer must have empty provenance")
            return self
        # status == "answered": a number must be sourced or derived.
        if self.value is not None and not self.provenance and self.synthesis is None:
            raise ValueError(
                "ResolvedAnswer.value is set but unsourced: a numeric value "
                "requires at least one provenance row or a non-null synthesis "
                "(Q20 — no authored numbers)"
            )
        return self


class ConceptQuestionReport(BaseModel):
    """The assembled report for one concept: meta + resolved answers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_slug: Slug
    concept_name: str
    answers: tuple[ResolvedAnswer, ...] = ()
