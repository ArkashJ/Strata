"""Eurostat SDMX / JSON-stat API client.

Typed wrappers for the Eurostat dissemination API with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

Primary endpoint: JSON-stat 2.0 (simpler to parse than SDMX XML).
Base URL: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data

No authentication required. No published rate limits (be courteous).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class EurostatCountry(StrEnum):
    """ISO 2-letter codes for EU members + common aggregates."""

    # Aggregates
    EU27 = "EU27_2020"
    EA20 = "EA20"

    # Member states (alphabetical by name)
    AT = "AT"  # Austria
    BE = "BE"  # Belgium
    BG = "BG"  # Bulgaria
    HR = "HR"  # Croatia
    CY = "CY"  # Cyprus
    CZ = "CZ"  # Czechia
    DK = "DK"  # Denmark
    EE = "EE"  # Estonia
    FI = "FI"  # Finland
    FR = "FR"  # France
    DE = "DE"  # Germany
    EL = "EL"  # Greece (Eurostat uses EL, not GR)
    HU = "HU"  # Hungary
    IE = "IE"  # Ireland
    IT = "IT"  # Italy
    LV = "LV"  # Latvia
    LT = "LT"  # Lithuania
    LU = "LU"  # Luxembourg
    MT = "MT"  # Malta
    NL = "NL"  # Netherlands
    PL = "PL"  # Poland
    PT = "PT"  # Portugal
    RO = "RO"  # Romania
    SK = "SK"  # Slovakia
    SI = "SI"  # Slovenia
    ES = "ES"  # Spain
    SE = "SE"  # Sweden

    # EEA / candidate countries commonly available
    NO = "NO"  # Norway
    CH = "CH"  # Switzerland
    IS = "IS"  # Iceland
    TR = "TR"  # Türkiye


class EurostatFrequency(StrEnum):
    ANNUAL = "A"
    QUARTERLY = "Q"
    MONTHLY = "M"


class EurostatDataset(StrEnum):
    """Common Eurostat datasets useful for market-sizing."""

    GDP = "nama_10_gdp"
    GDP_PER_CAPITA = "nama_10_pc"
    POPULATION = "demo_pjan"
    EMPLOYMENT = "lfsa_egan2"
    UNEMPLOYMENT = "une_rt_m"
    HICP_INFLATION = "prc_hicp_manr"
    TRADE = "ext_lt_maineu"
    HEALTH_SPENDING = "hlth_sha11_hf"
    RD_SPENDING = "rd_e_gerdtot"
    ICT_USAGE = "isoc_bde15cbc"
    TOURISM = "tour_occ_nim"
    ENERGY = "nrg_bal_c"
    INDUSTRIAL_PRODUCTION = "sts_inpr_m"
    BUSINESS_DEMOGRAPHY = "bd_9bd_sz_cl_r2"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw JSON-stat 2.0 response shapes
# ═══════════════════════════════════════════════════════════════════


class DimensionCategoryRaw(TypedDict, total=False):
    index: dict[str, int]
    label: dict[str, str]


class DimensionRaw(TypedDict, total=False):
    label: str
    category: DimensionCategoryRaw


class JsonStatResponseRaw(TypedDict, total=False):
    version: str
    label: str
    id: list[str]
    size: list[int]
    dimension: dict[str, DimensionRaw]
    value: dict[str, float]
    status: dict[str, str]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EurostatObservation:
    """A single data point extracted from a JSON-stat response."""

    dataset: str
    geo: str
    time_period: str
    value: float | None
    unit: str
    freq: str
    status_flag: str


@dataclass(frozen=True, slots=True)
class EurostatDatasetInfo:
    """Metadata about a Eurostat dataset."""

    id: str
    name: str
    description: str
    last_update: str


@dataclass(frozen=True, slots=True)
class EurostatResponse:
    """Standard return type for every Eurostat client call."""

    kind: str
    observations: tuple[EurostatObservation, ...] = ()
    datasets: tuple[EurostatDatasetInfo, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _extract_dimension_values(
    raw: dict[str, DimensionRaw],
    dim_ids: list[str],
) -> dict[str, list[str]]:
    """Build {dim_id: [code_0, code_1, ...]} ordered by JSON-stat index."""
    result: dict[str, list[str]] = {}
    for dim_id in dim_ids:
        dim_raw = raw.get(dim_id, {})
        cat: DimensionCategoryRaw = dim_raw.get("category", {})
        index_map: dict[str, int] = cat.get("index", {})
        # Sort codes by their positional index
        sorted_codes = sorted(index_map.keys(), key=lambda k: index_map[k])
        result[dim_id] = sorted_codes
    return result


def _flat_index(
    dim_ids: list[str],
    sizes: list[int],
    position: dict[str, int],
) -> int:
    """Compute the flat (row-major) index from dimension positions and sizes."""
    idx = 0
    multiplier = 1
    for i in range(len(dim_ids) - 1, -1, -1):
        idx += position[dim_ids[i]] * multiplier
        multiplier *= sizes[i]
    return idx


def _parse_observations(
    body: dict[str, Any],
    dataset: str,
) -> tuple[EurostatObservation, ...]:
    """Parse a JSON-stat 2.0 response into a tuple of observations."""
    dim_ids: list[str] = body.get("id", [])
    sizes: list[int] = body.get("size", [])
    dimension_raw: dict[str, DimensionRaw] = body.get("dimension", {})
    value_map: dict[str, float] = body.get("value", {})
    status_map: dict[str, str] = body.get("status", {})

    if not dim_ids or not sizes:
        return ()

    dim_values = _extract_dimension_values(dimension_raw, dim_ids)

    # Identify which dimensions carry geo, time, unit, freq
    geo_dim: str | None = None
    time_dim: str | None = None
    unit_dim: str | None = None
    freq_dim: str | None = None

    for d in dim_ids:
        dl = d.lower()
        if dl == "geo":
            geo_dim = d
        elif dl in ("time", "time_period"):
            time_dim = d
        elif dl in ("unit", "unit_measure"):
            unit_dim = d
        elif dl == "freq":
            freq_dim = d

    observations: list[EurostatObservation] = []

    # Iterate over all dimension combinations
    def _recurse(
        depth: int,
        position: dict[str, int],
        codes: dict[str, str],
    ) -> None:
        if depth == len(dim_ids):
            flat = _flat_index(dim_ids, sizes, position)
            flat_str = str(flat)
            raw_value = value_map.get(flat_str)
            value: float | None = None
            if raw_value is not None:
                try:
                    value = float(raw_value)
                except (ValueError, TypeError):
                    value = None
            status = status_map.get(flat_str, "")
            observations.append(
                EurostatObservation(
                    dataset=dataset,
                    geo=codes.get(geo_dim or "", ""),
                    time_period=codes.get(time_dim or "", ""),
                    value=value,
                    unit=codes.get(unit_dim or "", ""),
                    freq=codes.get(freq_dim or "", ""),
                    status_flag=status,
                )
            )
            return

        current_dim = dim_ids[depth]
        for i, code in enumerate(dim_values[current_dim]):
            position[current_dim] = i
            codes[current_dim] = code
            _recurse(depth + 1, position, codes)

    _recurse(0, {}, {})
    return tuple(observations)


def _parse_json_stat_response(
    body: dict[str, Any],
    dataset: str,
) -> EurostatResponse:
    """Parse a full JSON-stat 2.0 response into an EurostatResponse."""
    observations = _parse_observations(body, dataset)
    return EurostatResponse(
        kind="data",
        observations=observations,
        total=len(observations),
    )


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


class _DiskCache:
    """JSON-on-disk cache keyed by request hash, with configurable TTL."""

    def __init__(self, directory: Path, ttl_seconds: int = 604800) -> None:
        self._dir = directory
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"es_{key}.json"

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
        for f in self._dir.glob("es_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


class EurostatClientError(RuntimeError):
    """Raised on Eurostat API errors or client-side validation failures."""


class EurostatClient:
    """Typed client for the Eurostat JSON-stat API.

    Usage::

        client = EurostatClient()
        resp = client.get_gdp(geo="DE", start_year=2019, end_year=2023)
        for obs in resp.observations:
            print(obs.time_period, obs.value)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "eurostat"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EurostatClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        dataset: str,
        params: dict[str, str],
    ) -> EurostatResponse:
        """Issue a request to the Eurostat JSON-stat endpoint."""
        url = f"{_BASE}/{dataset}"
        params["format"] = "JSON"
        params["lang"] = "en"

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_json_stat_response(data, dataset)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)

        if http_resp.status_code == 404:
            raise EurostatClientError(
                f"Eurostat dataset '{dataset}' not found or no data for filters"
            )

        http_resp.raise_for_status()

        body: Any = http_resp.json()

        if not isinstance(body, dict):
            raise EurostatClientError(
                f"Eurostat API returned unexpected type: {type(body).__name__}"
            )

        body_dict = cast(dict[str, Any], body)

        # Check for error responses
        error_msg = body_dict.get("error")
        if error_msg is not None:
            raise EurostatClientError(f"Eurostat API error: {error_msg}")

        self._cache.put(ck, body_dict)
        return _parse_json_stat_response(body_dict, dataset)

    def _build_params(
        self,
        geo: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        frequency: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build query params for the JSON-stat endpoint."""
        params: dict[str, str] = {}
        if geo is not None:
            params["geo"] = geo
        if frequency is not None:
            params["freq"] = frequency
        if start_year is not None and end_year is not None:
            params["sinceTimePeriod"] = str(start_year)
            params["untilTimePeriod"] = str(end_year)
        elif start_year is not None:
            params["sinceTimePeriod"] = str(start_year)
        elif end_year is not None:
            params["untilTimePeriod"] = str(end_year)
        if filters:
            for k, v in filters.items():
                params[k] = v
        return params

    # ── core data fetch ──────────────────────────────────────────

    def get_data(
        self,
        dataset: str,
        geo: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        frequency: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> EurostatResponse:
        """Fetch data from any Eurostat dataset with arbitrary filters.

        Args:
            dataset: Eurostat dataset code (e.g. "nama_10_gdp").
            geo: Country/aggregate code (e.g. "DE", "EU27_2020").
            start_year: Start of time range (inclusive).
            end_year: End of time range (inclusive).
            frequency: Frequency filter (A, Q, M).
            filters: Additional dimension filters as key=value.
        """
        params = self._build_params(geo, start_year, end_year, frequency, filters)
        return self._request(dataset, params)

    # ── GDP ──────────────────────────────────────────────────────

    def get_gdp(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """GDP and main components (nama_10_gdp) in millions of EUR.

        Default unit: CP_MEUR (current prices, million euro).
        Default na_item: B1GQ (GDP at market prices).
        """
        filters: dict[str, str] = {"unit": "CP_MEUR", "na_item": "B1GQ"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.GDP, params)

    def get_gdp_per_capita(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """GDP per capita (nama_10_pc).

        Default unit: CP_EUR_HAB (current prices, euro per inhabitant).
        Default na_item: B1GQ.
        """
        filters: dict[str, str] = {"unit": "CP_EUR_HAB", "na_item": "B1GQ"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.GDP_PER_CAPITA, params)

    # ── Population ───────────────────────────────────────────────

    def get_population(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Population on 1 January (demo_pjan).

        Default sex: T (total). Default age: TOTAL.
        """
        filters: dict[str, str] = {"sex": "T", "age": "TOTAL"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.POPULATION, params)

    # ── Labour market ────────────────────────────────────────────

    def get_employment(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Employment by NACE Rev. 2 activity (lfsa_egan2).

        Default sex: T, age: Y15-64, nace_r2: TOTAL, unit: THS_PER.
        """
        filters: dict[str, str] = {
            "sex": "T",
            "age": "Y15-64",
            "nace_r2": "TOTAL",
            "unit": "THS_PER",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.EMPLOYMENT, params)

    def get_unemployment(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Unemployment rate (une_rt_m).

        Default sex: T, age: Y15-74, s_adj: SA, unit: PC_ACT.
        Returns monthly data.
        """
        filters: dict[str, str] = {
            "sex": "T",
            "age": "Y15-74",
            "s_adj": "SA",
            "unit": "PC_ACT",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.MONTHLY, filters=filters
        )
        return self._request(EurostatDataset.UNEMPLOYMENT, params)

    # ── Prices ───────────────────────────────────────────────────

    def get_inflation(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """HICP annual rate of change (prc_hicp_manr).

        Default coicop: CP00 (all items). Returns monthly data.
        """
        filters: dict[str, str] = {"coicop": "CP00", "unit": "RCH_A"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.MONTHLY, filters=filters
        )
        return self._request(EurostatDataset.HICP_INFLATION, params)

    # ── Trade ────────────────────────────────────────────────────

    def get_trade(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """External trade of EU (ext_lt_maineu).

        Default flow: BAL (balance), partner: EXT_EU27_2020,
        sitc06: TOTAL, unit: MIO_EUR, indic_et: TRD_VAL.
        """
        filters: dict[str, str] = {
            "flow": "BAL",
            "partner": "EXT_EU27_2020",
            "sitc06": "TOTAL",
            "indic_et": "TRD_VAL",
            "unit": "MIO_EUR",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.TRADE, params)

    # ── Health ───────────────────────────────────────────────────

    def get_health_spending(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Health expenditure by financing scheme (hlth_sha11_hf).

        Default icha11_hf: TOT_HF (all schemes), unit: MIO_EUR.
        """
        filters: dict[str, str] = {"icha11_hf": "TOT_HF", "unit": "MIO_EUR"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.HEALTH_SPENDING, params)

    # ── R&D ──────────────────────────────────────────────────────

    def get_rd_spending(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Gross domestic expenditure on R&D (rd_e_gerdtot).

        Default sectperf: TOTAL, unit: MIO_EUR.
        """
        filters: dict[str, str] = {"sectperf": "TOTAL", "unit": "MIO_EUR"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.RD_SPENDING, params)

    # ── ICT ──────────────────────────────────────────────────────

    def get_ict_usage(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """ICT usage in enterprises (isoc_bde15cbc).

        Default indic_is: E_CC (enterprises using cloud), unit: PC_ENT.
        """
        filters: dict[str, str] = {"indic_is": "E_CC", "unit": "PC_ENT"}
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.ICT_USAGE, params)

    # ── Tourism ──────────────────────────────────────────────────

    def get_tourism(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Tourism nights spent at accommodation (tour_occ_nim).

        Default nace_r2: I551-I553, c_resid: TOTAL, unit: NR.
        Returns monthly data.
        """
        filters: dict[str, str] = {
            "nace_r2": "I551-I553",
            "c_resid": "TOTAL",
            "unit": "NR",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.MONTHLY, filters=filters
        )
        return self._request(EurostatDataset.TOURISM, params)

    # ── Energy ───────────────────────────────────────────────────

    def get_energy(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Energy balance (nrg_bal_c).

        Default nrg_bal: PPRD (primary production), siec: TOTAL, unit: KTOE.
        """
        filters: dict[str, str] = {
            "nrg_bal": "PPRD",
            "siec": "TOTAL",
            "unit": "KTOE",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.ENERGY, params)

    # ── Industrial production ────────────────────────────────────

    def get_industrial_production(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Industrial production index (sts_inpr_m).

        Default nace_r2: B-D, s_adj: SCA, unit: I21.
        Returns monthly data.
        """
        filters: dict[str, str] = {
            "nace_r2": "B-D",
            "s_adj": "SCA",
            "unit": "I21",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.MONTHLY, filters=filters
        )
        return self._request(EurostatDataset.INDUSTRIAL_PRODUCTION, params)

    # ── Business demography ──────────────────────────────────────

    def get_business_demography(
        self,
        geo: str = "EU27_2020",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> EurostatResponse:
        """Business demography by size class (bd_9bd_sz_cl_r2).

        Default nace_r2: B-S_X_O, indic_sb: V11910 (births), sizeclas: TOTAL.
        """
        filters: dict[str, str] = {
            "nace_r2": "B-S_X_O",
            "indic_sb": "V11910",
            "sizeclas": "TOTAL",
        }
        params = self._build_params(
            geo, start_year, end_year, frequency=EurostatFrequency.ANNUAL, filters=filters
        )
        return self._request(EurostatDataset.BUSINESS_DEMOGRAPHY, params)

    # ── Multi-country convenience ────────────────────────────────

    def get_multi_country(
        self,
        dataset: str,
        countries: list[str],
        start_year: int | None = None,
        end_year: int | None = None,
        frequency: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> EurostatResponse:
        """Fetch data for multiple countries in one request.

        Eurostat accepts comma-separated geo codes in the query param.

        Args:
            dataset: Eurostat dataset code.
            countries: List of country/aggregate codes.
            start_year: Start of time range (inclusive).
            end_year: End of time range (inclusive).
            frequency: Frequency filter.
            filters: Additional dimension filters.
        """
        geo_str = "+".join(countries)
        merged_filters = dict(filters) if filters else {}
        params = self._build_params(
            geo=None,
            start_year=start_year,
            end_year=end_year,
            frequency=frequency,
            filters=merged_filters,
        )
        # Eurostat uses geo=X+Y+Z for multi-geo
        params["geo"] = geo_str
        return self._request(dataset, params)

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached Eurostat responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_observation(
    observations: tuple[EurostatObservation, ...],
    year: int | None,
) -> EurostatObservation:
    """Select a specific year's observation, preferring the requested year."""
    non_null = [o for o in observations if o.value is not None]

    if year is not None:
        year_str = str(year)
        match = next(
            (o for o in non_null if o.time_period == year_str),
            None,
        )
        if match is not None:
            return match

    if non_null:
        # Return the latest non-null observation (sort by time descending)
        return sorted(non_null, key=lambda o: o.time_period, reverse=True)[0]

    if observations:
        return observations[0]

    raise EurostatClientError("No observations to convert")


def _snapshot_hash(
    dataset: str,
    geo: str,
    time_period: str,
    value: float | None,
) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "dataset": dataset,
            "geo": geo,
            "time_period": time_period,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def observation_to_primitive_yaml(
    observations: tuple[EurostatObservation, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    year: int | None = None,
    geo_codes: tuple[str, ...] = ("EU27_2020",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "currency",
    unit_denominator: str | None = None,
    unit_currency: str | None = "EUR",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert Eurostat observations to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    obs = _pick_observation(observations, year)
    source_slug = f"es-{obs.dataset.lower().replace('_', '-')}-{obs.geo.lower()}-{obs.time_period}"
    sha = _snapshot_hash(obs.dataset, obs.geo, obs.time_period, obs.value)

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator
    if unit_currency:
        unit["currency"] = unit_currency

    # Determine as_of date: yearly data uses Dec 31, monthly uses last day
    if len(obs.time_period) == 4:
        as_of = f"{obs.time_period}-12-31"
    elif "M" in obs.time_period:
        # Format like "2023M06" → "2023-06-30"
        parts = obs.time_period.split("M")
        yr = parts[0]
        mo = parts[1] if len(parts) > 1 else "12"
        # Approximate last day of month
        last_day = "30" if mo in ("04", "06", "09", "11") else "31"
        if mo == "02":
            last_day = "28"
        as_of = f"{yr}-{mo}-{last_day}"
    elif "Q" in obs.time_period:
        # Format like "2023Q2" → "2023-06-30"
        parts = obs.time_period.split("Q")
        yr = parts[0]
        quarter = int(parts[1]) if len(parts) > 1 else 4
        q_months = {1: ("03", "31"), 2: ("06", "30"), 3: ("09", "30"), 4: ("12", "31")}
        mo, day = q_months.get(quarter, ("12", "31"))
        as_of = f"{yr}-{mo}-{day}"
    else:
        as_of = f"{obs.time_period}-12-31"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": obs.value,
        "unit": unit,
        "as_of": as_of,
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": distribution_shape,
        "delivery_mode": delivery_mode,
        "source": {
            "slug": source_slug,
            "tier": "regulator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def observation_to_source_yaml(
    observations: tuple[EurostatObservation, ...],
    *,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert Eurostat observations to a Strata source_registry YAML dict."""
    obs = _pick_observation(observations, year)
    source_slug = f"es-{obs.dataset.lower().replace('_', '-')}-{obs.geo.lower()}-{obs.time_period}"
    sha = _snapshot_hash(obs.dataset, obs.geo, obs.time_period, obs.value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or f"Eurostat {obs.dataset} for {obs.geo}, {obs.time_period} data.",
    }
