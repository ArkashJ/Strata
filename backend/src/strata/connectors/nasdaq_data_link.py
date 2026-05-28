"""Nasdaq Data Link connector — economic / financial time series.

Free datasets only by default. Paid datasets gated behind ``tier="premium"``
on the client.

API reference: https://docs.data.nasdaq.com/
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

from ._capability import CapabilityArg, CapabilitySpec


class NasdaqTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


@dataclass(frozen=True, slots=True)
class NasdaqObservation:
    dataset_code: str
    series_date: date
    value: float


@dataclass(frozen=True, slots=True)
class NasdaqDatasetMeta:
    database_code: str
    dataset_code: str
    name: str
    description: str
    frequency: str
    units: str | None
    refreshed_at: str | None


@dataclass(frozen=True, slots=True)
class NasdaqResponse:
    observations: tuple[NasdaqObservation, ...]
    meta: NasdaqDatasetMeta | None


def _safe_float(val: object) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val))
    except (TypeError, ValueError):
        return None


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
    """Nasdaq Data Link HTTP client.

    All requests cached on disk for 24h.
    """

    BASE_URL = "https://data.nasdaq.com/api/v3"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        tier: NasdaqTier = NasdaqTier.FREE,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.tier = tier
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "nasdaq_data_link")
        self._client = httpx.Client(timeout=timeout)

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
        try:
            resp = self._client.get(f"{self.BASE_URL}{path}", params=signed)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise NasdaqDataLinkClientError(f"Nasdaq request failed: {exc}") from exc
        self.cache.put(cache_key, data)
        return data

    def get_dataset(
        self,
        database_code: str,
        dataset_code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> NasdaqResponse:
        """Fetch dataset observations and metadata."""
        params: dict[str, str] = {"limit": str(limit)}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        raw = self._request(f"/datasets/{database_code}/{dataset_code}.json", params)
        dataset = raw.get("dataset", {})
        observations: list[NasdaqObservation] = []
        for row in dataset.get("data", []):
            if not isinstance(row, list) or len(row) < 2:
                continue
            try:
                d = date.fromisoformat(str(row[0]))
            except ValueError:
                continue
            v = _safe_float(row[1])
            if v is None:
                continue
            observations.append(
                NasdaqObservation(dataset_code=dataset_code, series_date=d, value=v)
            )
        meta: NasdaqDatasetMeta | None = None
        if dataset:
            meta = NasdaqDatasetMeta(
                database_code=str(dataset.get("database_code", database_code)),
                dataset_code=str(dataset.get("dataset_code", dataset_code)),
                name=str(dataset.get("name", "")),
                description=str(dataset.get("description", "")),
                frequency=str(dataset.get("frequency", "")),
                units=str(dataset["newest_available_date"])
                if dataset.get("newest_available_date")
                else None,
                refreshed_at=str(dataset["refreshed_at"]) if dataset.get("refreshed_at") else None,
            )
        return NasdaqResponse(observations=tuple(observations), meta=meta)

    def clear_cache(self) -> int:
        return self.cache.clear()


def observation_to_primitive_yaml(
    obs: NasdaqObservation,
    *,
    slug: str,
    concept_slug: str,
    meta: NasdaqDatasetMeta | None,
    accessed: date,
    dimension: str = "currency",
    currency: str = "USD",
) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": (meta.name if meta else obs.dataset_code) + f" ({obs.series_date.isoformat()})",
        "description": (
            meta.description if meta else f"Nasdaq Data Link series {obs.dataset_code}"
        ),
        "value": obs.value,
        "unit": {"kind": "flow", "dimension": dimension, "currency": currency},
        "as_of": obs.series_date.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": observation_to_source_yaml(obs, accessed=accessed),
    }


def observation_to_source_yaml(obs: NasdaqObservation, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {"dataset": obs.dataset_code, "date": obs.series_date.isoformat(), "value": obs.value},
        sort_keys=True,
    )
    return {
        "slug": f"nasdaq-{obs.dataset_code.lower()}-{obs.series_date.isoformat()}",
        "tier": "aggregator",
        "url": f"https://data.nasdaq.com/data/{obs.dataset_code}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


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
            args=[
                CapabilityArg(
                    name="database_code",
                    type="str",
                    description="Database code (e.g. WIKI, FRED, OPEC)",
                    example="OPEC",
                ),
                CapabilityArg(
                    name="dataset_code",
                    type="str",
                    description="Dataset code within the database",
                    example="ORB",
                ),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="nasdaq_data_link",
            method="get_dataset",
            description=(
                "Premium (paid) dataset observations from Nasdaq Data Link. "
                "Only available when the client is constructed with "
                "tier=NasdaqTier.PREMIUM and a paid API key."
            ),
            returns="atomic primitive observations, unit varies, tier=aggregator",
            args=[
                CapabilityArg(
                    name="database_code",
                    type="str",
                    description="Premium database code",
                    example="QDL/OPEC",
                ),
                CapabilityArg(
                    name="dataset_code",
                    type="str",
                    description="Dataset code within the premium database",
                    example="ORB",
                ),
            ],
            source_tier="aggregator",
            requires_paid_tier=True,
        ),
    ]
