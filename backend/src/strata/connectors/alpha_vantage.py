"""Alpha Vantage connector — equities, FX, crypto, fundamentals, economics.

Alpha Vantage is a commercial market-data vendor exposing equities, FX,
crypto, company fundamentals, and US economic indicators over a single
``/query`` REST endpoint keyed by a ``function`` parameter.

Free tier: 25 requests/day, 5 requests/minute. Over the limit the API
returns a ``Note`` / ``Information`` field (HTTP 200) rather than an error
status; this connector raises :class:`AlphaVantageClientError` in that case.
Every call is disk-cached for 24h to conserve the daily budget, so the
capability manifest carries ``is_fragile=True`` on every method and the
query-time router demotes them unless explicitly asked.

API reference: https://www.alphavantage.co/documentation/
Source tier: ``aggregator`` (a commercial market-data vendor).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict

import httpx

from strata.config import settings

from ._capability import CapabilityArg, CapabilitySpec


class AlphaVantageInterval(StrEnum):
    """Equity time-series cadence + intraday sampling intervals."""

    DAILY = "TIME_SERIES_DAILY"
    WEEKLY = "TIME_SERIES_WEEKLY"
    MONTHLY = "TIME_SERIES_MONTHLY"
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"


class AlphaVantageFunction(StrEnum):
    """Alpha Vantage ``function`` query values."""

    OVERVIEW = "OVERVIEW"
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    EARNINGS = "EARNINGS"
    GLOBAL_QUOTE = "GLOBAL_QUOTE"
    TIME_SERIES_DAILY = "TIME_SERIES_DAILY"
    TIME_SERIES_WEEKLY = "TIME_SERIES_WEEKLY"
    TIME_SERIES_MONTHLY = "TIME_SERIES_MONTHLY"
    TIME_SERIES_INTRADAY = "TIME_SERIES_INTRADAY"
    CURRENCY_EXCHANGE_RATE = "CURRENCY_EXCHANGE_RATE"
    FX_DAILY = "FX_DAILY"
    DIGITAL_CURRENCY_DAILY = "DIGITAL_CURRENCY_DAILY"
    REAL_GDP = "REAL_GDP"
    CPI = "CPI"
    INFLATION = "INFLATION"
    FEDERAL_FUNDS_RATE = "FEDERAL_FUNDS_RATE"
    TREASURY_YIELD = "TREASURY_YIELD"
    UNEMPLOYMENT = "UNEMPLOYMENT"
    RETAIL_SALES = "RETAIL_SALES"
    NONFARM_PAYROLL = "NONFARM_PAYROLL"


class OverviewRaw(TypedDict, total=False):
    Symbol: str
    Name: str
    Exchange: str
    Sector: str
    Industry: str
    MarketCapitalization: str
    EBITDA: str
    PERatio: str
    DividendYield: str
    RevenueTTM: str
    Currency: str


class TimeSeriesEntryRaw(TypedDict, total=False):
    open: str
    high: str
    low: str
    close: str
    volume: str


@dataclass(frozen=True, slots=True)
class CompanyOverview:
    """Company fundamentals from the OVERVIEW endpoint."""

    symbol: str
    name: str
    exchange: str
    sector: str | None
    industry: str | None
    market_cap_usd: float | None
    ebitda: float | None
    pe_ratio: float | None
    dividend_yield: float | None
    revenue_ttm: float | None
    currency: str | None


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """One OHLCV observation for a symbol."""

    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class GlobalQuote:
    """A latest-price snapshot for one symbol (GLOBAL_QUOTE)."""

    symbol: str
    price: float
    open: float
    high: float
    low: float
    volume: int
    latest_trading_day: str
    previous_close: float
    change: float
    change_percent: str


@dataclass(frozen=True, slots=True)
class ExchangeRate:
    """A spot FX or crypto exchange rate (CURRENCY_EXCHANGE_RATE)."""

    from_currency: str
    to_currency: str
    rate: float
    last_refreshed: str
    bid: float | None
    ask: float | None


@dataclass(frozen=True, slots=True)
class FinancialReport:
    """A single fiscal-period financial report (raw key/value strings)."""

    fiscal_date_ending: str
    reported_currency: str
    line_items: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Annual + quarterly statements for one statement type."""

    symbol: str
    function: AlphaVantageFunction
    annual: tuple[FinancialReport, ...]
    quarterly: tuple[FinancialReport, ...]


