"""Dune Analytics API v1 client.

Typed wrappers for Dune's async query-execution model (execute → poll status →
fetch results) with disk caching and conversion to Strata AtomicPrimitive /
Source YAML format.

API reference: https://docs.dune.com/api-reference/
Base URL: https://api.dune.com/api/v1
Auth: header ``X-Dune-API-Key: <key>`` (read from ``STRATA_DUNE_API_KEY``).
Source tier: onchain (Dune surfaces on-chain analytics).

Dune is on-chain analytics: anyone can write SQL over decoded blockchain data
(DEX trades, stablecoin transfers, NFT sales, lending, wallet activity) and Dune
materializes the result. This connector pulls those query results into Strata's
data bank as atomic primitives, giving TAM models crypto-native volume / revenue
/ active-user numbers that no analyst report provides::

    DUNE.COM (SQL over decoded on-chain data)
            │
            ▼  DuneClient executes + polls + fetches
    ┌─ THIS CONNECTOR ──────────────────────────────┐
    │  X-Dune-API-Key auth → execute query          │
    │  → poll execution status until COMPLETED      │
    │  → fetch result rows + column metadata         │
    │  → disk cache (don't re-execute for 1 hour)    │
    └──────────────┬─────────────────────────────────┘
                   │  run_query_result_to_primitive_yaml()
                   ▼
    ┌─ DATA BANK ───────────────────────────────────┐
    │  e.g. monthly DEX volume_usd per chain         │
    │  Every number → source URL + sha256 pin        │
    └────────────────────────────────────────────────┘

Why on-chain data for TAM:
    - L4 (platform throughput) needs volume × take_rate → dex.trades volume
    - Stablecoin transfer volume → remittance / payments TAM
    - Active wallet counts → total addressable users for crypto products
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

import httpx

from strata.config import settings

if TYPE_CHECKING:
    from ._capability import CapabilitySpec

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class ExecutionState(StrEnum):
    """Lifecycle states of a Dune query execution."""

    PENDING = "QUERY_STATE_PENDING"
    EXECUTING = "QUERY_STATE_EXECUTING"
    COMPLETED = "QUERY_STATE_COMPLETED"
    FAILED = "QUERY_STATE_FAILED"
    CANCELLED = "QUERY_STATE_CANCELLED"
    EXPIRED = "QUERY_STATE_EXPIRED"


class QueryPerformance(StrEnum):
    """Execution engine tier (affects credit cost and speed)."""

    MEDIUM = "medium"
    LARGE = "large"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw Dune JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class ExecuteRaw(TypedDict, total=False):
    execution_id: str
    state: str


class ResultMetadataRaw(TypedDict, total=False):
    column_names: list[str]
    column_types: list[str]
    row_count: int
    total_row_count: int
    result_set_bytes: int
    datapoint_count: int


class ResultPayloadRaw(TypedDict, total=False):
    rows: list[dict[str, Any]]
    metadata: ResultMetadataRaw


class StatusRaw(TypedDict, total=False):
    execution_id: str
    query_id: int
    state: str
    submitted_at: str
    execution_started_at: str
    execution_ended_at: str
    result_metadata: ResultMetadataRaw


class ResultsRaw(TypedDict, total=False):
    execution_id: str
    query_id: int
    state: str
    result: ResultPayloadRaw
    next_offset: NotRequired[int]
    next_uri: NotRequired[str]


# ═══════════════════════════════════════════════════════════════════
# Frozen dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    """Returned by ``execute_query`` — identifies a running execution."""

    execution_id: str
    state: ExecutionState


@dataclass(frozen=True, slots=True)
class ExecutionStatus:
    """State of an in-flight or finished execution."""

    execution_id: str
    state: ExecutionState
    row_count: int = 0
    total_row_count: int = 0

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.EXPIRED,
        )

    @property
    def is_complete(self) -> bool:
        return self.state == ExecutionState.COMPLETED


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Result rows plus column metadata for a query execution."""

    execution_id: str
    state: ExecutionState
    rows: tuple[dict[str, Any], ...]
    column_names: tuple[str, ...]
    row_count: int
    query_id: int | None = None
    cached: bool = False
    cache_age_seconds: float = 0.0

    def column(self, name: str) -> tuple[Any, ...]:
        """Extract a single column's values across all rows."""
        return tuple(row.get(name) for row in self.rows)


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_state(val: str | None) -> ExecutionState:
    try:
        return ExecutionState(str(val))
    except ValueError:
        return ExecutionState.PENDING


