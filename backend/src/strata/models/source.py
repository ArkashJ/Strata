"""Source record + 9-tier enum (Q26, Q37, Q40).

The ``analyst-paraphrase`` tier (Q40) sits between ``analyst`` and
``community-modeled`` and unlocks paywalled numerical claims under tight
fair-use rules: short paraphrase (≤ 280 chars), mandatory attribution,
mandatory reviewer.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Source(BaseModel):
    """Citation record. ``snapshot_sha256`` is content-hash-pinned (Q5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: Slug
    tier: SourceTier
    url: str
    accessed: date
    snapshot_sha256: Sha256Hex

    # analyst-paraphrase tier additions (Q40). These are validated as required
    # iff tier == ANALYST_PARAPHRASE; otherwise they MUST be absent.
    original_publisher: str | None = None
    paraphrase_reviewer: Slug | None = None
    paraphrase_text: str | None = Field(default=None, max_length=PARAPHRASE_MAX_CHARS)

    @model_validator(mode="after")
    def _enforce_paraphrase_fields(self) -> Self:
        is_paraphrase = self.tier == SourceTier.ANALYST_PARAPHRASE
        paraphrase_fields = {
            "original_publisher": self.original_publisher,
            "paraphrase_reviewer": self.paraphrase_reviewer,
            "paraphrase_text": self.paraphrase_text,
        }
        if is_paraphrase:
            missing = [k for k, v in paraphrase_fields.items() if v is None]
            if missing:
                raise ValueError(
                    f"analyst-paraphrase source {self.slug!r} requires fields: {missing}"
                )
        else:
            present = [k for k, v in paraphrase_fields.items() if v is not None]
            if present:
                raise ValueError(
                    f"source {self.slug!r} tier={self.tier.value} must not carry "
                    f"paraphrase fields: {present}"
                )
        return self
