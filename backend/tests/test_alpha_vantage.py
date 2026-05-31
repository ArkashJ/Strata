"""Tests for the Alpha Vantage connector capability + client."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

import httpx
import pytest

from strata.connectors.alpha_vantage import (
    AlphaVantageClient,
    AlphaVantageClientError,
    AlphaVantageFunction,
    AlphaVantageInterval,
    CompanyOverview,
    Earnings,
    EconomicIndicator,
    EconomicSeries,
    FinancialStatements,
    GlobalQuote,
    capabilities,
    economic_to_primitive_yaml,
    market_cap_to_primitive_yaml,
)


def _client(
    cache_dir: Path,
    routes: Mapping[str, object],
    *,
    status: int = 200,
) -> AlphaVantageClient:
    """Build a client whose transport dispatches on the ``function`` query param."""

    def handler(request: httpx.Request) -> httpx.Response:
        fn = request.url.params.get("function", "")
        return httpx.Response(status, json=routes.get(fn, {}))

    return AlphaVantageClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        cache_dir=cache_dir,
    )


def test_daily_time_series_parses(tmp_path: Path) -> None:
    payload = {
        "Time Series (Daily)": {
            "2024-01-03": {
                "1. open": "100.0",
                "2. high": "105.0",
                "3. low": "99.0",
                "4. close": "104.0",
                "5. volume": "1000000",
            },
            "2024-01-02": {
                "1. open": "98.0",
                "2. high": "101.0",
                "3. low": "97.0",
                "4. close": "100.0",
                "5. volume": "900000",
            },
        }
    }
    client = _client(tmp_path, {"TIME_SERIES_DAILY": payload})
    bars = client.get_daily("IBM")
    assert len(bars) == 2
    assert bars[-1].close == 104.0
    assert bars[-1].date == date(2024, 1, 3)
    assert bars[-1].volume == 1000000


def test_global_quote_parses(tmp_path: Path) -> None:
    payload = {
        "Global Quote": {
            "01. symbol": "IBM",
            "05. price": "189.50",
            "06. volume": "3200000",
            "07. latest trading day": "2024-01-02",
            "09. change": "1.25",
            "10. change percent": "0.66%",
        }
    }
    client = _client(tmp_path, {"GLOBAL_QUOTE": payload})
    quote = client.get_global_quote("IBM")
    assert isinstance(quote, GlobalQuote)
    assert quote.price == 189.50
    assert quote.change_percent == "0.66%"


def test_economic_indicator_parses(tmp_path: Path) -> None:
    payload = {
        "name": "Real Gross Domestic Product",
        "interval": "annual",
        "unit": "billions of dollars",
        "data": [
            {"date": "2023-01-01", "value": "22000.0"},
            {"date": "2022-01-01", "value": "21000.0"},
        ],
    }
    client = _client(tmp_path, {"REAL_GDP": payload})
    series = client.get_real_gdp()
    assert isinstance(series, EconomicSeries)
    assert series.unit == "billions of dollars"
    assert len(series.observations) == 2
    assert series.observations[0].value == 22000.0


def test_intraday_threads_interval(tmp_path: Path) -> None:
    payload = {
        "Time Series (15min)": {
            "2024-01-02 16:00:00": {
                "1. open": "1.0",
                "2. high": "2.0",
                "3. low": "0.5",
                "4. close": "1.5",
                "5. volume": "10",
            }
        }
    }
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["interval"] = request.url.params.get("interval", "")
        return httpx.Response(200, json=payload)

    client = AlphaVantageClient(
        api_key="x", transport=httpx.MockTransport(handler), cache_dir=tmp_path
    )
    bars = client.get_intraday("IBM", interval=AlphaVantageInterval.MIN_15)
    assert seen["interval"] == "15min"
    assert len(bars) == 1
    assert bars[0].date == date(2024, 1, 2)


def test_currency_exchange_rate_parses(tmp_path: Path) -> None:
    payload = {
        "Realtime Currency Exchange Rate": {
            "1. From_Currency Code": "EUR",
            "3. To_Currency Code": "USD",
            "5. Exchange Rate": "1.0850",
            "6. Last Refreshed": "2024-01-02 12:00:00",
        }
    }
    client = _client(tmp_path, {"CURRENCY_EXCHANGE_RATE": payload})
    rate = client.get_currency_exchange_rate("EUR", "USD")
    assert rate.rate == 1.0850
    assert rate.to_currency == "USD"


def test_rate_limit_note_raises(tmp_path: Path) -> None:
    payload = {
        "Note": "Thank you for using Alpha Vantage! Our standard API rate limit "
        "is 25 requests per day."
    }
    client = _client(tmp_path, {"GLOBAL_QUOTE": payload})
    with pytest.raises(AlphaVantageClientError, match="rate limit"):
        client.get_global_quote("IBM")


def test_error_message_raises(tmp_path: Path) -> None:
    payload = {"Error Message": "Invalid API call."}
    client = _client(tmp_path, {"OVERVIEW": payload})
    with pytest.raises(AlphaVantageClientError, match="Invalid API call"):
        client.get_company_overview("NOPE")


def test_market_cap_converter() -> None:
    overview = CompanyOverview(
        symbol="IBM",
        name="International Business Machines",
        exchange="NYSE",
        sector="TECHNOLOGY",
        industry="Computers",
        market_cap_usd=150_000_000_000.0,
        ebitda=None,
        pe_ratio=None,
        dividend_yield=None,
        revenue_ttm=None,
        currency="USD",
    )
    prim = market_cap_to_primitive_yaml(
        overview, slug="market-cap-ibm", concept_slug="ibm", accessed=date(2024, 1, 1)
    )
    assert prim["value"] == 150_000_000_000.0
    assert prim["unit"]["currency"] == "USD"
    assert prim["source"]["tier"] == "aggregator"
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_income_statement_parses(tmp_path: Path) -> None:
    payload = {
        "symbol": "IBM",
        "annualReports": [
            {"fiscalDateEnding": "2023-12-31", "reportedCurrency": "USD", "totalRevenue": "61000"}
        ],
        "quarterlyReports": [],
    }
    client = _client(tmp_path, {"INCOME_STATEMENT": payload})
    stmts = client.get_income_statement("IBM")
    assert isinstance(stmts, FinancialStatements)
    assert stmts.annual[0].line_items


def test_earnings_parses(tmp_path: Path) -> None:
    payload = {
        "symbol": "IBM",
        "annualEarnings": [{"fiscalDateEnding": "2023-12-31", "reportedEPS": "9.50"}],
        "quarterlyEarnings": [],
    }
    client = _client(tmp_path, {"EARNINGS": payload})
    earnings = client.get_earnings("IBM")
    assert isinstance(earnings, Earnings)
    assert earnings.annual[0].reported_eps == 9.50


def test_economic_converter() -> None:
    series = EconomicSeries(
        function=AlphaVantageFunction.REAL_GDP,
        name="Real GDP",
        interval="annual",
        unit="b",
        observations=(),
    )
    indicator = EconomicIndicator(date=date(2023, 1, 1), value=22000.0)
    prim = economic_to_primitive_yaml(
        series, indicator, slug="gdp-2023", concept_slug="us-gdp", accessed=date(2024, 1, 1)
    )
    assert prim["value"] == 22000.0
    assert prim["source"]["tier"] == "aggregator"


def test_capabilities_methods_exist_and_fragile() -> None:
    specs = capabilities()
    assert specs
    for spec in specs:
        assert hasattr(AlphaVantageClient, spec.method)
        assert spec.is_fragile is True