@dataclass(frozen=True, slots=True)
class EarningsReport:
    """A single reported-earnings period."""

    fiscal_date_ending: str
    reported_eps: float | None


@dataclass(frozen=True, slots=True)
class Earnings:
    """Annual and quarterly EPS history for a symbol."""

    symbol: str
    annual: tuple[EarningsReport, ...]
    quarterly: tuple[EarningsReport, ...]


@dataclass(frozen=True, slots=True)
class EconomicIndicator:
    """A single economic-indicator observation."""

    date: date
    value: float | None


@dataclass(frozen=True, slots=True)
class EconomicSeries:
    """An economic-indicator time series."""

    function: AlphaVantageFunction
    name: str
    interval: str
    unit: str
    observations: tuple[EconomicIndicator, ...]


@dataclass(frozen=True, slots=True)
class AlphaVantageResponse:
    """Unified response wrapper around any normalized record set."""

    function: AlphaVantageFunction
    items: tuple[Any, ...]
    total_count: int


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    text = str(val).strip()
    if text in ("", "None", "-", "."):
        return None
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_overview(raw: dict[str, Any]) -> CompanyOverview:
    return CompanyOverview(
        symbol=str(raw.get("Symbol", "")),
        name=str(raw.get("Name", "")),
        exchange=str(raw.get("Exchange", "")),
        sector=str(raw["Sector"]) if raw.get("Sector") else None,
        industry=str(raw["Industry"]) if raw.get("Industry") else None,
        market_cap_usd=_safe_float(raw.get("MarketCapitalization")),
        ebitda=_safe_float(raw.get("EBITDA")),
        pe_ratio=_safe_float(raw.get("PERatio")),
        dividend_yield=_safe_float(raw.get("DividendYield")),
        revenue_ttm=_safe_float(raw.get("RevenueTTM")),
        currency=str(raw["Currency"]) if raw.get("Currency") else None,
    )


