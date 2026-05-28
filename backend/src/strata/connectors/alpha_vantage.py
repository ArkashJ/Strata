"""Alpha Vantage connector — equities, FX, crypto, fundamentals.

Free tier: 25 requests/day. Heavy disk-cache + ingest-only by default;
the capability manifest carries ``is_fragile=True`` on rate-limited methods
so the query-time router will demote them unless explicitly asked.

API reference: https://www.alphavantage.co/documentation/
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

from ._capability import CapabilityArg, CapabilitySpec

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class AlphaVantageInterval(StrEnum):
    DAILY = "TIME_SERIES_DAILY"
    WEEKLY = "TIME_SERIES_WEEKLY"
    MONTHLY = "TIME_SERIES_MONTHLY"


class AlphaVantageFunction(StrEnum):
    OVERVIEW = "OVERVIEW"
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    EARNINGS = "EARNINGS"
    FX_DAILY = "FX_DAILY"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts (raw API shape)
# ═══════════════════════════════════════════════════════════════════


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
    Currency: str


class TimeSeriesEntryRaw(TypedDict, total=False):
    open: str
    high: str
    low: str
    close: str
    volume: str


# ═══════════════════════════════════════════════════════════════════
# Frozen dataclasses
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CompanyOverview:
    symbol: str
    name: str
    exchange: str
    sector: str | None
    industry: str | None
    market_cap_usd: float | None
    pe_ratio: float | None
    dividend_yield: float | None
    currency: str | None


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    symbol: str
    date: date
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class AlphaVantageResponse:
    items: tuple[CompanyOverview | TimeSeriesPoint, ...]
    total_count: int


# ═══════════════════════════════════════════════════════════════════
# Parsers
# ═══════════════════════════════════════════════════════════════════


def _safe_float(val: object) -> float | None:
    if val is None or val == "None" or val == "-" or val == "":
        return None
    try:
        return float(str(val))
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
        pe_ratio=_safe_float(raw.get("PERatio")),
        dividend_yield=_safe_float(raw.get("DividendYield")),
        currency=str(raw["Currency"]) if raw.get("Currency") else None,
    )


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


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
        path = self._path(self._key(params))
        path.write_text(json.dumps(data))

    def clear(self) -> int:
        count = 0
        for p in self.directory.glob("*.json"):
            p.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════


class AlphaVantageClientError(RuntimeError):
    pass


class AlphaVantageClient:
    """Alpha Vantage HTTP client.

    25 req/day free tier — every call is disk-cached for 24h.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise AlphaVantageClientError("Alpha Vantage API key required")
        self.api_key = api_key
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "alpha_vantage")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AlphaVantageClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
        signed_params = {**params, "apikey": self.api_key}
        cache_params = json.dumps({k: v for k, v in params.items()}, sort_keys=True)
        cached = self.cache.get(cache_params)
        if cached is not None:
            return cached[0]
        try:
            resp = self._client.get(self.BASE_URL, params=signed_params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AlphaVantageClientError(f"Alpha Vantage request failed: {exc}") from exc
        if "Error Message" in data:
            raise AlphaVantageClientError(str(data["Error Message"]))
        if "Note" in data and "frequency" in str(data["Note"]).lower():
            raise AlphaVantageClientError("Alpha Vantage rate limit exceeded")
        self.cache.put(cache_params, data)
        return data

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Return fundamentals (market cap, P/E, sector) for an equity."""
        raw = self._request({"function": "OVERVIEW", "symbol": symbol})
        if not raw or not raw.get("Symbol"):
            raise AlphaVantageClientError(f"No overview for {symbol!r}")
        return _parse_overview(raw)

    def clear_cache(self) -> int:
        return self.cache.clear()


# ═══════════════════════════════════════════════════════════════════
# YAML converters
# ═══════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════
# Capability manifest
# ═══════════════════════════════════════════════════════════════════


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the router. All marked fragile (rate-limited free tier)."""
    return [
        CapabilitySpec(
            connector="alpha_vantage",
            method="get_company_overview",
            description=(
                "Public-equity fundamentals (market cap, P/E, sector, industry) "
                "for a ticker symbol. Use for $-denominated company-size questions."
            ),
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="symbol",
                    type="str",
                    description="Stock ticker symbol (e.g. AAPL, MSFT)",
                    example="AAPL",
                ),
            ],
            source_tier="aggregator",
            is_fragile=True,
        ),
    ]
