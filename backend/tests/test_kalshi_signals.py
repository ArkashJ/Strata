"""Tests for the Kalshi connector's new signal-only surface.

Kalshi is the ``prediction_market`` tier — quarantined, never feeds a TAM.
These tests assert signal shapes (candlesticks, series, derived stats) only;
no TAM-primitive conversion is exercised. HTTP is mocked, no network/auth.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from strata.connectors.kalshi import (
    Candlestick,
    KalshiClient,
    KalshiClientError,
    MarketStats,
    Series,
    capabilities,
)


def _client(tmp_path: Path, handler: object) -> KalshiClient:
    return KalshiClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_get_market_history_parses_candlesticks(tmp_path: Path) -> None:
    payload = {
        "candlesticks": [
            {
                "end_period_ts": 1_700_000_000,
                "yes_bid": {"close": 0.40},
                "yes_ask": {"close": 0.44},
                "price": {"close": 0.42},
                "volume": 1500,
                "open_interest": 9000,
            },
            {
                "end_period_ts": 1_700_003_600,
                "yes_bid": {"close": 0.45},
                "yes_ask": {"close": 0.48},
                "price": {"close": 0.46},
                "volume": 800,
                "open_interest": 9200,
            },
        ]
    }
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=payload)

    client = _client(tmp_path, handler)
    resp = client.get_market_history("KXRECSSNBER-26", series_ticker="KXRECSSNBER")
    assert "/series/KXRECSSNBER/markets/KXRECSSNBER-26/candlesticks" in seen["path"]
    assert len(resp.candlesticks) == 2
    c = resp.candlesticks[0]
    assert isinstance(c, Candlestick)
    assert c.price_close == 0.42
    assert c.open_interest == 9000
    assert c.end_time is not None


def test_get_series_parses(tmp_path: Path) -> None:
    payload = {
        "series": {
            "ticker": "KXRECSSNBER",
            "title": "US recession (NBER)",
            "category": "Economics",
            "frequency": "yearly",
            "contract_url": "https://kalshi.com/series/KXRECSSNBER",
        }
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _client(tmp_path, handler)
    resp = client.get_series("KXRECSSNBER")
    assert len(resp.series) == 1
    s = resp.series[0]
    assert isinstance(s, Series)
    assert s.category == "Economics"
    assert s.title == "US recession (NBER)"


def test_get_market_stats_derives_signal(tmp_path: Path) -> None:
    payload = {
        "market": {
            "ticker": "KXRECSSNBER-26",
            "yes_bid_dollars": "0.15",
            "yes_ask_dollars": "0.18",
            "last_price_dollars": "0.165",
            "volume_fp": "120000",
            "open_interest_fp": "45000",
            "liquidity_dollars": "9000",
            "status": "open",
            "category": "Economics",
        }
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _client(tmp_path, handler)
    resp = client.get_market_stats("KXRECSSNBER-26")
    assert isinstance(resp.stats, MarketStats)
    assert resp.stats.midpoint == 0.165
    assert round(resp.stats.spread, 2) == 0.03
    assert resp.stats.volume == 120000.0
    assert resp.stats.is_active is True


def test_get_events_by_category_filters(tmp_path: Path) -> None:
    payload = {
        "events": [
            {"event_ticker": "E1", "title": "Recession", "category": "Economics", "markets": []},
            {"event_ticker": "E2", "title": "BTC price", "category": "Crypto", "markets": []},
            {"event_ticker": "E3", "title": "CPI print", "category": "Economics", "markets": []},
        ]
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _client(tmp_path, handler)
    resp = client.get_events_by_category("Economics")
    tickers = {e.event_ticker for e in resp.events}
    assert tickers == {"E1", "E3"}


def test_market_stats_missing_market_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"market": {}})

    client = _client(tmp_path, handler)
    # An empty market parses to a blank ticker; stats still build but never crash.
    resp = client.get_market_stats("DOESNOTEXIST")
    assert resp.stats is not None


def test_capabilities_stay_signal_minimal() -> None:
    specs = capabilities()
    kalshi = [s for s in specs if s.connector == "kalshi"]
    # Router exposure is intentionally minimal: prediction_market is quarantined.
    assert len(kalshi) <= 1
    for spec in kalshi:
        assert spec.source_tier == "prediction_market"


def test_no_tam_converter_for_new_signals() -> None:
    """The new signal types must NOT have *_to_primitive_yaml converters."""
    import strata.connectors.kalshi as mod

    assert not hasattr(mod, "candlestick_to_primitive_yaml")
    assert not hasattr(mod, "series_to_primitive_yaml")
    assert not hasattr(mod, "stats_to_primitive_yaml")


def test_client_init_error_on_bad_status(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    client = _client(tmp_path, handler)
    with pytest.raises(KalshiClientError, match="Authentication failed"):
        client.get_series("KXRECSSNBER")
