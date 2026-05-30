"""Source records (Q26, Q37, Q40) modelled as a discriminated union.

The ``analyst-paraphrase`` tier (Q40) sits between ``analyst`` and
``community-modeled`` and unlocks paywalled numerical claims under tight
fair-use rules: short paraphrase (≤ 280 chars), mandatory attribution,
mandatory reviewer. Modelled as its own variant of ``Source`` so the
paraphrase-only fields are required on that branch and forbidden on the rest.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import Sha256Hex, Slug

# Paraphrase claims must be terse — the rule that lets the fair-use shape work.
PARAPHRASE_MAX_CHARS = 280


class SourceTier(StrEnum):
    """Nine tiers ordered roughly first-party → modeled (Q26, Q37, Q40)."""

    FIRST_PARTY = "first_party"
    REGULATOR = "regulator"
    AGGREGATOR = "aggregator"
    ANALYST = "analyst"
    ANALYST_PARAPHRASE = "analyst-paraphrase"
    COMMUNITY = "community"
    ONCHAIN = "onchain"
    PREDICTION_MARKET = "prediction_market"
    COMMUNITY_MODELED = "community-modeled"


class _SourceBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: Slug
    url: str
    accessed: date
    snapshot_sha256: Sha256Hex
    # Wave 1 / AC1.7 — freshness SLA in days. A primitive whose data period
    # (``as_of``) is older than this many days is rendered with a `stale` chip.
    # ``None`` means no SLA declared (never auto-flagged stale).
    freshness_sla_days: int | None = None


class StandardSource(_SourceBase):
    """Every tier except ``analyst-paraphrase``."""

    tier: Literal[
        SourceTier.FIRST_PARTY,
        SourceTier.REGULATOR,
        SourceTier.AGGREGATOR,
        SourceTier.ANALYST,
        SourceTier.COMMUNITY,
        SourceTier.ONCHAIN,
        SourceTier.PREDICTION_MARKET,
        SourceTier.COMMUNITY_MODELED,
    ]


class AnalystParaphraseSource(_SourceBase):
    """Q40 paraphrase variant. ``snapshot_sha256`` is over the paraphrase +
    metadata, not the original document — fair-use transformative.
    """

    tier: Literal[SourceTier.ANALYST_PARAPHRASE]
    original_publisher: str = Field(min_length=1)
    paraphrase_reviewer: Slug
    paraphrase_text: str = Field(min_length=1, max_length=PARAPHRASE_MAX_CHARS)


Source = Annotated[
    StandardSource | AnalystParaphraseSource,
    Field(discriminator="tier"),
]
