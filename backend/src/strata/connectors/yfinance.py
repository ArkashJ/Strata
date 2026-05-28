"""yfinance connector — unofficial Yahoo Finance scraper.

Marked ``is_fragile=True`` on every capability — the router prefers
EDGAR / FRED over it. Use only when no regulator-tier source covers
the question (e.g. quotes for foreign-listed equities not in EDGAR).

We hit Yahoo's chart endpoint directly with ``httpx`` to keep
dependencies thin (no ``yfinance`` package needed; the package is a
wrapper around the same JSON endpoints).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from ._capability import CapabilityArg, CapabilitySpec


@dataclass(frozen=True, slots=True)
class YahooQuote:
    symbol: str
    price: float
    currency: str
    market_cap: float | None
    shares_outstanding: int | None
    short_name: str
    exchange: str
    quote_as_of: datetime


@dataclass(frozen=True, slots=True)
class YahooResponse:
    quote: YahooQuote


class _DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 3600) -> None:
        self.directory = directory
        self.ttl = ttl_seconds
        directory.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def get(self, params: str) -> dict[str, Any] | None:
        path = self.directory / f"{self._key(params)}.json"
        if not path.exists() or time.time() - path.stat().st_mtime > self.ttl:
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def put(self, params: str, data: dict[str, Any]) -> None:
        (self.directory / f"{self._key(params)}.json").write_text(json.dumps(data))

    def clear(self) -> int:
        count = 0
        for p in self.directory.glob("*.json"):
            p.unlink()
            count += 1
        return count


class YFinanceClientError(RuntimeError):
    pass


class YFinanceClient:
    """Yahoo Finance unofficial JSON endpoint client."""

    BASE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
    USER_AGENT = "Mozilla/5.0 (Strata; +https://github.com/anthropics/strata)"

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "yfinance")
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": self.USER_AGENT})

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> YFinanceClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get_quote(self, symbol: str) -> YahooQuote:
        """Single-symbol spot quote + market cap + shares outstanding."""
        cache_key = json.dumps({"symbol": symbol}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            raw = cached
        else:
            try:
                resp = self._client.get(self.BASE_URL, params={"symbols": symbol})
                resp.raise_for_status()
                raw = resp.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                raise YFinanceClientError(f"Yahoo quote request failed: {exc}") from exc
            self.cache.put(cache_key, raw)
        results: list[dict[str, Any]] = list(raw.get("quoteResponse", {}).get("result", []))
        if not results:
            raise YFinanceClientError(f"No quote for {symbol!r}")
        q = results[0]
        try:
            price = float(q["regularMarketPrice"])
        except (KeyError, TypeError, ValueError) as exc:
            raise YFinanceClientError(f"Quote for {symbol!r} missing price") from exc
        return YahooQuote(
            symbol=str(q.get("symbol", symbol)),
            price=price,
            currency=str(q.get("currency", "USD")),
            market_cap=float(q["marketCap"]) if q.get("marketCap") is not None else None,
            shares_outstanding=int(q["sharesOutstanding"])
            if q.get("sharesOutstanding") is not None
            else None,
            short_name=str(q.get("shortName", "")),
            exchange=str(q.get("fullExchangeName", q.get("exchange", ""))),
            quote_as_of=datetime.fromtimestamp(
                int(q.get("regularMarketTime", time.time())), tz=UTC
            ),
        )

    def clear_cache(self) -> int:
        return self.cache.clear()


def quote_to_primitive_yaml(
    quote: YahooQuote, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    if quote.market_cap is None:
        raise ValueError(f"no market_cap for {quote.symbol}")
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{quote.short_name} market cap (Yahoo Finance)",
        "description": f"Yahoo Finance market capitalization of {quote.symbol}.",
        "value": quote.market_cap,
        "unit": {
            "kind": "stock",
            "dimension": "currency",
            "currency": quote.currency,
        },
        "as_of": quote.quote_as_of.date().isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": quote_to_source_yaml(quote, accessed=accessed),
    }


def quote_to_source_yaml(quote: YahooQuote, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {
            "symbol": quote.symbol,
            "price": quote.price,
            "market_cap": quote.market_cap,
            "as_of": quote.quote_as_of.isoformat(),
        },
        sort_keys=True,
    )
    return {
        "slug": f"yfinance-{quote.symbol.lower()}-{accessed.isoformat()}",
        "tier": "analyst",
        "url": f"https://finance.yahoo.com/quote/{quote.symbol}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="yfinance",
            method="get_quote",
            description=(
                "Yahoo Finance spot quote, market cap, shares outstanding for "
                "a ticker. Fragile scraper — prefer EDGAR/FRED when available."
            ),
            returns="atomic primitive, unit=currency, tier=analyst",
            args=[
                CapabilityArg(
                    name="symbol",
                    type="str",
                    description="Ticker symbol (e.g. AAPL, TSM)",
                    example="AAPL",
                ),
            ],
            source_tier="analyst",
            is_fragile=True,
        ),
    ]
