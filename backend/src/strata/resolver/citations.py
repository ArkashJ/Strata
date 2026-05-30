"""Citation-host allowlist + host→tier derivation (Wave 1 / AC1.1 + AC1.2).

The resolver must never emit a *fabricated* citation host (a hallucinated URL or
the internal ``strata.internal`` marker), and source tier must come from the data
— a connector/source record or the URL's host class — **never** from the LLM's
say-so. This module is the single gate for both.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..models import SourceTier
from ..registry import Registry

# The internal/synthetic marker used by community-modeled primitives — a real
# number, but with no external citation. Never a valid emitted host.
INTERNAL_HOST_MARKERS: frozenset[str] = frozenset({"strata.internal"})

# Hosts for the 15 curated gov/aggregator connectors + the public research and
# vendor domains the seed library cites. Combined with the live registry's own
# source hosts (``source_hosts_from_registry``) and the gov/edu TLD rule, this is
# the allowlist a real emitted citation must clear.
CONNECTOR_HOSTS: frozenset[str] = frozenset(
    {
        "bls.gov",
        "www.bls.gov",
        "census.gov",
        "www.census.gov",
        "fred.stlouisfed.org",
        "sec.gov",
        "www.sec.gov",
        "data.worldbank.org",
        "worldbank.org",
        "kalshi.com",
        "oecd.org",
        "data.oecd.org",
        "ec.europa.eu",
        "comtradeapi.un.org",
        "comtrade.un.org",
        "banks.data.fdic.gov",
        "fdic.gov",
        "data.cms.gov",
        "cms.gov",
        "api.eia.gov",
        "eia.gov",
        "quickstats.nass.usda.gov",
        "nass.usda.gov",
        "faa.gov",
        "api.fda.gov",
        "fda.gov",
    }
)

# Host → regulator/aggregator classification for hosts that aren't a registry
# source record (e.g. a novel Exa web hit). Everything else is `community`
# (never `regulator`/`analyst` on the LLM's word).
_AGGREGATOR_HOSTS: frozenset[str] = frozenset(
    {"data.worldbank.org", "worldbank.org", "oecd.org", "data.oecd.org", "comtrade.un.org"}
)


class FabricatedHostError(ValueError):
    """An emitted citation URL has a fabricated / internal / disallowed host."""


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_internal(url: str) -> bool:
    return host_of(url) in INTERNAL_HOST_MARKERS


def _gov_or_edu(host: str) -> bool:
    return host.endswith((".gov", ".edu")) or host == "gov"


def source_hosts_from_registry(reg: Registry) -> frozenset[str]:
    """Every real host the loaded data bank already cites (atomic + signal
    primitives), minus the internal marker."""
    hosts: set[str] = set()
    for pool in (reg.atomic, reg.signals):
        for p in pool.values():
            h = host_of(p.source.url)
            if h and h not in INTERNAL_HOST_MARKERS:
                hosts.add(h)
    return frozenset(hosts)


def is_real_host(url: str, allowed: frozenset[str]) -> bool:
    host = host_of(url)
    if not host or host in INTERNAL_HOST_MARKERS:
        return False
    return host in allowed or host in CONNECTOR_HOSTS or _gov_or_edu(host)


def assert_real_host(url: str, allowed: frozenset[str]) -> None:
    if not is_real_host(url, allowed):
        raise FabricatedHostError(f"citation host for {url!r} is not an allowlisted real source")


def tier_for_host(host: str) -> SourceTier:
    """Deterministic tier from the host class — NOT from the LLM (AC1.2). A
    novel web hit is at best `regulator` (gov/edu) or `aggregator`, else
    `community`; the model's claimed tier is discarded by the caller."""
    host = host.lower()
    if host in _AGGREGATOR_HOSTS:
        return SourceTier.AGGREGATOR
    if _gov_or_edu(host) or host in CONNECTOR_HOSTS:
        return SourceTier.REGULATOR
    return SourceTier.COMMUNITY
