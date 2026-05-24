"""Shared primitive types reused across Strata record models.

Decisions traced: Q4 (units), Q5 (sources), Q8 (geo), Q26+Q37+Q40 (source tiers),
Q39 (analysis lens).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field

# Slugs are kebab-case identifiers used across all record kinds.
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
Slug = Annotated[str, Field(pattern=SLUG_PATTERN, min_length=1, max_length=128)]

# Content-hash format (sha256 hex digest). Q5.
SHA256_PATTERN = r"^[a-f0-9]{64}$"
Sha256Hex = Annotated[str, Field(pattern=SHA256_PATTERN, min_length=64, max_length=64)]


class AnalysisLens(StrEnum):
    """Six first-class TAM lenses (Q39).

    Each lens has a structurally distinct math shape; frameworks are tagged to
    exactly one lens and the framework picker filters by the concept's declared
    lens. The validator enforces lens-tag agreement between concept and framework.
    """

    COST_EFFICIENCY = "cost_efficiency"
    REVENUE_GENERATION = "revenue_generation"
    LATENT_DEMAND = "latent_demand"
    PLATFORM_THROUGHPUT = "platform_throughput"
    BUNDLE_CONSOLIDATION = "bundle_consolidation"
    PRODUCTIVITY_UPLIFT = "productivity_uplift"


# Lens → required primitive roles (Q39 schema delta).
# Static mapping; concepts declare a lens, frameworks declare a lens, and
# variants bind these named roles to primitive slugs (honouring Q15: no scalar
# defaults — every binding is a primitive slug).
REQUIRED_PRIMITIVE_ROLES: dict[AnalysisLens, tuple[str, ...]] = {
    AnalysisLens.COST_EFFICIENCY: (
        "persona_pool",
        "addressable_share",
        "replacement_rate",
        "cost_per_persona",
    ),
    AnalysisLens.REVENUE_GENERATION: (
        "target_segment_count",
        "spend_per_target",
        "capture_rate",
    ),
    AnalysisLens.LATENT_DEMAND: (
        "addressable_population",
        "adoption_rate_curve",
        "willingness_to_pay",
    ),
    AnalysisLens.PLATFORM_THROUGHPUT: (
        "gmv_or_volume",
        "take_rate",
        "market_share_assumption",
    ),
    AnalysisLens.BUNDLE_CONSOLIDATION: (
        "tools_displaced",
        "spend_per_tool",
        "consolidation_rate",
        "pricing_discount",
    ),
    AnalysisLens.PRODUCTIVITY_UPLIFT: (
        "persona_count",
        "productivity_gain_pct",
        "value_split_to_vendor",
    ),
}
