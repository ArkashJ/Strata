"""Capability manifest schema for connectors (spec §5).

Every connector exposes a ``capabilities()`` classmethod (or module-level
``capabilities()`` function for connectors that prefer it) that returns a
list of ``CapabilitySpec``. The router serializes these into a single
prompt block (cached) and asks Claude which method to call for a given
query slot.

The manifest is the only thing the router sees. Anything not on it is
invisible to the LLM, which keeps the surface area auditable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArgType = Literal["str", "int", "float", "bool", "date"]

SourceTier = Literal[
    "first_party",
    "regulator",
    "aggregator",
    "analyst",
    "community",
    "onchain",
    "prediction_market",
    "community-modeled",
]


class CapabilityArg(BaseModel):
    """One argument the connector method takes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: ArgType
    description: str
    example: str | None = None
    required: bool = True


class CapabilitySpec(BaseModel):
    """One callable method on a connector, surfaced to the LLM router."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector: str
    method: str
    description: str = Field(min_length=8)
    returns: str = Field(min_length=4)
    args: list[CapabilityArg] = Field(default_factory=list[CapabilityArg])
    source_tier: SourceTier
    is_fragile: bool = False
    requires_paid_tier: bool = False


_capabilities_cache: list[CapabilitySpec] | None = None


def all_capabilities() -> list[CapabilitySpec]:
    """Walk every connector module and collect its capability specs.

    Import lazily to avoid pulling network-heavy clients at module load.
    Each connector exposes ``capabilities()`` as a module-level function
    or as a ``Client.capabilities()`` classmethod; both are supported.

    Memoized: the capability set is static for the process lifetime (connector
    modules don't change at runtime), so the import + walk runs once. Specs are
    frozen, so sharing the cached list with read-only callers is safe.
    """
    global _capabilities_cache
    if _capabilities_cache is not None:
        return _capabilities_cache

    from . import (
        alpha_vantage,
        bls,
        census,
        cms,
        comtrade,
        dune,
        edgar,
        eia,
        eurostat,
        faa,
        fdic,
        fred,
        github,
        kalshi,
        nasdaq_data_link,
        oecd,
        openfda,
        reddit,
        stack_exchange,
        twitter,
        usda_nass,
        worldbank,
        yfinance,
    )

    modules = [
        alpha_vantage,
        bls,
        census,
        cms,
        comtrade,
        dune,
        edgar,
        eia,
        eurostat,
        faa,
        fdic,
        fred,
        github,
        kalshi,
        nasdaq_data_link,
        oecd,
        openfda,
        reddit,
        stack_exchange,
        twitter,
        usda_nass,
        worldbank,
        yfinance,
    ]

    specs: list[CapabilitySpec] = []
    for mod in modules:
        fn = getattr(mod, "capabilities", None)
        if fn is None:
            continue
        specs.extend(fn())
    _capabilities_cache = specs
    return specs
