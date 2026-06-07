"""Framework record (Q3, Q15-Q18, Q39).

Frameworks are the only place unit-crossing arithmetic lives (Q3). Every
input is a primitive slug — no scalar defaults (Q15). Each framework declares
exactly one ``lens`` (Q39); the validator enforces lens-tag agreement against
consuming concepts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # Phase 2 — structurally-distinct families the formula engine enables:
    # adoption-curve (latent_demand S-curve) and weighted-blend (min/max
    # triangulation of two same-unit estimates). They score as independent
    # method families for convergence/independence (engine.py).
    ADOPTION_CURVE = "adoption_curve"
    WEIGHTED_BLEND = "weighted_blend"


class RealismModifier(StrEnum):
    """How a SUBFRAMEWORK specializes its lens's canonical math shape.

    The six lenses are six multiplication shapes (the IP). A subframework is that
    same shape with one or more of these realism treatments applied to the
    formula — so a number it produces differs, but the structure is the lens's.
    A canonical framework declares NO modifier (it *is* the raw shape).

      BOUNDED         a clamp(...) caps a factor — can't displace/capture >100%
      ADOPTION_GATED  curve()/logistic() gates a rate by an S-curve over time
      SATURATING      a saturating curve (ceiling) without the logistic midpoint
      ADDRESSABLE     an extra addressable_share factor narrows the base
      REDUCED         a degenerate form that drops one of the canonical roles
    """

    BOUNDED = "bounded"
    ADOPTION_GATED = "adoption_gated"
    SATURATING = "saturating"
    ADDRESSABLE = "addressable"
    REDUCED = "reduced"


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

    # Taxonomy (2026-06-07 reframe): the 6 lens shapes are the canonical
    # frameworks (parent_lens_shape=None, no realism_modifiers). Every other
    # framework is a SUBFRAMEWORK — the same shape specialized — and points at
    # its lens's canonical via ``parent_lens_shape`` and names how it differs via
    # ``realism_modifiers``. The cross-record validator enforces "exactly one
    # canonical per lens" so the count of distinct shapes can't silently inflate.
    parent_lens_shape: Slug | None = None
    realism_modifiers: tuple[RealismModifier, ...] = ()

    inputs: tuple[FrameworkInput, ...]
    formula: str
    output_unit: Unit

    applicable_to: tuple[Slug, ...] = ()
    not_applicable_to: tuple[Slug, ...] = ()
    requires_clearance: tuple[str, ...] = ()

    variants: tuple[FrameworkVariant, ...] = ()

    expansion_stage_parameter: bool = False
    horizon_class: HorizonClass = HorizonClass.SNAPSHOT

    @model_validator(mode="after")
    def _taxonomy_pair_coheres(self) -> Framework:
        """The canonical/subframework distinction is a LOCAL invariant of a single
        framework (it relates only this record's ``parent_lens_shape`` and
        ``realism_modifiers``), so it must hold at *every* construction — a row
        from Postgres, an MCP build path, a test — not just under ``strata
        validate``. Mirrors ``_formula_parses``: load-bearing local invariants
        live on the model. The genuinely cross-record parts (parent exists, is a
        same-lens canonical, one canonical per lens) stay in the cross validator.

          canonical  (parent_lens_shape is None)  ⇒ NO realism_modifiers
          subframework (parent set)               ⇒ ≥1 realism_modifier
          a framework is never its own parent
        """
        if self.parent_lens_shape is None and self.realism_modifiers:
            raise ValueError(
                f"canonical framework {self.slug!r} (no parent_lens_shape) must not "
                f"declare realism_modifiers; it is the raw lens shape"
            )
        if self.parent_lens_shape is not None and not self.realism_modifiers:
            raise ValueError(
                f"subframework {self.slug!r} declares a parent but no realism_modifiers; "
                f"a specialization must name how it differs from the canonical shape"
            )
        if self.parent_lens_shape == self.slug:
            raise ValueError(f"framework {self.slug!r} cannot be its own parent_lens_shape")
        return self

    @model_validator(mode="after")
    def _formula_parses(self) -> Framework:
        """Phase 2: the formula is load-bearing, so a syntactically broken or
        unknown-identifier formula must fail at construction — i.e. whenever the
        framework is loaded from YAML or Postgres, not just under ``strata
        validate``. The deeper unit-coherence check stays in the cross-record
        validator. Imported lazily (the parser has no model dependency; the
        ``formula`` package's unit algebra imports this module)."""
        from ..evaluator.formula import identifiers
        from ..evaluator.formula.parser import parse

        ast = parse(self.formula)  # raises FormulaSyntaxError on bad text
        declared = {inp.name for inp in self.inputs}
        unknown = sorted(identifiers(ast) - declared)
        if unknown:
            raise ValueError(
                f"framework {self.slug!r} formula references undeclared input(s): {unknown}"
            )
        return self

    def variant_for(self, scope: str) -> FrameworkVariant | None:
        for v in self.variants:
            if v.scope == scope:
                return v
        return None
