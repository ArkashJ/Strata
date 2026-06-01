"""Nasdaq Data Link (formerly Quandl) connector — economic / financial series.

Typed wrappers for the two core Nasdaq Data Link API v3 shapes — time-series
datasets and datatables — with disk caching and conversion to Strata
AtomicPrimitive / Source YAML.

Free datasets work without (or with a free) key (LBMA/GOLD, USTREASURY/YIELD,
FRED mirrors); premium datasets and most datatables require a paid key, so the
datatable capability is gated behind ``requires_paid_tier=True``.

API reference: https://docs.data.nasdaq.com/
Base URL: https://data.nasdaq.com/api/v3
Errors come back as ``{"quandl_error": {"code", "message"}}`` (sometimes with
a non-200 status); both are surfaced as :class:`NasdaqDataLinkClientError`.
Source tier: ``aggregator``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from strata.config import settings

from ._capability import CapabilityArg, CapabilitySpec

_BASE = "https://data.nasdaq.com/api/v3"


class NasdaqTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class NasdaqOrder(StrEnum):
    """Row sort order for time-series dataset requests."""

    ASC = "asc"
    DESC = "desc"


class NasdaqCollapse(StrEnum):
    """Frequency-collapse codes for time-series dataset requests."""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class NasdaqTransform(StrEnum):
    """Value-transformation codes for time-series dataset requests."""

    NONE = "none"
    DIFF = "diff"
    RDIFF = "rdiff"
    CUMUL = "cumul"
    NORMALIZE = "normalize"


@dataclass(frozen=True, slots=True)
class NasdaqObservation:
    """One time-series observation: a date plus the parsed numeric columns."""

    dataset_code: str
    series_date: date
    values: tuple[float | None, ...]

    @property
    def value(self) -> float | None:
        """Convenience accessor for the first numeric column."""
        return self.values[0] if self.values else None


@dataclass(frozen=True, slots=True)
class NasdaqDatasetMeta:
    """Metadata describing a time-series dataset."""

    database_code: str
    dataset_code: str
    name: str
    description: str
    frequency: str
    newest_available_date: str
    oldest_available_date: str
    refreshed_at: str | None
    column_names: tuple[str, ...]
    premium: bool = False


@dataclass(frozen=True, slots=True)
class NasdaqDatatableColumn:
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class NasdaqDatatable:
    """A datatable page: columns, rows, and a pagination cursor."""

    datatable_code: str
    columns: tuple[NasdaqDatatableColumn, ...]
    rows: tuple[tuple[Any, ...], ...]
    next_cursor_id: str | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor_id is not None


@dataclass(frozen=True, slots=True)
class NasdaqResponse:
    """Unified time-series response: observations + dataset metadata."""

    database_code: str
    dataset_code: str
    column_names: tuple[str, ...]
    observations: tuple[NasdaqObservation, ...]
    meta: NasdaqDatasetMeta | None

    def latest(self, column_index: int = 0) -> NasdaqObservation:
        """Return the most recent observation carrying a value in ``column_index``."""
        ordered = self.observations if self._is_desc() else tuple(reversed(self.observations))
        for obs in ordered:
            if column_index < len(obs.values) and obs.values[column_index] is not None:
                return obs
        raise NasdaqDataLinkClientError(f"No observation has a value in column {column_index}")

    def _is_desc(self) -> bool:
        if len(self.observations) < 2:
            return False
        return self.observations[0].series_date >= self.observations[-1].series_date


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_observations(
    dataset_code: str, raw: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[NasdaqObservation, ...]]:
    column_names = tuple(str(c) for c in raw.get("column_names", []))
    observations: list[NasdaqObservation] = []
    for entry in raw.get("data", []):
        if not isinstance(entry, list) or not entry:
            continue
        cells: list[Any] = entry
        try:
            d = date.fromisoformat(str(cells[0]))
        except ValueError:
            continue
        values = tuple(_safe_float(cell) for cell in cells[1:])
        observations.append(
            NasdaqObservation(dataset_code=dataset_code, series_date=d, values=values)
        )
    return column_names, tuple(observations)


def _parse_meta(raw: dict[str, Any]) -> NasdaqDatasetMeta:
    return NasdaqDatasetMeta(
        database_code=str(raw.get("database_code", "")),
        dataset_code=str(raw.get("dataset_code", "")),
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        frequency=str(raw.get("frequency", "")),
        newest_available_date=str(raw.get("newest_available_date", "")),
        oldest_available_date=str(raw.get("oldest_available_date", "")),
        refreshed_at=str(raw["refreshed_at"]) if raw.get("refreshed_at") else None,
        column_names=tuple(str(c) for c in raw.get("column_names", [])),
        premium=bool(raw.get("premium", False)),
    )


def _parse_datatable(
    datatable_code: str, raw: dict[str, Any], cursor: str | None
) -> NasdaqDatatable:
    cols_raw: list[dict[str, Any]] = raw.get("columns", [])
    columns = tuple(
        NasdaqDatatableColumn(name=str(c.get("name", "")), type=str(c.get("type", "")))
        for c in cols_raw
    )
    rows: tuple[tuple[Any, ...], ...] = tuple(
        tuple(r) for r in raw.get("data", []) if isinstance(r, list)
    )
    return NasdaqDatatable(
        datatable_code=datatable_code,
        columns=columns,
        rows=rows,
        next_cursor_id=cursor,
    )


class _DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
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


class NasdaqDataLinkClientError(RuntimeError):
    pass


class NasdaqDataLinkClient:
    """Nasdaq Data Link HTTP client. All requests cached on disk for 24h."""

    BASE_URL = _BASE

    def __init__(
        self,
        api_key: str | None = None,
        *,
        tier: NasdaqTier = NasdaqTier.FREE,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or settings.nasdaq_data_link_api_key
        self.tier = tier
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "nasdaq_data_link")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NasdaqDataLinkClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        signed = dict(params)
        if self.api_key:
            signed["api_key"] = self.api_key
        cache_key = json.dumps({"path": path, "params": params}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        resp = self._client.get(f"{self.BASE_URL}/{path}", params=signed)
        try:
            data: dict[str, Any] = resp.json()
        except (json.JSONDecodeError, ValueError):
            data = {}
        if "quandl_error" in data:
            err: dict[str, Any] = data["quandl_error"]
            code = err.get("code", "unknown")
            msg = err.get("message", "Unknown Nasdaq Data Link API error")
            raise NasdaqDataLinkClientError(f"Nasdaq Data Link error {code}: {msg}")
        if resp.status_code >= 400:
            raise NasdaqDataLinkClientError(
                f"Nasdaq Data Link HTTP {resp.status_code} for {path!r}"
            )
        self.cache.put(cache_key, data)
        return data

    def get_dataset(
        self,
        database_code: str,
        dataset_code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        order: NasdaqOrder = NasdaqOrder.ASC,
        collapse: NasdaqCollapse = NasdaqCollapse.NONE,
        transform: NasdaqTransform = NasdaqTransform.NONE,
    ) -> NasdaqResponse:
        """Fetch time-series observations for a dataset.

        Args:
            database_code: Database code (e.g. "LBMA", "USTREASURY").
            dataset_code: Dataset code within the database (e.g. "GOLD").
            start_date / end_date: Inclusive date bounds "YYYY-MM-DD".
            limit: Max rows to return.
            order: Row sort order (NasdaqOrder).
            collapse: Frequency collapse (NasdaqCollapse).
            transform: Value transform (NasdaqTransform).
        """
        params: dict[str, str] = {"order": order.value}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if limit is not None:
            params["limit"] = str(limit)
        if collapse is not NasdaqCollapse.NONE:
            params["collapse"] = collapse.value
        if transform is not NasdaqTransform.NONE:
            params["transform"] = transform.value
        raw = self._request(f"datasets/{database_code}/{dataset_code}/data.json", params)
        data_raw: dict[str, Any] = raw.get("dataset_data", {})
        column_names, observations = _parse_observations(dataset_code, data_raw)
        return NasdaqResponse(
            database_code=database_code,
            dataset_code=dataset_code,
            column_names=column_names,
            observations=observations,
            meta=None,
        )

    def get_dataset_metadata(self, database_code: str, dataset_code: str) -> NasdaqDatasetMeta:
        """Fetch metadata (name, description, frequency, date range) for a dataset."""
        raw = self._request(f"datasets/{database_code}/{dataset_code}/metadata.json", {})
        meta_raw: dict[str, Any] = raw.get("dataset", {})
        if not meta_raw:
            raise NasdaqDataLinkClientError(f"No metadata for {database_code}/{dataset_code}")
        return _parse_meta(meta_raw)

    def get_datatable(
        self,
        datatable_code: str,
        *,
        filters: dict[str, str] | None = None,
        columns: tuple[str, ...] = (),
        cursor_id: str | None = None,
        per_page: int | None = None,
    ) -> NasdaqDatatable:
        """Fetch rows from a datatable, with optional filtering and pagination.

        Premium feature — requires a paid key. ``cursor_id`` resumes from a
        prior page's ``next_cursor_id``.
        """
        params: dict[str, str] = dict(filters or {})
        if columns:
            params["qopts.columns"] = ",".join(columns)
        if cursor_id:
            params["qopts.cursor_id"] = cursor_id
        if per_page is not None:
            params["qopts.per_page"] = str(per_page)
        raw = self._request(f"datatables/{datatable_code}.json", params)
        table_raw: dict[str, Any] = raw.get("datatable", {})
        meta: dict[str, Any] = raw.get("meta", {})
        cursor = meta.get("next_cursor_id")
        return _parse_datatable(datatable_code, table_raw, str(cursor) if cursor else None)

    def get_treasury_yield_curve(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> NasdaqResponse:
        """Fetch the US Treasury daily yield curve (free dataset USTREASURY/YIELD).

        Columns are the maturities (1 MO … 30 YR). Convenience wrapper over
        :meth:`get_dataset`.
        """
        return self.get_dataset(
            "USTREASURY",
            "YIELD",
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            order=NasdaqOrder.DESC,
        )

    def get_lbma_gold(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> NasdaqResponse:
        """Fetch the LBMA daily gold fixing in USD/EUR/GBP (free dataset LBMA/GOLD).

        Convenience wrapper over :meth:`get_dataset`.
        """
        return self.get_dataset(
            "LBMA",
            "GOLD",
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            order=NasdaqOrder.DESC,
        )

    def clear_cache(self) -> int:
        return self.cache.clear()


def _snapshot_hash(obs: NasdaqObservation, column_index: int) -> str:
    content = json.dumps(
        {
            "dataset": obs.dataset_code,
            "date": obs.series_date.isoformat(),
            "value": obs.values[column_index] if column_index < len(obs.values) else None,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def observation_to_primitive_yaml(
    obs: NasdaqObservation,
    *,
    slug: str,
    concept_slug: str,
    meta: NasdaqDatasetMeta | None,
    accessed: date,
    column_index: int = 0,
    dimension: str = "currency",
    currency: str = "USD",
    unit_kind: str = "flow",
) -> dict[str, Any]:
    value = obs.values[column_index] if column_index < len(obs.values) else None
    if value is None:
        raise NasdaqDataLinkClientError("Observation has no value in the requested column")
    unit: dict[str, str] = {"kind": unit_kind, "dimension": dimension}
    if dimension == "currency":
        unit["currency"] = currency
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": (meta.name if meta else obs.dataset_code) + f" ({obs.series_date.isoformat()})",
        "description": (
            meta.description if meta else f"Nasdaq Data Link series {obs.dataset_code}"
        ),
        "value": value,
        "unit": unit,
        "as_of": obs.series_date.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": observation_to_source_yaml(obs, accessed=accessed, column_index=column_index),
    }


def observation_to_source_yaml(
    obs: NasdaqObservation, *, accessed: date, column_index: int = 0
) -> dict[str, Any]:
    return {
        "slug": f"nasdaq-{obs.dataset_code.lower()}-{obs.series_date.isoformat()}",
        "tier": "aggregator",
        "url": f"https://data.nasdaq.com/data/{obs.dataset_code}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": _snapshot_hash(obs, column_index),
    }


_DATASET_ARGS = [
    CapabilityArg(
        name="database_code",
        type="str",
        description="Database code (e.g. LBMA, USTREASURY, FRED)",
        example="LBMA",
    ),
    CapabilityArg(
        name="dataset_code",
        type="str",
        description="Dataset code within the database",
        example="GOLD",
    ),
]


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_dataset",
            description=(
                "Time-series observations from a Nasdaq Data Link dataset "
                "(economic, commodity, financial). Free datasets only by default."
            ),
            returns="atomic primitive observations, unit varies by dataset, tier=aggregator",
            args=_DATASET_ARGS,
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_dataset_metadata",
            description=(
                "Metadata (name, description, frequency, date range) for a "
                "Nasdaq Data Link dataset."
            ),
            returns="dataset metadata, tier=aggregator",
            args=_DATASET_ARGS,
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_datatable",
            description=(
                "Premium (paid) datatable rows from Nasdaq Data Link, with "
                "filtering and cursor pagination. Requires a paid API key."
            ),
            returns="datatable rows + pagination cursor, tier=aggregator",
            args=[
                CapabilityArg(
                    name="datatable_code",
                    type="str",
                    description="Datatable code (e.g. ZACKS/FC)",
                    example="ZACKS/FC",
                ),
            ],
            source_tier="aggregator",
            requires_paid_tier=True,
        ),
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_treasury_yield_curve",
            description=(
                "US Treasury daily yield curve (free USTREASURY/YIELD dataset); "
                "columns are maturities 1 MO through 30 YR."
            ),
            returns="atomic primitive observations, unit=percent yield, tier=aggregator",
            args=[],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_lbma_gold",
            description=("LBMA daily gold fixing price in USD/EUR/GBP (free LBMA/GOLD dataset)."),
            returns="atomic primitive observations, unit=currency per troy oz, tier=aggregator",
            args=[],
            source_tier="aggregator",
        ),
    ]
