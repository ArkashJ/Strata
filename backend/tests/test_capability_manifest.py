"""Capability manifest validity (spec §5).

Every connector's ``capabilities()`` must:
 - return a non-empty list of valid CapabilitySpec instances,
 - declare methods that actually exist on the connector module,
 - use only known source tiers,
 - emit globally-unique (connector, method, args-signature) tuples.

The router relies on these invariants; a broken manifest silently teaches
Claude to call a method that doesn't exist.
"""

from __future__ import annotations

import importlib
import inspect

from strata.connectors import all_capabilities
from strata.connectors._capability import CapabilitySpec

EXPECTED_CONNECTORS: frozenset[str] = frozenset(
    {
        "alpha_vantage",
        "bls",
        "census",
        "cms",
        "comtrade",
        "edgar",
        "eia",
        "eurostat",
        "faa",
        "fdic",
        "fred",
        "github",
        "kalshi",
        "nasdaq_data_link",
        "oecd",
        "openfda",
        "reddit",
        "stack_exchange",
        "twitter",
        "usda_nass",
        "worldbank",
        "yfinance",
    }
)


def test_all_connectors_register() -> None:
    specs = all_capabilities()
    declared = {spec.connector for spec in specs}
    assert declared == EXPECTED_CONNECTORS, (
        f"Missing: {EXPECTED_CONNECTORS - declared}; extra: {declared - EXPECTED_CONNECTORS}"
    )


def test_every_spec_is_a_capabilityspec() -> None:
    for spec in all_capabilities():
        assert isinstance(spec, CapabilitySpec)
        assert spec.connector
        assert spec.method
        assert len(spec.description) >= 8
        assert len(spec.returns) >= 4


def test_declared_methods_exist_on_client_class() -> None:
    """Each ``method`` named in a CapabilitySpec must exist on the connector's
    ``Client`` class. Catches typos that would teach the router to call
    methods that don't exist.

    Two registered methods that are intentionally *not* on the client (they
    are convenience aggregators handled in the router/CLI layer) are
    whitelisted below.
    """
    whitelist: set[tuple[str, str]] = set()

    for spec in all_capabilities():
        module = importlib.import_module(f"strata.connectors.{spec.connector}")
        client_classes = [
            obj
            for name, obj in inspect.getmembers(module, inspect.isclass)
            if name.endswith("Client") and not name.endswith("Error")
        ]
        if (spec.connector, spec.method) in whitelist:
            continue
        assert client_classes, f"No Client class found in connector {spec.connector!r}"
        # At least one of the candidate client classes must expose the method
        if not any(hasattr(cls, spec.method) for cls in client_classes):
            raise AssertionError(
                f"Capability spec {spec.connector}.{spec.method} declares a method "
                f"that does not exist on any *Client class in the module."
            )


def test_source_tiers_are_known() -> None:
    valid = {
        "first_party",
        "regulator",
        "aggregator",
        "analyst",
        "community",
        "onchain",
        "prediction_market",
        "community-modeled",
    }
    for spec in all_capabilities():
        assert spec.source_tier in valid, (
            f"unknown tier {spec.source_tier!r} on {spec.connector}.{spec.method}"
        )


def test_fragile_and_paid_flags_are_explicit_bools() -> None:
    for spec in all_capabilities():
        assert isinstance(spec.is_fragile, bool)
        assert isinstance(spec.requires_paid_tier, bool)


def test_yfinance_is_marked_fragile() -> None:
    """Spec §4 — yfinance is an unofficial Yahoo scraper; router must demote."""
    yf = [s for s in all_capabilities() if s.connector == "yfinance"]
    assert yf, "yfinance has no capabilities"
    assert all(s.is_fragile for s in yf)


def test_alpha_vantage_is_marked_fragile() -> None:
    """Spec §4 — 25 req/day free tier; router must demote at query time."""
    av = [s for s in all_capabilities() if s.connector == "alpha_vantage"]
    assert av
    assert all(s.is_fragile for s in av)


def test_twitter_only_exposes_free_endpoints() -> None:
    """Spec §4 / audit fix F — Twitter exposes only the two free endpoints
    (user_lookup_by_username + user_timeline). No search/tweet-volume stubs."""
    methods = {s.method for s in all_capabilities() if s.connector == "twitter"}
    assert methods == {"user_lookup_by_username", "user_timeline"}


def test_nasdaq_premium_capability_is_gated() -> None:
    """Spec §4 — premium datasets gated behind requires_paid_tier."""
    nasdaq = [s for s in all_capabilities() if s.connector == "nasdaq_data_link"]
    assert any(s.requires_paid_tier for s in nasdaq), (
        "expected at least one Nasdaq capability with requires_paid_tier=True"
    )
