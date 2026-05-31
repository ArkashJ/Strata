"""Wave 1 / AC1.1 + AC1.2 — citation hosts are real; tier comes from data.

AC1.1: no emitted citation URL has a fabricated host; ``strata.internal`` and
hallucinated hosts are rejected, and the novel Exa path only emits URLs Exa
actually returned.
AC1.2: source tier is derived from the host class / source record, never from
the LLM's claimed tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.models import SourceTier
from strata.registry import Registry
from strata.resolver.citations import (
    FabricatedHostError,
    assert_real_host,
    host_of,
    is_internal,
    is_real_host,
    source_hosts_from_registry,
    tier_for_host,
)

_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def reg() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


def test_internal_marker_is_not_a_real_host() -> None:
    assert is_internal("https://strata.internal/models/x")
    with pytest.raises(FabricatedHostError):
        assert_real_host("https://strata.internal/models/x", frozenset())


def test_fabricated_host_rejected() -> None:
    with pytest.raises(FabricatedHostError):
        assert_real_host("https://totally-made-up-12345.example/foo", frozenset())


def test_gov_hosts_allowed() -> None:
    assert is_real_host("https://www.bls.gov/oes/current/oes151252.htm", frozenset())
    assert is_real_host("https://nass.usda.gov/whatever", frozenset())


def test_every_registry_citation_is_real_or_internal(reg: Registry) -> None:
    """AC1.1 — every committed primitive's host is allowlisted OR the honest
    internal-modeled marker (which the emit layer scrubs to null)."""
    allowed = source_hosts_from_registry(reg)
    for p in reg.atomic.values():
        url = p.source.url
        assert is_real_host(url, allowed) or is_internal(url), f"{p.slug}: bad host {url!r}"


def test_tier_from_host_not_model() -> None:
    # AC1.2 — a gov host is regulator regardless of any claimed tier; an unknown
    # host is community, never regulator/analyst on someone's say-so.
    assert tier_for_host(host_of("https://www.bls.gov/x")) is SourceTier.REGULATOR
    assert tier_for_host(host_of("https://data.worldbank.org/x")) is SourceTier.AGGREGATOR
    assert tier_for_host(host_of("https://some-blog.example/x")) is SourceTier.COMMUNITY
    # A prediction market is not a regulator (review fix).
    assert tier_for_host(host_of("https://kalshi.com/markets/x")) is SourceTier.PREDICTION_MARKET