def _parse_execute(raw: dict[str, Any]) -> ExecutionHandle:
    return ExecutionHandle(
        execution_id=str(raw.get("execution_id", "")),
        state=_parse_state(raw.get("state")),
    )


def _parse_status(raw: dict[str, Any]) -> ExecutionStatus:
    meta: dict[str, Any] = raw.get("result_metadata") or {}
    return ExecutionStatus(
        execution_id=str(raw.get("execution_id", "")),
        state=_parse_state(raw.get("state")),
        row_count=int(meta.get("row_count", 0) or 0),
        total_row_count=int(meta.get("total_row_count", 0) or 0),
    )


def _parse_results(raw: dict[str, Any], *, query_id: int | None = None) -> QueryResult:
    payload: dict[str, Any] = raw.get("result") or {}
    meta: dict[str, Any] = payload.get("metadata") or {}
    rows_raw: list[dict[str, Any]] = payload.get("rows") or []
    rows = tuple(dict(r) for r in rows_raw)

    columns_raw = meta.get("column_names")
    if columns_raw:
        column_names = tuple(str(c) for c in columns_raw)
    elif rows:
        column_names = tuple(rows[0].keys())
    else:
        column_names = ()

    row_count = int(meta.get("row_count", len(rows)) or len(rows))

    return QueryResult(
        execution_id=str(raw.get("execution_id", "")),
        state=_parse_state(raw.get("state")),
        rows=rows,
        column_names=column_names,
        row_count=row_count,
        query_id=query_id,
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
        return self._dir / f"dune_{key}.json"

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
        for f in self._dir.glob("dune_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.dune.com/api/v1"


class DuneClientError(RuntimeError):
    """Raised on Dune API errors or client-side validation failures."""


class DuneClient:
    """Typed client for the Dune Analytics API v1 with disk caching.

    Dune's execution model is asynchronous: you trigger an execution, poll its
    status until it reaches ``COMPLETED``, then fetch the result rows. The
    ``run_query`` convenience method wraps all three steps.

    Usage::

        client = DuneClient(api_key="your-key")              # or STRATA_DUNE_API_KEY env
        result = client.run_query(649046, poll_interval=2.0)
        for row in result.rows:
            print(row["volume_usd"], row["chain"])

        prim = run_query_result_to_primitive_yaml(
            result,
            query_id=649046,
            column="volume_usd",
            concept_slug="dex-volume",
            primitive_slug="dune-dex-volume-eth",
            name="Monthly DEX volume (Ethereum)",
            description="Sum of dex.trades amount_usd.",
        )

    API endpoints used:
        POST /query/{query_id}/execute         — trigger an execution
        GET  /execution/{execution_id}/status  — poll execution state
        GET  /execution/{execution_id}/results — fetch result rows
        GET  /query/{query_id}/results         — latest cached results for a query
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 3600,
        timeout: float = 60.0,
    ) -> None:
        self._key = api_key or settings.dune_api_key
        self._http = httpx.Client(
            timeout=timeout,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        default_cache = Path.home() / ".strata" / "cache" / "dune"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> DuneClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {"X-Dune-API-Key": self._key} if self._key else {}

    def _cache_key(self, method: str, path: str, params: dict[str, Any] | None) -> str:
        parts = [method, path]
        if params:
            parts.append(json.dumps(params, sort_keys=True))
        return "|".join(parts)

    def _raise_for_error(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        message = f"HTTP {resp.status_code}"
        try:
            body: dict[str, Any] = resp.json()
            if body.get("error"):
                message = str(body["error"])
        except (ValueError, json.JSONDecodeError):
            message = resp.text or message
        if resp.status_code == 401:
            raise DuneClientError(f"Authentication failed — check STRATA_DUNE_API_KEY: {message}")
        if resp.status_code == 402:
            raise DuneClientError(f"Over plan limit: {message}")
        if resp.status_code == 404:
            raise DuneClientError(f"Not found: {message}")
        raise DuneClientError(message)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        use_cache: bool = False,
    ) -> dict[str, Any]:
        if use_cache:
            ck = self._cache_key(method, path, params)
            cached = self._cache.get(ck)
            if cached is not None:
                data, age = cached
                data["_cached"] = True
                data["_cache_age"] = age
                return data

        url = f"{_BASE}{path}"
        headers = self._auth_headers()
        if method == "POST":
            resp = self._http.post(url, params=params, json=json_body, headers=headers)
        else:
            resp = self._http.get(url, params=params, headers=headers)

        self._raise_for_error(resp)
        data: dict[str, Any] = resp.json()

        if data.get("error"):
            raise DuneClientError(str(data["error"]))

        if use_cache:
            self._cache.put(self._cache_key(method, path, params), data)
        return data

    # ── Endpoint 1: execute a query ──────────────────────────────

    def execute_query(
        self,
        query_id: int,
        *,
        query_parameters: dict[str, Any] | None = None,
        performance: str | None = None,
    ) -> ExecutionHandle:
        """Trigger an asynchronous execution of a saved Dune query."""
        body: dict[str, Any] = {}
        if query_parameters:
            body["query_parameters"] = query_parameters
        if performance:
            body["performance"] = performance
        data = self._request("POST", f"/query/{query_id}/execute", json_body=body or None)
        return _parse_execute(data)

    # ── Endpoint 2: execution status ─────────────────────────────

    def get_status(self, execution_id: str) -> ExecutionStatus:
        """Poll the state of a running or finished execution."""
        data = self._request("GET", f"/execution/{execution_id}/status")
        return _parse_status(data)

    # ── Endpoint 3: execution results ────────────────────────────

    def get_results(
        self,
        execution_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        query_id: int | None = None,
    ) -> QueryResult:
        """Fetch result rows for a completed execution."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        data = self._request("GET", f"/execution/{execution_id}/results", params=params or None)
        return _parse_results(data, query_id=query_id)

    # ── Endpoint 4: latest cached results for a query ────────────

    def get_latest_result(
        self,
        query_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult:
        """Fetch the latest cached results for a query without re-executing."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        data = self._request(
            "GET", f"/query/{query_id}/results", params=params or None, use_cache=True
        )
        result = _parse_results(data, query_id=query_id)
        if data.get("_cached"):
            result = replace(
                result,
                cached=True,
                cache_age_seconds=round(float(data.get("_cache_age", 0.0)), 1),
            )
        return result

    # ── High-level convenience: execute → poll → fetch ───────────

    def run_query(
        self,
        query_id: int,
        *,
        query_parameters: dict[str, Any] | None = None,
        performance: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> QueryResult:
        """Execute a query, poll until COMPLETED, then return results.

        ``poll_interval`` and ``timeout`` are in seconds; set ``poll_interval=0``
        in tests to avoid sleeping. Raises ``DuneClientError`` on a FAILED /
        CANCELLED / EXPIRED state or if the timeout elapses before completion.
        """
        handle = self.execute_query(
            query_id, query_parameters=query_parameters, performance=performance
        )
        deadline = time.monotonic() + timeout
        while True:
            status = self.get_status(handle.execution_id)
            if status.is_complete:
                break
            if status.is_terminal:
                raise DuneClientError(
                    f"Execution {handle.execution_id} ended in state {status.state.value}"
                )
            if time.monotonic() >= deadline:
                raise DuneClientError(
                    f"Execution {handle.execution_id} timed out after {timeout}s "
                    f"(last state {status.state.value})"
                )
            if poll_interval > 0:
                time.sleep(poll_interval)

        return self.get_results(handle.execution_id, query_id=query_id)

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached Dune responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _result_snapshot_hash(result: QueryResult, query_id: int, column: str) -> str:
    """Content-hash the result payload for source pinning (Q5)."""
    content = json.dumps(
        {
            "query_id": query_id,
            "column": column,
            "column_names": list(result.column_names),
            "rows": result.rows,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _select_value(result: QueryResult, column: str, row_index: int) -> Any:
    """Pull one cell out of the result set, with clear errors."""
    if not result.rows:
        raise DuneClientError("Query result has no rows")
    if column not in result.column_names and column not in result.rows[0]:
        raise DuneClientError(f"Column {column!r} not in result columns {result.column_names}")
    try:
        return result.rows[row_index][column]
    except (IndexError, KeyError) as exc:
        raise DuneClientError(f"No value at row {row_index}, column {column!r}") from exc


def run_query_result_to_primitive_yaml(
    result: QueryResult,
    *,
    query_id: int,
    column: str,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    row_index: int = 0,
    geo_codes: tuple[str, ...] = ("WORLD",),
    geo_level: str = "global",
    geo_perspective: str = "supply",
    unit_kind: str = "flow",
    unit_dimension: str = "currency",
    unit_denominator: str | None = None,
    unit_currency: str | None = "USD",
    distribution_shape: str = "power_law",
    delivery_mode: str = "n/a",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Convert a Dune QueryResult cell to a Strata AtomicPrimitive YAML dict.

    Selects ``column`` from row ``row_index`` as the primitive value. Returns a
    dict ready for ``yaml.dump()`` conforming to the AtomicPrimitive schema.
    """
    raw_value = _select_value(result, column, row_index)
    try:
        value: float = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise DuneClientError(f"Value {raw_value!r} for column {column!r} is not numeric") from exc

    sha = _result_snapshot_hash(result, query_id, column)
    source_slug = f"dune-query-{query_id}-{date.today().isoformat()}"
    source_url = f"https://dune.com/queries/{query_id}"

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator
    if unit_currency:
        unit["currency"] = unit_currency

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": value,
        "unit": unit,
        "as_of": as_of or date.today().isoformat(),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": distribution_shape,
        "delivery_mode": delivery_mode,
        "source": {
            "slug": source_slug,
            "tier": "onchain",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def run_query_result_to_source_yaml(
    result: QueryResult,
    *,
    query_id: int,
    column: str,
    description: str = "",
) -> dict[str, Any]:
    """Convert a Dune QueryResult to a Strata source_registry YAML dict."""
    sha = _result_snapshot_hash(result, query_id, column)
    source_slug = f"dune-query-{query_id}-{date.today().isoformat()}"
    source_url = f"https://dune.com/queries/{query_id}"

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "onchain",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description or f"Dune query {query_id}, column {column}.",
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="dune",
            method="run_query",
            description=(
                "Dune Analytics on-chain SQL query result (DEX volume, stablecoin "
                "transfers, active wallets, protocol revenue)."
            ),
            returns="atomic primitive, unit varies (often currency USD), tier=onchain",
            args=[
                CapabilityArg(
                    name="query_id",
                    type="int",
                    description="Saved Dune query ID",
                    example="649046",
                ),
            ],
            source_tier="onchain",
            requires_paid_tier=True,
        ),
        CapabilitySpec(
            connector="dune",
            method="get_latest_result",
            description=(
                "Latest cached result rows for a saved Dune query, without "
                "triggering a fresh (credit-spending) execution."
            ),
            returns="atomic primitive, unit varies (often currency USD), tier=onchain",
            args=[
                CapabilityArg(
                    name="query_id",
                    type="int",
                    description="Saved Dune query ID",
                    example="649046",
                ),
            ],
            source_tier="onchain",
            requires_paid_tier=True,
        ),
    ]
