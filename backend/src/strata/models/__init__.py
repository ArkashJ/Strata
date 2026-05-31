"""Pydantic models for every Strata record type.

Schemas trace back to docs/07-data-layer-brainstorm.md decisions Q1-Q40 and
docs/09-expert-layer-brainstorm.md decision record E3.
"""

from __future__ import annotations

from ._common import (
    REQUIRED_PRIMITIVE_ROLES,
    SHA256_PATTERN,
    SLUG_PATTERN,
    AnalysisLens,
    Sha256Hex,
    Slug,
)
from .annotation import Annotation, AnnotationKindTag, AnnotationTargetType
from .concept import (
    Concept,
    ConceptAnalysisLens,
    ConceptKind,
    ConceptModifiers,
    MarginCaptureModifier,
    OpexConversionModifier,
    RegulatoryUnlockModifier,
    RiskTransferModifier,
)
from .framework import (
    Framework,
    FrameworkInput,
    FrameworkVariant,
    HorizonClass,
    InputRole,
    MethodFamily,
)
from .geo import Geo, GeoAggregationRule, GeoLevel, GeoPerspective
from .primitive import (
    AtomicPrimitive,
    CompositePrimitive,
    DeliveryMode,
    DistributionShape,
    SetOperation,
    Uncertainty,
)
from .source import (
    PARAPHRASE_MAX_CHARS,
    AnalystParaphraseSource,
    Source,
    SourceTier,
    StandardSource,
)
from .tam_output import (
    BannerKind,
    Convergence,
    ExpansionStage,
    InputUsed,
    Scenario,
    ScenarioBanner,
    TAMOutput,
    TAMTarget,
    TAMTrajectory,
    TrajectoryPoint,
)
from .unit import Unit, UnitBasis, UnitDimension, UnitKind

__all__ = [
    "PARAPHRASE_MAX_CHARS",
    "REQUIRED_PRIMITIVE_ROLES",
    "SHA256_PATTERN",
    "SLUG_PATTERN",
    "AnalysisLens",
    "AnalystParaphraseSource",
    "Annotation",
    "AnnotationKindTag",
    "AnnotationTargetType",
    "AtomicPrimitive",
    "BannerKind",
    "CompositePrimitive",
    "Concept",
    "ConceptAnalysisLens",
    "ConceptKind",
    "ConceptModifiers",
    "Convergence",
    "DeliveryMode",
    "DistributionShape",
    "ExpansionStage",
    "Framework",
    "FrameworkInput",
    "FrameworkVariant",
    "Geo",
    "GeoAggregationRule",
    "GeoLevel",
    "GeoPerspective",
    "HorizonClass",
    "InputRole",
    "InputUsed",
    "MarginCaptureModifier",
    "MethodFamily",
    "OpexConversionModifier",
    "RegulatoryUnlockModifier",
    "RiskTransferModifier",
    "Scenario",
    "ScenarioBanner",
    "SetOperation",
    "Sha256Hex",
    "Slug",
    "Source",
    "SourceTier",
    "StandardSource",
    "TAMOutput",
    "TAMTarget",
    "TAMTrajectory",
    "TrajectoryPoint",
    "Uncertainty",
    "Unit",
    "UnitBasis",
    "UnitDimension",
    "UnitKind",
]
