"""Kalshi prediction markets API v2 client.

Typed wrappers for Kalshi market/event endpoints with RSA-PSS authentication,
disk caching, and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://docs.kalshi.com
Auth: RSA-PSS SHA256 signing (private key + timestamp + method + path).
Source tier: prediction_market.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class KalshiMarketStatus(StrEnum):
    ACTIVE = "active"
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"
    FINALIZED = "finalized"


class KalshiMarketResult(StrEnum):
    YES = "yes"
    NO = "no"
    ALL_NO = "all_no"
    ALL_YES = "all_yes"


class KalshiEventCategory(StrEnum):
    """Common Kalshi event categories relevant to TAM research."""

    ECONOMICS = "Economics"
    FINANCIALS = "Financials"
    TECH = "Tech & Science"
    CLIMATE = "Climate & Weather"
    POLITICS = "Politics"
    CRYPTO = "Crypto"
    AI = "AI"
    COMPANIES = "Companies"
    TRANSPORTATION = "Transportation"
    HEALTH = "Health"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw Kalshi JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class MarketRaw(TypedDict, total=False):
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    yes_bid_dollars: str
    yes_ask_dollars: str
    no_bid_dollars: str
    no_ask_dollars: str
    last_price_dollars: str
    previous_price_dollars: str
    previous_yes_bid_dollars: str
    previous_yes_ask_dollars: str
    volume_fp: str
    volume_24h_fp: str
    open_interest_fp: str
    liquidity_dollars: str
    notional_value_dollars: str
    status: str
    result: str
    close_time: str
    expiration_time: str
    expected_expiration_time: str
    category: str
    market_type: str
    yes_sub_title: str
    no_sub_title: str
    open_time: str
    settlement_timer_seconds: int
    strike_type: NotRequired[str]
    cap_strike: NotRequired[float]
    floor_strike: NotRequired[float]


class EventRaw(TypedDict, total=False):
    event_ticker: str
    series_ticker: str
    title: str
    sub_title: str
    category: str
    markets: list[MarketRaw]
    mutually_exclusive: bool
    collateral_return_type: str


class TradeRaw(TypedDict, total=False):
    trade_id: str
    ticker: str
    count: int
    yes_price: int
    no_price: int
    created_time: str
    taker_side: str


class OrderbookEntryRaw(TypedDict):
    price: int
    quantity: int


class OrderbookRaw(TypedDict, total=False):
    ticker: str
    yes: list[OrderbookEntryRaw]
    no: list[OrderbookEntryRaw]


# ═══════════════════════════════════════════════════════════════════
# Frozen dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Market:
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    yes_bid: float
    yes_ask: float
    last_price: float
    volume: float
    volume_24h: float
    open_interest: float
    liquidity: float
    status: KalshiMarketStatus
    result: str | None
    close_time: datetime | None
    expiration_time: datetime | None
    category: str
    market_type: str = "binary"
    cap_strike: float | None = None
    floor_strike: float | None = None

    @property
    def midpoint(self) -> float:
        """Yes probability midpoint (0-1 scale). Prices are in dollars (0.00-1.00)."""
        if self.yes_bid > 0 and self.yes_ask > 0:
            return (self.yes_bid + self.yes_ask) / 2.0
        if self.last_price > 0:
            return self.last_price
        return 0.5

    @property
    def spread(self) -> float:
        """Bid-ask spread in dollars."""
        if self.yes_bid > 0.0 and self.yes_ask > 0.0:
            return self.yes_ask - self.yes_bid
        return 0.0

    @property
    def is_active(self) -> bool:
        return self.status in (KalshiMarketStatus.OPEN, KalshiMarketStatus.ACTIVE)


@dataclass(frozen=True, slots=True)
class Event:
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    category: str
    markets: tuple[Market, ...]
    mutually_exclusive: bool

    @property
    def total_volume(self) -> float:
        return sum(m.volume for m in self.markets)

    @property
    def total_open_interest(self) -> float:
        return sum(m.open_interest for m in self.markets)


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: str
    ticker: str
    count: int
    yes_price: int
    no_price: int
    created_time: datetime | None
    taker_side: str


@dataclass(frozen=True, slots=True)
class OrderbookLevel:
    price: int
    quantity: int


@dataclass(frozen=True, slots=True)
class Orderbook:
    ticker: str
    yes_levels: tuple[OrderbookLevel, ...]
    no_levels: tuple[OrderbookLevel, ...]

    @property
    def best_yes_bid(self) -> int | None:
        return self.yes_levels[0].price if self.yes_levels else None

    @property
    def best_yes_ask(self) -> int | None:
        return self.no_levels[0].price if self.no_levels else None


# ═══════════════════════════════════════════════════════════════════
# Response type
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class KalshiResponse:
    status: str
    response_time_ms: int
    markets: tuple[Market, ...] = ()
    events: tuple[Event, ...] = ()
    trades: tuple[Trade, ...] = ()
    orderbook: Orderbook | None = None
    cursor: str = ""
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Parsers
# ═══════════════════════════════════════════════════════════════════


def _parse_status(val: str) -> KalshiMarketStatus:
    try:
        return KalshiMarketStatus(val)
    except ValueError:
        return KalshiMarketStatus.OPEN


def _parse_ts(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float:
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


def _parse_market(raw: dict[str, Any]) -> Market:
    return Market(
        ticker=str(raw.get("ticker", "")),
        event_ticker=str(raw.get("event_ticker", "")),
        series_ticker=str(raw.get("series_ticker", "")),
        title=str(raw.get("title", "")),
        subtitle=str(raw.get("subtitle", raw.get("sub_title", raw.get("yes_sub_title", "")))),
        yes_bid=_safe_float(raw.get("yes_bid_dollars", raw.get("yes_bid", 0))),
        yes_ask=_safe_float(raw.get("yes_ask_dollars", raw.get("yes_ask", 0))),
        last_price=_safe_float(raw.get("last_price_dollars", raw.get("last_price", 0))),
        volume=_safe_float(raw.get("volume_fp", raw.get("volume", 0))),
        volume_24h=_safe_float(raw.get("volume_24h_fp", raw.get("volume_24h", 0))),
        open_interest=_safe_float(raw.get("open_interest_fp", raw.get("open_interest", 0))),
        liquidity=_safe_float(raw.get("liquidity_dollars", 0)),
        status=_parse_status(raw.get("status", "open")),
        result=raw.get("result") or None,
        close_time=_parse_ts(raw.get("close_time")),
        expiration_time=_parse_ts(raw.get("expiration_time")),
        category=str(raw.get("category", "")),
        market_type=str(raw.get("market_type", "binary")),
        cap_strike=raw.get("cap_strike"),
        floor_strike=raw.get("floor_strike"),
    )


def _parse_event(raw: dict[str, Any]) -> Event:
    markets_raw: list[dict[str, Any]] = raw.get("markets", [])
    return Event(
        event_ticker=str(raw.get("event_ticker", "")),
        series_ticker=str(raw.get("series_ticker", "")),
        title=str(raw.get("title", "")),
        subtitle=str(raw.get("sub_title", raw.get("subtitle", ""))),
        category=str(raw.get("category", "")),
        markets=tuple(_parse_market(m) for m in markets_raw),
        mutually_exclusive=bool(raw.get("mutually_exclusive", False)),
    )


def _parse_trade(raw: dict[str, Any]) -> Trade:
    return Trade(
        trade_id=str(raw.get("trade_id", "")),
        ticker=str(raw.get("ticker", "")),
        count=int(raw.get("count", 0)),
        yes_price=int(raw.get("yes_price", 0)),
        no_price=int(raw.get("no_price", 0)),
        created_time=_parse_ts(raw.get("created_time")),
        taker_side=str(raw.get("taker_side", "")),
    )


def _parse_orderbook(raw: dict[str, Any]) -> Orderbook:
    return Orderbook(
        ticker=str(raw.get("ticker", "")),
        yes_levels=tuple(
            OrderbookLevel(price=int(e.get("price", 0)), quantity=int(e.get("quantity", 0)))
            for e in raw.get("yes", [])
        ),
        no_levels=tuple(
            OrderbookLevel(price=int(e.get("price", 0)), quantity=int(e.get("quantity", 0)))
            for e in raw.get("no", [])
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


class _DiskCache:
    """JSON-on-disk cache keyed by request hash, with configurable TTL."""

    def __init__(self, directory: Path, ttl_seconds: int = 3600) -> None:
        self._dir = directory
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"kalshi_{key}.json"

    def get(self, params: str) -> tuple[dict[str, Any], float] | None:
        path = self._path(self._key(params))
        if not path.exists():
            return None
        try:
            raw: dict[str, Any] = json.loads(path.read_text())
            ts = float(raw.get("_ts", 0))
            age = time.time() - ts
            if age > self._ttl:
                path.unlink(missing_ok=True)
                return None
            data: dict[str, Any] = raw.get("_data", {})
            return data, age
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def put(self, params: str, data: dict[str, Any]) -> None:
        path = self._path(self._key(params))
        payload: dict[str, Any] = {"_ts": time.time(), "_data": data}
        path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> int:
        count = 0
        for f in self._dir.glob("kalshi_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# RSA-PSS Auth
# ═══════════════════════════════════════════════════════════════════


def _sign_request(
    private_key_pem: str,
    timestamp_ms: int,
    method: str,
    path: str,
) -> str:
    """Sign a Kalshi API request with RSA-PSS SHA256."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    path_without_query = path.split("?")[0]
    msg = f"{timestamp_ms}{method}{path_without_query}"

    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise KalshiClientError("Key must be RSA private key")

    import base64

    signature = private_key.sign(
        msg.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE_PROD = "https://external-api.kalshi.com/trade-api/v2"
_BASE_DEMO = "https://external-api.demo.kalshi.co/trade-api/v2"


class KalshiClientError(RuntimeError):
    """Raised on Kalshi API errors or client-side validation failures."""


class KalshiClient:
    """Typed client for Kalshi prediction markets API v2.

    Kalshi is a regulated prediction market where people bet real money on
    real-world outcomes. This connector pulls that data into Strata's data bank
    as atomic primitives, giving TAM models crowd-sourced probability estimates
    and conviction signals that no analyst report provides.

    How it fits into Strata's TAM engine::

        KALSHI.COM (people bet real money on outcomes)
                │
                ▼  KalshiClient fetches + caches
        ┌─ THIS CONNECTOR ─────────────────────────────┐
        │  RSA-signed auth → fetch markets/events       │
        │  → parse into typed Market dataclass          │
        │  → disk cache (don't re-hit API for 1 hour)   │
        └──────────────┬────────────────────────────────┘
                       │  market_to_primitive_yaml()
                       ▼
        ┌─ DATA BANK ──────────────────────────────────┐
        │  Two primitives per event:                    │
        │  • Probability (what the crowd thinks)        │
        │  • Volume (how sure they are / attention)     │
        │  Every number → source URL + sha256 pin       │
        └──────────────┬────────────────────────────────┘
                       │
                       ▼
        ┌─ TAM ENGINE ─────────────────────────────────┐
        │  Developer Tools TAM =                        │
        │    1.46M devs (BLS)                           │
        │    * 60.5% AI adoption (Kalshi)               │
        │    * $840/yr spend (EDGAR)                    │
        │    * (1 - 16.5% recession wt) (Kalshi)        │
        │  = $X billion with confidence range           │
        └──────────────────────────────────────────────┘

    Why prediction markets for TAM:
        - L3 (latent demand) needs adoption probability → Kalshi measures this directly
        - L4 (platform throughput) needs volume → crypto market prices signal DeFi TAM
        - All lenses need macro scenario weights → recession/growth/inflation probabilities
        - Tighter bid-ask spread = more liquid market = higher confidence in the number

    API endpoints used:
        GET /markets              — list/filter markets (paginated, cursor-based)
        GET /markets/{ticker}     — single market detail
        GET /markets/{ticker}/orderbook — bid/ask depth
        GET /markets/trades       — recent trade history
        GET /events               — event groups with nested markets
        GET /events/{ticker}      — single event with markets

    Authentication:
        RSA-PSS SHA256 signing. Each request signs: timestamp_ms + METHOD + path.
        Headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-TIMESTAMP, KALSHI-ACCESS-SIGNATURE.

    Usage::

        from strata.connectors import KalshiClient, market_to_primitive_yaml

        client = KalshiClient(
            api_key="your-key-id",
            private_key_path=Path("~/.kalshi/private_key.pem"),
        )

        # Fetch a TAM-relevant event
        resp = client.get_event("KXRECSSNBER-26")
        market = resp.events[0].markets[0]
        print(f"Recession probability: {market.midpoint:.1%}")  # 16.5%

        # Convert to Strata primitive for the data bank
        prim = market_to_primitive_yaml(
            market,
            concept_slug="us-economic-cycle-2026",
            primitive_slug="kalshi-recession-2026-probability",
            name="Probability: US recession in 2026 (Kalshi NBER)",
            description="...",
        )

        # Also extract volume as a separate demand-signal primitive
        from strata.connectors import market_volume_to_primitive_yaml
        vol = market_volume_to_primitive_yaml(
            market,
            concept_slug="us-economic-cycle-2026",
            primitive_slug="kalshi-recession-2026-volume",
            name="Kalshi volume: US recession 2026",
            description="...",
        )

    Key TAM-relevant event tickers:
        KXRECSSNBER-26          — Recession probability (macro gate)
        KXLAYOFFSYINFO-26       — Tech layoffs (labor TAM)
        KXRATECUTCOUNT-26DEC31  — Fed rate cuts (discount rate)
        KXIPOOPENAI             — OpenAI IPO timing (AI capital formation)
        KXLLM1-26DEC31          — Best AI model (competitive dynamics)
        KXCODINGMODEL-26DEC     — Best coding AI (developer tools TAM)
        KXBTCY-27JAN0100        — Bitcoin year-end (crypto TAM)
        KXETHY-27JAN0100        — Ethereum year-end (DeFi TAM)
        KXAGICO-COMP            — AGI timeline (automation ceiling)
        TESLAOPTIMUS-26DEC31    — Optimus release (robotics TAM timing)
    """

    def __init__(
        self,
        api_key: str | None = None,
        private_key_path: Path | None = None,
        private_key_pem: str | None = None,
        *,
        demo: bool = False,
        cache_dir: Path | None = None,
        cache_ttl: int = 3600,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base = _BASE_DEMO if demo else _BASE_PROD

        if private_key_pem:
            self._private_key = private_key_pem
        elif private_key_path:
            resolved = private_key_path.expanduser()
            if not resolved.exists():
                raise KalshiClientError(f"Private key not found: {resolved}")
            self._private_key = resolved.read_text()
        else:
            self._private_key = None

        self._http = httpx.Client(
            timeout=timeout,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        default_cache = Path.home() / ".strata" / "cache" / "kalshi"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> KalshiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _auth_headers(self, method: str, path: str) -> dict[str, str]:
        if not self._api_key or not self._private_key:
            return {}
        ts = int(time.time() * 1000)
        sig = _sign_request(self._private_key, ts, method, path)
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-TIMESTAMP": str(ts),
            "KALSHI-ACCESS-SIGNATURE": sig,
        }

    def _cache_key(self, method: str, path: str, params: dict[str, Any] | None) -> str:
        parts = [method, path]
        if params:
            parts.append(json.dumps(params, sort_keys=True))
        return "|".join(parts)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ck = self._cache_key(method, path, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, _age = cached
            data["_cached"] = True
            data["_cache_age"] = _age
            return data

        url = f"{self._base}{path}"
        headers = self._auth_headers(method, path)
        t0 = time.monotonic()

        if method == "GET":
            resp = self._http.get(url, params=params, headers=headers)
        else:
            resp = self._http.post(url, json=params, headers=headers)

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 401:
            raise KalshiClientError("Authentication failed — check API key and private key")
        if resp.status_code == 429:
            raise KalshiClientError("Rate limited — back off and retry")
        resp.raise_for_status()

        data: dict[str, Any] = resp.json()
        data["_elapsed_ms"] = elapsed_ms
        self._cache.put(ck, data)
        return data

    # ── Markets ──────────────────────────────────────────────────

    def get_markets(
        self,
        *,
        limit: int = 200,
        cursor: str | None = None,
        event_ticker: str | None = None,
        series_ticker: str | None = None,
        status: str | None = None,
        tickers: list[str] | None = None,
    ) -> KalshiResponse:
        """List markets with optional filters."""
        params: dict[str, Any] = {"limit": min(limit, 1000)}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if tickers:
            params["tickers"] = ",".join(tickers)

        data = self._request("GET", "/markets", params)
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        markets_raw: list[dict[str, Any]] = data.get("markets", [])
        markets = tuple(_parse_market(m) for m in markets_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            markets=markets,
            cursor=str(data.get("cursor", "")),
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    def get_market(self, ticker: str) -> KalshiResponse:
        """Get a single market by ticker."""
        data = self._request("GET", f"/markets/{ticker}")
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        market_raw: dict[str, Any] = data.get("market", data)
        market = _parse_market(market_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            markets=(market,),
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    def get_markets_all(
        self,
        *,
        status: str | None = None,
        event_ticker: str | None = None,
        series_ticker: str | None = None,
        max_pages: int = 10,
    ) -> KalshiResponse:
        """Auto-paginate through all markets matching filters."""
        all_markets: list[Market] = []
        cursor: str | None = None
        total_ms = 0

        for _ in range(max_pages):
            resp = self.get_markets(
                limit=1000,
                cursor=cursor,
                status=status,
                event_ticker=event_ticker,
                series_ticker=series_ticker,
            )
            all_markets.extend(resp.markets)
            total_ms += resp.response_time_ms
            if not resp.cursor:
                break
            cursor = resp.cursor

        return KalshiResponse(
            status="ok",
            response_time_ms=total_ms,
            markets=tuple(all_markets),
        )

    # ── Events ───────────────────────────────────────────────────

    def get_events(
        self,
        *,
        limit: int = 200,
        cursor: str | None = None,
        status: str | None = None,
        series_ticker: str | None = None,
        with_nested_markets: bool = True,
    ) -> KalshiResponse:
        """List events with optional filters."""
        params: dict[str, Any] = {"limit": min(limit, 200)}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if with_nested_markets:
            params["with_nested_markets"] = "true"

        data = self._request("GET", "/events", params)
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        events_raw: list[dict[str, Any]] = data.get("events", [])
        events = tuple(_parse_event(e) for e in events_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            events=events,
            cursor=str(data.get("cursor", "")),
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    def get_event(self, event_ticker: str, *, with_nested_markets: bool = True) -> KalshiResponse:
        """Get a single event by ticker."""
        params: dict[str, Any] = {}
        if with_nested_markets:
            params["with_nested_markets"] = "true"

        data = self._request("GET", f"/events/{event_ticker}", params or None)
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        event_raw: dict[str, Any] = data.get("event", data)
        event = _parse_event(event_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            events=(event,),
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    # ── Trades ───────────────────────────────────────────────────

    def get_trades(
        self,
        *,
        ticker: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> KalshiResponse:
        """Get recent trades, optionally filtered by market ticker."""
        params: dict[str, Any] = {"limit": min(limit, 1000)}
        if ticker:
            params["ticker"] = ticker
        if cursor:
            params["cursor"] = cursor

        data = self._request("GET", "/markets/trades", params)
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        trades_raw: list[dict[str, Any]] = data.get("trades", [])
        trades = tuple(_parse_trade(t) for t in trades_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            trades=trades,
            cursor=str(data.get("cursor", "")),
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    # ── Orderbook ────────────────────────────────────────────────

    def get_orderbook(self, ticker: str) -> KalshiResponse:
        """Get the orderbook for a market."""
        data = self._request("GET", f"/markets/{ticker}/orderbook")
        cached = bool(data.get("_cached", False))
        cache_age = float(data.get("_cache_age", 0.0))
        elapsed = int(data.get("_elapsed_ms", 0))

        ob_raw: dict[str, Any] = data.get("orderbook", data)
        ob_raw["ticker"] = ticker
        orderbook = _parse_orderbook(ob_raw)

        return KalshiResponse(
            status="ok",
            response_time_ms=elapsed,
            orderbook=orderbook,
            cached=cached,
            cache_age_seconds=round(cache_age, 1) if cached else 0.0,
        )

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached Kalshi responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _slugify_ticker(ticker: str) -> str:
    """Sanitize a Kalshi ticker into a valid slug component (lowercase alphanum + hyphens)."""
    import re

    slug = ticker.lower().replace(".", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _market_snapshot_hash(market: Market) -> str:
    """Content-hash a market state for source pinning."""
    content = json.dumps(
        {
            "ticker": market.ticker,
            "last_price": str(market.last_price),
            "yes_bid": str(market.yes_bid),
            "yes_ask": str(market.yes_ask),
            "volume": str(market.volume),
            "open_interest": str(market.open_interest),
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def market_to_primitive_yaml(
    market: Market,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    unit_kind: str = "dimensionless",
    unit_dimension: str = "percent",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "demand",
) -> dict[str, Any]:
    """Convert a Kalshi Market to a Strata AtomicPrimitive YAML dict.

    Emits a prediction_market tier primitive where the value is the
    midpoint probability (0-1) and uncertainty.range is [yes_bid, yes_ask]
    scaled to 0-1.
    """
    sha = _market_snapshot_hash(market)
    source_slug = f"kalshi-{_slugify_ticker(market.ticker)}-{date.today().isoformat()}"
    source_url = f"https://kalshi.com/markets/{market.ticker}"

    low = market.yes_bid if market.yes_bid > 0 else 0.0
    high = market.yes_ask if market.yes_ask > 0 else 1.0

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": round(market.midpoint, 4),
        "unit": {"kind": unit_kind, "dimension": unit_dimension},
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": "uniform",
        "delivery_mode": "n/a",
        "uncertainty": {
            "range": [round(low, 4), round(high, 4)],
            "basis": f"Kalshi bid-ask spread ({market.ticker})",
        },
        "source": {
            "slug": source_slug,
            "tier": "prediction_market",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def market_volume_to_primitive_yaml(
    market: Market,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "demand",
) -> dict[str, Any]:
    """Convert a Kalshi Market's volume/OI to a demand-signal primitive.

    Separate from the probability primitive — this captures market
    attention/conviction as a standalone number.
    """
    sha = _market_snapshot_hash(market)
    source_slug = f"kalshi-vol-{_slugify_ticker(market.ticker)}-{date.today().isoformat()}"
    source_url = f"https://kalshi.com/markets/{market.ticker}"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": float(market.volume),
        "unit": {"kind": "flow", "dimension": "transactions"},
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": {
            "slug": source_slug,
            "tier": "prediction_market",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def market_to_source_yaml(
    market: Market,
    *,
    description: str = "",
) -> dict[str, Any]:
    """Convert a Kalshi Market to a Strata source_registry YAML dict."""
    sha = _market_snapshot_hash(market)
    source_slug = f"kalshi-{_slugify_ticker(market.ticker)}-{date.today().isoformat()}"
    source_url = f"https://kalshi.com/markets/{market.ticker}"

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "prediction_market",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description or f"Kalshi market {market.ticker}: {market.title}",
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="kalshi",
            method="get_market",
            description=("Kalshi prediction-market mid-price / volume for an event contract."),
            returns="atomic primitive, unit=probability percent, tier=prediction_market",
            args=[
                CapabilityArg(
                    name="ticker",
                    type="str",
                    description="Kalshi market ticker",
                    example="NASDAQ100-24DEC31",
                ),
            ],
            source_tier="prediction_market",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