def _find_time_series(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Locate the awkwardly-named ``Time Series (...)`` block in a payload."""
    for key, value in payload.items():
        if key.startswith("Time Series") and isinstance(value, dict):
            return value
    raise AlphaVantageClientError("Alpha Vantage: no time-series block in response")


def _parse_report(raw: dict[str, Any]) -> FinancialReport:
    skip = {"fiscalDateEnding", "reportedCurrency"}
    items = tuple((k, str(v)) for k, v in raw.items() if k not in skip)
    return FinancialReport(
        fiscal_date_ending=str(raw.get("fiscalDateEnding", "")),
        reported_currency=str(raw.get("reportedCurrency", "USD")),
        line_items=items,
    )


def _to_date(ts: str) -> date:
    """Parse a date or datetime stamp into a ``date`` (intraday keeps the day)."""
    return date.fromisoformat(ts.split(" ")[0])


class _DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
        self.directory = directory
        self.ttl = ttl_seconds
        directory.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, params: str) -> tuple[dict[str, Any], float] | None:
        path = self._path(self._key(params))
        if not path.exists():
            return None
        mtime = path.stat().st_mtime
        if time.time() - mtime > self.ttl:
            return None
        try:
            return json.loads(path.read_text()), mtime
        except json.JSONDecodeError:
            return None

    def put(self, params: str, data: dict[str, Any]) -> None:
        self._path(self._key(params)).write_text(json.dumps(data))

    def clear(self) -> int:
        count = 0
        for p in self.directory.glob("*.json"):
            p.unlink()
            count += 1
        return count


class AlphaVantageClientError(RuntimeError):
    pass


class AlphaVantageClient:
    """Alpha Vantage HTTP client. 25 req/day free tier — every call cached 24h."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved = api_key or settings.alpha_vantage_api_key
        if not resolved:
            raise AlphaVantageClientError("Alpha Vantage API key required")
        self.api_key = resolved
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "alpha_vantage")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AlphaVantageClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
        signed_params = {**params, "apikey": self.api_key}
        cache_params = json.dumps(dict(params), sort_keys=True)
        cached = self.cache.get(cache_params)
        if cached is not None:
            return cached[0]
        try:
            resp = self._client.get(self.BASE_URL, params=signed_params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AlphaVantageClientError(f"Alpha Vantage request failed: {exc}") from exc
        _check_api_error(data)
        self.cache.put(cache_params, data)
        return data

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Return fundamentals (market cap, P/E, sector) for an equity."""
        raw = self._request({"function": "OVERVIEW", "symbol": symbol})
        if not raw or not raw.get("Symbol"):
            raise AlphaVantageClientError(f"No overview for {symbol!r}")
        return _parse_overview(raw)

    def get_income_statement(self, symbol: str) -> FinancialStatements:
        """Return annual + quarterly income statements for ``symbol``."""
        return self._statements(AlphaVantageFunction.INCOME_STATEMENT, symbol)

    def get_balance_sheet(self, symbol: str) -> FinancialStatements:
        """Return annual + quarterly balance sheets for ``symbol``."""
        return self._statements(AlphaVantageFunction.BALANCE_SHEET, symbol)

    def get_cash_flow(self, symbol: str) -> FinancialStatements:
        """Return annual + quarterly cash-flow statements for ``symbol``."""
        return self._statements(AlphaVantageFunction.CASH_FLOW, symbol)

    def get_earnings(self, symbol: str) -> Earnings:
        """Return annual + quarterly EPS history for ``symbol``."""
        payload = self._request({"function": "EARNINGS", "symbol": symbol})
        annual = tuple(
            EarningsReport(
                fiscal_date_ending=str(r.get("fiscalDateEnding", "")),
                reported_eps=_safe_float(r.get("reportedEPS")),
            )
            for r in payload.get("annualEarnings") or []
        )
        quarterly = tuple(
            EarningsReport(
                fiscal_date_ending=str(r.get("fiscalDateEnding", "")),
                reported_eps=_safe_float(r.get("reportedEPS")),
            )
            for r in payload.get("quarterlyEarnings") or []
        )
        return Earnings(symbol=symbol, annual=annual, quarterly=quarterly)

    def get_daily(self, symbol: str, *, full: bool = False) -> tuple[TimeSeriesPoint, ...]:
        """Return the daily OHLCV series for ``symbol``."""
        return self._equity_series(AlphaVantageFunction.TIME_SERIES_DAILY, symbol, full=full)

    def get_weekly(self, symbol: str) -> tuple[TimeSeriesPoint, ...]:
        """Return the weekly OHLCV series for ``symbol``."""
        return self._equity_series(AlphaVantageFunction.TIME_SERIES_WEEKLY, symbol)

    def get_monthly(self, symbol: str) -> tuple[TimeSeriesPoint, ...]:
        """Return the monthly OHLCV series for ``symbol``."""
        return self._equity_series(AlphaVantageFunction.TIME_SERIES_MONTHLY, symbol)

    def get_intraday(
        self,
        symbol: str,
        *,
        interval: AlphaVantageInterval = AlphaVantageInterval.MIN_5,
        full: bool = False,
    ) -> tuple[TimeSeriesPoint, ...]:
        """Return the intraday OHLCV series for ``symbol`` at ``interval``."""
        params: dict[str, str] = {
            "function": AlphaVantageFunction.TIME_SERIES_INTRADAY.value,
            "symbol": symbol,
            "interval": interval.value,
            "outputsize": "full" if full else "compact",
        }
        payload = self._request(params)
        return self._parse_bars(symbol, payload)

    def get_global_quote(self, symbol: str) -> GlobalQuote:
        """Return the latest price snapshot for ``symbol``."""
        payload = self._request({"function": "GLOBAL_QUOTE", "symbol": symbol})
        block: dict[str, Any] = payload.get("Global Quote") or {}
        if not block:
            raise AlphaVantageClientError(f"Alpha Vantage: no quote for {symbol!r}")
        return GlobalQuote(
            symbol=str(block.get("01. symbol", symbol)),
            open=_safe_float(block.get("02. open")) or 0.0,
            high=_safe_float(block.get("03. high")) or 0.0,
            low=_safe_float(block.get("04. low")) or 0.0,
            price=_safe_float(block.get("05. price")) or 0.0,
            volume=int(_safe_float(block.get("06. volume")) or 0),
            latest_trading_day=str(block.get("07. latest trading day", "")),
            previous_close=_safe_float(block.get("08. previous close")) or 0.0,
            change=_safe_float(block.get("09. change")) or 0.0,
            change_percent=str(block.get("10. change percent", "")),
        )

    def get_currency_exchange_rate(self, from_currency: str, to_currency: str) -> ExchangeRate:
        """Return the spot exchange rate (FX or crypto) for a pair."""
        params: dict[str, str] = {
            "function": AlphaVantageFunction.CURRENCY_EXCHANGE_RATE.value,
            "from_currency": from_currency,
            "to_currency": to_currency,
        }
        payload = self._request(params)
        block: dict[str, Any] = payload.get("Realtime Currency Exchange Rate") or {}
        if not block:
            raise AlphaVantageClientError(
                f"Alpha Vantage: no exchange rate for {from_currency}->{to_currency}"
            )
        return ExchangeRate(
            from_currency=str(block.get("1. From_Currency Code", from_currency)),
            to_currency=str(block.get("3. To_Currency Code", to_currency)),
            rate=_safe_float(block.get("5. Exchange Rate")) or 0.0,
            last_refreshed=str(block.get("6. Last Refreshed", "")),
            bid=_safe_float(block.get("8. Bid Price")),
            ask=_safe_float(block.get("9. Ask Price")),
        )

    def get_fx_daily(self, from_symbol: str, to_symbol: str) -> tuple[TimeSeriesPoint, ...]:
        """Return the daily FX series for a currency pair (volume reported 0)."""
        params: dict[str, str] = {
            "function": AlphaVantageFunction.FX_DAILY.value,
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
        }
        payload = self._request(params)
        series = _find_time_series(payload)
        return tuple(
            TimeSeriesPoint(
                symbol=f"{from_symbol}/{to_symbol}",
                date=_to_date(ts),
                open=_safe_float(row.get("1. open")) or 0.0,
                high=_safe_float(row.get("2. high")) or 0.0,
                low=_safe_float(row.get("3. low")) or 0.0,
                close=_safe_float(row.get("4. close")) or 0.0,
                volume=0,
            )
            for ts, row in sorted(series.items())
        )

    def get_digital_currency_daily(
        self, symbol: str, market: str = "USD"
    ) -> tuple[TimeSeriesPoint, ...]:
        """Return the daily digital-currency series quoted in ``market``."""
        params: dict[str, str] = {
            "function": AlphaVantageFunction.DIGITAL_CURRENCY_DAILY.value,
            "symbol": symbol,
            "market": market,
        }
        payload = self._request(params)
        series = _find_time_series(payload)
        points: list[TimeSeriesPoint] = []
        for ts, row in sorted(series.items()):
            points.append(
                TimeSeriesPoint(
                    symbol=symbol,
                    date=_to_date(ts),
                    open=_safe_float(row.get(f"1a. open ({market})"))
                    or _safe_float(row.get("1. open"))
                    or 0.0,
                    high=_safe_float(row.get(f"2a. high ({market})"))
                    or _safe_float(row.get("2. high"))
                    or 0.0,
                    low=_safe_float(row.get(f"3a. low ({market})"))
                    or _safe_float(row.get("3. low"))
                    or 0.0,
                    close=_safe_float(row.get(f"4a. close ({market})"))
                    or _safe_float(row.get("4. close"))
                    or 0.0,
                    volume=int(_safe_float(row.get("5. volume")) or 0),
                )
            )
        return tuple(points)

    def get_real_gdp(self, *, interval: str = "annual") -> EconomicSeries:
        """Return US real GDP (annual or quarterly)."""
        return self._economic_series(AlphaVantageFunction.REAL_GDP, {"interval": interval})

    def get_cpi(self, *, interval: str = "monthly") -> EconomicSeries:
        """Return the US Consumer Price Index."""
        return self._economic_series(AlphaVantageFunction.CPI, {"interval": interval})

    def get_inflation(self) -> EconomicSeries:
        """Return US annual inflation."""
        return self._economic_series(AlphaVantageFunction.INFLATION, {})

    def get_federal_funds_rate(self, *, interval: str = "monthly") -> EconomicSeries:
        """Return the US federal funds rate."""
        return self._economic_series(
            AlphaVantageFunction.FEDERAL_FUNDS_RATE, {"interval": interval}
        )

    def get_treasury_yield(
        self, *, interval: str = "monthly", maturity: str = "10year"
    ) -> EconomicSeries:
        """Return US Treasury yield for a maturity."""
        return self._economic_series(
            AlphaVantageFunction.TREASURY_YIELD, {"interval": interval, "maturity": maturity}
        )

    def get_unemployment(self) -> EconomicSeries:
        """Return the US unemployment rate."""
        return self._economic_series(AlphaVantageFunction.UNEMPLOYMENT, {})

    def get_retail_sales(self) -> EconomicSeries:
        """Return US advance retail sales."""
        return self._economic_series(AlphaVantageFunction.RETAIL_SALES, {})

    def get_nonfarm_payroll(self) -> EconomicSeries:
        """Return US total nonfarm payroll."""
        return self._economic_series(AlphaVantageFunction.NONFARM_PAYROLL, {})

    def clear_cache(self) -> int:
        return self.cache.clear()

    def _equity_series(
        self, function: AlphaVantageFunction, symbol: str, *, full: bool = False
    ) -> tuple[TimeSeriesPoint, ...]:
        params: dict[str, str] = {
            "function": function.value,
            "symbol": symbol,
            "outputsize": "full" if full else "compact",
        }
        payload = self._request(params)
        return self._parse_bars(symbol, payload)

    def _parse_bars(self, symbol: str, payload: dict[str, Any]) -> tuple[TimeSeriesPoint, ...]:
        series = _find_time_series(payload)
        return tuple(
            TimeSeriesPoint(
                symbol=symbol,
                date=_to_date(ts),
                open=_safe_float(row.get("1. open")) or 0.0,
                high=_safe_float(row.get("2. high")) or 0.0,
                low=_safe_float(row.get("3. low")) or 0.0,
                close=_safe_float(row.get("4. close")) or 0.0,
                volume=int(_safe_float(row.get("5. volume")) or 0),
            )
            for ts, row in sorted(series.items())
        )

    def _statements(self, function: AlphaVantageFunction, symbol: str) -> FinancialStatements:
        payload = self._request({"function": function.value, "symbol": symbol})
        annual = tuple(_parse_report(r) for r in payload.get("annualReports") or [])
        quarterly = tuple(_parse_report(r) for r in payload.get("quarterlyReports") or [])
        return FinancialStatements(
            symbol=symbol, function=function, annual=annual, quarterly=quarterly
        )

    def _economic_series(
        self, function: AlphaVantageFunction, extra: dict[str, str]
    ) -> EconomicSeries:
        params: dict[str, str] = {"function": function.value, **extra}
        payload = self._request(params)
        observations = tuple(
            EconomicIndicator(
                date=date.fromisoformat(str(row["date"])),
                value=_safe_float(row.get("value")),
            )
            for row in payload.get("data") or []
            if row.get("date")
        )
        return EconomicSeries(
            function=function,
            name=str(payload.get("name", function.value)),
            interval=str(payload.get("interval", "")),
            unit=str(payload.get("unit", "")),
            observations=observations,
        )


def _check_api_error(payload: dict[str, Any]) -> None:
    """Raise on Alpha Vantage's error / rate-limit envelopes (HTTP 200)."""
    if "Error Message" in payload:
        raise AlphaVantageClientError(str(payload["Error Message"]))
    if "Note" in payload:
        raise AlphaVantageClientError(f"Alpha Vantage rate limit: {payload['Note']}")
    if "Information" in payload:
        raise AlphaVantageClientError(f"Alpha Vantage rate limit: {payload['Information']}")


def market_cap_to_primitive_yaml(
    overview: CompanyOverview, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    if overview.market_cap_usd is None:
        raise ValueError(f"no market cap for {overview.symbol}")
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{overview.name} market capitalization (Alpha Vantage)",
        "description": f"Public-equity market capitalization of {overview.name}.",
        "value": overview.market_cap_usd,
        "unit": {
            "kind": "stock",
            "dimension": "currency",
            "currency": overview.currency or "USD",
        },
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": overview_to_source_yaml(overview, accessed=accessed),
    }


def economic_to_primitive_yaml(
    series: EconomicSeries,
    indicator: EconomicIndicator,
    *,
    slug: str,
    concept_slug: str,
    accessed: date,
    unit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one economic-indicator observation into a Strata primitive dict."""
    if indicator.value is None:
        raise ValueError(f"no value for {series.function.value} at {indicator.date}")
    payload = json.dumps(
        {
            "function": series.function.value,
            "date": indicator.date.isoformat(),
            "value": indicator.value,
        },
        sort_keys=True,
    )
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": series.name,
        "description": f"{series.name} ({series.unit}).",
        "value": indicator.value,
        "unit": unit or {"kind": "flow", "dimension": "scalar"},
        "as_of": indicator.date.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": {
            "slug": f"alpha-vantage-{series.function.value.lower()}-{indicator.date.isoformat()}",
            "tier": "aggregator",
            "url": f"https://www.alphavantage.co/query?function={series.function.value}",
            "accessed": accessed.isoformat(),
            "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        },
    }


def overview_to_source_yaml(overview: CompanyOverview, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {
            "symbol": overview.symbol,
            "name": overview.name,
            "market_cap": overview.market_cap_usd,
        },
        sort_keys=True,
    )
    return {
        "slug": f"alpha-vantage-{overview.symbol.lower()}-{accessed.isoformat()}",
        "tier": "aggregator",
        "url": f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={overview.symbol}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


_SYMBOL_ARG = CapabilityArg(
    name="symbol",
    type="str",
    description="Stock ticker symbol (e.g. AAPL, MSFT)",
    example="AAPL",
)


def _spec(method: str, description: str, returns: str, args: list[CapabilityArg]) -> CapabilitySpec:
    return CapabilitySpec(
        connector="alpha_vantage",
        method=method,
        description=description,
        returns=returns,
        args=args,
        source_tier="aggregator",
        is_fragile=True,
    )


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the router. All marked fragile (rate-limited free tier)."""
    return [
        _spec(
            "get_company_overview",
            "Public-equity fundamentals (market cap, P/E, sector, industry) for a "
            "ticker. Use for $-denominated company-size questions.",
            "atomic primitive, unit=currency USD, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_income_statement",
            "Annual + quarterly income-statement line items for a ticker.",
            "financial statements (line-item key/value), tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_balance_sheet",
            "Annual + quarterly balance-sheet line items for a ticker.",
            "financial statements (line-item key/value), tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_cash_flow",
            "Annual + quarterly cash-flow-statement line items for a ticker.",
            "financial statements (line-item key/value), tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_earnings",
            "Annual + quarterly reported EPS history for a ticker.",
            "earnings reports (reported EPS by period), tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_daily",
            "Daily OHLCV equity time series for a ticker.",
            "OHLCV time-series points, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_weekly",
            "Weekly OHLCV equity time series for a ticker.",
            "OHLCV time-series points, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_monthly",
            "Monthly OHLCV equity time series for a ticker.",
            "OHLCV time-series points, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_intraday",
            "Intraday OHLCV equity time series at a sampling interval.",
            "OHLCV time-series points, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_global_quote",
            "Latest price / change snapshot for a ticker.",
            "latest-price quote snapshot, tier=aggregator",
            [_SYMBOL_ARG],
        ),
        _spec(
            "get_currency_exchange_rate",
            "Realtime FX or crypto-to-fiat spot exchange rate for a pair.",
            "spot exchange rate, tier=aggregator",
            [
                CapabilityArg(
                    name="from_currency",
                    type="str",
                    description="ISO currency / crypto code to convert from",
                    example="EUR",
                ),
                CapabilityArg(
                    name="to_currency",
                    type="str",
                    description="ISO currency code to convert to",
                    example="USD",
                ),
            ],
        ),
        _spec(
            "get_fx_daily",
            "Daily FX OHLC time series for a currency pair.",
            "OHLC time-series points (volume 0), tier=aggregator",
            [
                CapabilityArg(
                    name="from_symbol",
                    type="str",
                    description="Base currency code",
                    example="EUR",
                ),
                CapabilityArg(
                    name="to_symbol",
                    type="str",
                    description="Quote currency code",
                    example="USD",
                ),
            ],
        ),
        _spec(
            "get_digital_currency_daily",
            "Daily crypto OHLCV time series quoted in a market currency.",
            "OHLCV time-series points, tier=aggregator",
            [
                CapabilityArg(
                    name="symbol",
                    type="str",
                    description="Crypto symbol (e.g. BTC, ETH)",
                    example="BTC",
                ),
            ],
        ),
        _spec(
            "get_real_gdp",
            "US real GDP (annual or quarterly).",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_cpi",
            "US Consumer Price Index series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_inflation",
            "US annual inflation-rate series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_federal_funds_rate",
            "US effective federal funds rate series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_treasury_yield",
            "US Treasury yield series for a maturity.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_unemployment",
            "US unemployment-rate series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_retail_sales",
            "US advance retail-sales series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
        _spec(
            "get_nonfarm_payroll",
            "US total nonfarm-payroll series.",
            "economic-indicator series, tier=aggregator",
            [],
        ),
    ]
