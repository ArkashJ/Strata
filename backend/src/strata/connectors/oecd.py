"""OECD SDMX REST API client.

Typed wrappers for the OECD Statistics API (SDMX-JSON) with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://sdmx.oecd.org/public/rest
No authentication required. Rate limits undocumented (be polite).
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


class OECDFrequency(StrEnum):
    """SDMX frequency dimension codes."""

    ANNUAL = "A"
    QUARTERLY = "Q"
    MONTHLY = "M"


class OECDCountry(StrEnum):
    """ISO 3166-1 alpha-3 codes for all 38 OECD member countries."""

    AUS = "AUS"  # Australia
    AUT = "AUT"  # Austria
    BEL = "BEL"  # Belgium
    CAN = "CAN"  # Canada
    CHL = "CHL"  # Chile
    COL = "COL"  # Colombia
    CRI = "CRI"  # Costa Rica
    CZE = "CZE"  # Czech Republic
    DNK = "DNK"  # Denmark
    EST = "EST"  # Estonia
    FIN = "FIN"  # Finland
    FRA = "FRA"  # France
    DEU = "DEU"  # Germany
    GRC = "GRC"  # Greece
    HUN = "HUN"  # Hungary
    ISL = "ISL"  # Iceland
    IRL = "IRL"  # Ireland
    ISR = "ISR"  # Israel
    ITA = "ITA"  # Italy
    JPN = "JPN"  # Japan
    KOR = "KOR"  # Korea
    LVA = "LVA"  # Latvia
    LTU = "LTU"  # Lithuania
    LUX = "LUX"  # Luxembourg
    MEX = "MEX"  # Mexico
    NLD = "NLD"  # Netherlands
    NZL = "NZL"  # New Zealand
    NOR = "NOR"  # Norway
    POL = "POL"  # Poland
    PRT = "PRT"  # Portugal
    SVK = "SVK"  # Slovak Republic
    SVN = "SVN"  # Slovenia
    ESP = "ESP"  # Spain
    SWE = "SWE"  # Sweden
    CHE = "CHE"  # Switzerland
    TUR = "TUR"  # Turkiye
    GBR = "GBR"  # United Kingdom
    USA = "USA"  # United States


class OECDDataflow(StrEnum):
    """Common OECD dataflows for market-sizing.

    Format: ``{agency},{dsdId}@{dataflowId}``  (as expected by the SDMX REST
    ``/data/{dataflow}`` endpoint).
    """

    GDP = "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE"
    LABOUR = "OECD.SDD.TPS,DSD_LFS@DF_IALFS_INDIC"
    TRADE = "OECD.SDD.TPS,DSD_BOP@DF_BOP"
    HEALTH_SPENDING = "OECD.ELS.HD,DSD_SHA@DF_SHA"
    RD_SPENDING = "OECD.STI.STP,DSD_MSTI@DF_MSTI"
    EDUCATION = "OECD.EDU.IMEP,DSD_EAG_FIN@DF_EAG_FIN_INDICATOR"
    PRODUCTIVITY = "OECD.SDD.NAD,DSD_NAAG@DF_NAAG_I"
    CPI = "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL"
    INTEREST_RATES = "OECD.SDD.STES,DSD_KEI@DF_KEI"
    FDI = "OECD.SDD.TPS,DSD_FDI@DF_FDI_MAIN"
    UNEMPLOYMENT = "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_RATES"
    POPULATION = "OECD.ELS.SAE,DSD_POPULATION@DF_POP_HIST"
    # Gross value added by NACE activity (National Accounts, NAMAIN10 family).
    VALUE_ADDED = "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE6"
    # Household final consumption by COICOP purpose (NAMAIN1, table 5).
    HOUSEHOLD_CONSUMPTION = "OECD.SDD.NAD,DSD_NAMAIN1@DF_TABLE5"
    # Employment by NACE activity (National Accounts, NAMAIN10 employment table).
    EMPLOYMENT_BY_SECTOR = "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE3"
    # ICT access & use by businesses / households (Going Digital, ICT_HH_IND).
    ICT_BUSINESS = "OECD.STI.DEP,DSD_ICT_BUS@DF_BUS_ICT"
    ICT_HOUSEHOLD = "OECD.STI.DEP,DSD_ICT_HH@DF_HH_ICT"
    # Structural business statistics — business demography (TIMELY_BDS family).
    BUSINESS_DEMOGRAPHY = "OECD.SDD.TPS,DSD_BDS@DF_BDS"
    # Patents (Intellectual Property statistics, PATS_IPC family).
    PATENTS = "OECD.STI.PIE,DSD_PATS_IPC@DF_PATS_IPC"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw SDMX-JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class _DimensionValueRaw(TypedDict, total=False):
    id: str
    name: str


class _DimensionRaw(TypedDict, total=False):
    id: str
    name: str
    keyPosition: int
    values: list[_DimensionValueRaw]


class _AttributeValueRaw(TypedDict, total=False):
    id: str
    name: str


class _AttributeRaw(TypedDict, total=False):
    id: str
    name: str
    values: list[_AttributeValueRaw]


class _StructureRaw(TypedDict, total=False):
    dimensions: dict[str, list[_DimensionRaw]]
    attributes: dict[str, list[_AttributeRaw]]


class _DataSetRaw(TypedDict, total=False):
    action: str
    observations: dict[str, list[float | None]]
    series: dict[str, dict[str, Any]]


class DataMessageRaw(TypedDict, total=False):
    """Top-level SDMX-JSON data message."""

    header: dict[str, Any]
    dataSets: list[_DataSetRaw]
    structure: _StructureRaw


class DataflowMessageRaw(TypedDict, total=False):
    """Top-level SDMX-JSON dataflow list response."""

    data: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class OECDObservation:
    """A single data point from an OECD SDMX dataset."""

    country: str
    frequency: str
    time_period: str
    value: float | None
    unit_measure: str
    flags: str
    series_key: str
    dataflow_id: str


@dataclass(frozen=True, slots=True)
class OECDSeriesInfo:
    """Metadata about an SDMX series."""

    dataflow_id: str
    name: str
    description: str
    agency: str


@dataclass(frozen=True, slots=True)
class OECDBusinessStat:
    """A business-demography / structural-business statistic data point."""

    country: str
    activity: str
    indicator: str
    time_period: str
    value: float | None
    unit_measure: str
    dataflow_id: str


@dataclass(frozen=True, slots=True)
class OECDDataflowInfo:
    """Metadata about an OECD dataflow."""

    id: str
    name: str
    description: str
    agency: str
    version: str


@dataclass(frozen=True, slots=True)
class OECDResponse:
    """Standard return type for every OECD client call."""

    kind: str
    observations: tuple[OECDObservation, ...] = ()
    dataflows: tuple[OECDDataflowInfo, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing — standalone functions (not methods)
# ═══════════════════════════════════════════════════════════════════


def _safe_lookup(values: list[dict[str, str]], index: int) -> str:
    """Look up a value by index, returning empty string if out of range."""
    if 0 <= index < len(values):
        return values[index].get("id", values[index].get("name", ""))
    return ""


def _parse_data_message(
    body: dict[str, Any],
    *,
    dataflow_id: str,
) -> OECDResponse:
    """Parse an SDMX-JSON data message into OECDObservation tuples.

    SDMX-JSON uses a compact representation where series and observation keys
    are colon-separated dimension indices.  We resolve each index back to
    the human-readable value using the ``structure`` block.
    """
    # SDMX-JSON 2.0 (current OECD API) wraps everything under "data" and uses a
    # "structures" list; SDMX-JSON 1.0 put "structure" (singular) and "dataSets"
    # at the top level. Accept both so the parser survives the version the live
    # endpoint actually serves.
    container: dict[str, Any] = body.get("data", body)
    structure: dict[str, Any] = container.get("structure", {})
    if not structure:
        structures = container.get("structures", [])
        if structures:
            structure = structures[0]
    datasets: list[dict[str, Any]] = container.get("dataSets", [])

    if not datasets:
        return OECDResponse(kind="data", total=0)

    dataset = datasets[0]

    # Resolve dimension value lists for series-level keys
    series_dims: list[dict[str, Any]] = structure.get("dimensions", {}).get("series", [])
    obs_dims: list[dict[str, Any]] = structure.get("dimensions", {}).get("observation", [])

    # Build ordered value lists for each series dimension
    series_dim_values: list[list[dict[str, str]]] = [d.get("values", []) for d in series_dims]
    obs_dim_values: list[list[dict[str, str]]] = [d.get("values", []) for d in obs_dims]

    # Identify well-known dimensions by id
    ref_area_pos: int | None = None
    freq_pos: int | None = None
    unit_measure_pos: int | None = None
    for idx, d in enumerate(series_dims):
        did = d.get("id", "")
        if did == "REF_AREA":
            ref_area_pos = idx
        elif did == "FREQ":
            freq_pos = idx
        elif did == "UNIT_MEASURE":
            unit_measure_pos = idx

    # Observation-level attribute for flags / status
    obs_attrs: list[dict[str, Any]] = structure.get("attributes", {}).get("observation", [])
    obs_status_attr_idx: int | None = None
    obs_status_values: list[dict[str, str]] = []
    for idx, a in enumerate(obs_attrs):
        if a.get("id") == "OBS_STATUS":
            obs_status_attr_idx = idx
            obs_status_values = a.get("values", [])
            break

    # Unit measure may also live as a series-level attribute
    series_attrs: list[dict[str, Any]] = structure.get("attributes", {}).get("series", [])
    unit_attr_idx: int | None = None
    unit_attr_values: list[dict[str, str]] = []
    for idx, a in enumerate(series_attrs):
        if a.get("id") == "UNIT_MEASURE":
            unit_attr_idx = idx
            unit_attr_values = a.get("values", [])
            break

    observations: list[OECDObservation] = []

    raw_series: dict[str, Any] = dataset.get("series", {})
    for series_key_str, series_obj in raw_series.items():
        # series_key_str is like "0:1:0:2:..." — indices into series_dim_values
        key_parts = series_key_str.split(":")
        key_indices = [int(p) for p in key_parts]

        # Extract country, frequency, unit from series key dimensions
        country = ""
        frequency = ""
        unit_from_dim = ""
        if ref_area_pos is not None and ref_area_pos < len(key_indices):
            country = _safe_lookup(series_dim_values[ref_area_pos], key_indices[ref_area_pos])
        if freq_pos is not None and freq_pos < len(key_indices):
            frequency = _safe_lookup(series_dim_values[freq_pos], key_indices[freq_pos])
        if unit_measure_pos is not None and unit_measure_pos < len(key_indices):
            unit_from_dim = _safe_lookup(
                series_dim_values[unit_measure_pos],
                key_indices[unit_measure_pos],
            )

        # Unit measure may be a series attribute instead of a dimension
        unit_from_attr = ""
        if unit_attr_idx is not None:
            s_attrs: list[int | None] | None = series_obj.get("attributes")
            if s_attrs and unit_attr_idx < len(s_attrs):
                attr_val = s_attrs[unit_attr_idx]
                if attr_val is not None:
                    unit_from_attr = _safe_lookup(unit_attr_values, attr_val)

        unit_measure = unit_from_dim or unit_from_attr

        # Parse each observation in this series
        raw_obs: dict[str, list[Any]] = series_obj.get("observations", {})
        for obs_key_str, obs_vals in raw_obs.items():
            obs_key_parts = obs_key_str.split(":")
            obs_key_indices = [int(p) for p in obs_key_parts]

            # Resolve time period (usually the first obs dimension)
            time_period = ""
            if obs_dim_values and obs_key_indices:
                time_period = _safe_lookup(obs_dim_values[0], obs_key_indices[0])

            # Value is the first element of the observation array
            raw_value: float | None = None
            if obs_vals:
                v = obs_vals[0]
                if v is not None:
                    try:
                        raw_value = float(v)
                    except (ValueError, TypeError):
                        raw_value = None

            # Flags from observation attributes
            flags = ""
            if obs_status_attr_idx is not None and len(obs_vals) > obs_status_attr_idx + 1:
                flag_idx = obs_vals[obs_status_attr_idx + 1]
                if flag_idx is not None:
                    try:
                        flags = _safe_lookup(obs_status_values, int(flag_idx))
                    except (ValueError, TypeError):
                        flags = ""

            observations.append(
                OECDObservation(
                    country=country,
                    frequency=frequency,
                    time_period=time_period,
                    value=raw_value,
                    unit_measure=unit_measure,
                    flags=flags,
                    series_key=series_key_str,
                    dataflow_id=dataflow_id,
                )
            )

    # Also handle the flat "observations" format (no series grouping)
    if not raw_series and "observations" in dataset:
        flat_obs: dict[str, list[Any]] = dataset.get("observations", {})
        all_dims = series_dims + obs_dims
        all_dim_values = series_dim_values + obs_dim_values

        # Re-find positions in the combined dimension list
        flat_ref_area: int | None = None
        flat_freq: int | None = None
        flat_time: int | None = None
        flat_unit: int | None = None
        for idx, d in enumerate(all_dims):
            did = d.get("id", "")
            if did == "REF_AREA":
                flat_ref_area = idx
            elif did == "FREQ":
                flat_freq = idx
            elif did == "TIME_PERIOD":
                flat_time = idx
            elif did == "UNIT_MEASURE":
                flat_unit = idx

        for obs_key_str, obs_vals in flat_obs.items():
            parts = obs_key_str.split(":")
            indices = [int(p) for p in parts]

            country = ""
            frequency = ""
            time_period = ""
            unit_measure_flat = ""
            if flat_ref_area is not None and flat_ref_area < len(indices):
                country = _safe_lookup(all_dim_values[flat_ref_area], indices[flat_ref_area])
            if flat_freq is not None and flat_freq < len(indices):
                frequency = _safe_lookup(all_dim_values[flat_freq], indices[flat_freq])
            if flat_time is not None and flat_time < len(indices):
                time_period = _safe_lookup(all_dim_values[flat_time], indices[flat_time])
            if flat_unit is not None and flat_unit < len(indices):
                unit_measure_flat = _safe_lookup(all_dim_values[flat_unit], indices[flat_unit])

            raw_value = None
            if obs_vals:
                v = obs_vals[0]
                if v is not None:
                    try:
                        raw_value = float(v)
                    except (ValueError, TypeError):
                        raw_value = None

            observations.append(
                OECDObservation(
                    country=country,
                    frequency=frequency,
                    time_period=time_period,
                    value=raw_value,
                    unit_measure=unit_measure_flat,
                    flags="",
                    series_key=obs_key_str,
                    dataflow_id=dataflow_id,
                )
            )

    obs_tuple = tuple(observations)
    return OECDResponse(kind="data", observations=obs_tuple, total=len(obs_tuple))


def _parse_dataflow_list(body: dict[str, Any]) -> OECDResponse:
    """Parse a dataflow list response into OECDDataflowInfo tuples."""
    # SDMX structure messages nest under data.dataflows or data.dataStructures
    data_block: dict[str, Any] = body.get("data", {})
    raw_flows: list[dict[str, Any]] = data_block.get("dataflows", [])

    flows: list[OECDDataflowInfo] = []
    for rf in raw_flows:
        # name / description may be dicts with language keys or plain strings
        name_obj: Any = rf.get("name", "")
        if isinstance(name_obj, dict):
            name_dict = cast(dict[str, str], name_obj)
            name_str = str(name_dict.get("en", next(iter(name_dict.values()), "")))
        else:
            name_str = str(name_obj)

        desc_obj: Any = rf.get("description", "")
        if isinstance(desc_obj, dict):
            desc_dict = cast(dict[str, str], desc_obj)
            desc_str = str(desc_dict.get("en", next(iter(desc_dict.values()), "")))
        else:
            desc_str = str(desc_obj)

        flows.append(
            OECDDataflowInfo(
                id=str(rf.get("id", "")),
                name=name_str,
                description=desc_str,
                agency=str(rf.get("agencyID", "")),
                version=str(rf.get("version", "")),
            )
        )

    flow_tuple = tuple(flows)
    return OECDResponse(kind="dataflows", dataflows=flow_tuple, total=len(flow_tuple))


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
        return self._dir / f"oecd_{key}.json"

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
        for f in self._dir.glob("oecd_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://sdmx.oecd.org/public/rest"


class OECDClientError(RuntimeError):
    """Raised on OECD API errors or client-side validation failures."""


class OECDClient:
    """Typed client for the OECD SDMX REST API.

    Usage::

        client = OECDClient()
        resp = client.get_gdp("USA", start_period="2019", end_period="2023")
        for obs in resp.observations:
            print(obs.time_period, obs.value, obs.unit_measure)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={
                "Accept": "application/json",
                "User-Agent": "strata-connector/0.2",
            },
        )
        default_cache = Path.home() / ".strata" / "cache" / "oecd"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OECDClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request_data(
        self,
        dataflow: str,
        key: str = "",
        *,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Fetch data from a dataflow with optional key filter and time range."""
        # Build URL: /data/{dataflow}/{key}
        url = f"{_BASE}/data/{dataflow}"
        if key:
            url = f"{url}/{key}"

        params: dict[str, str] = {"format": "jsondata"}
        if start_period is not None:
            params["startPeriod"] = start_period
        if end_period is not None:
            params["endPeriod"] = end_period

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_data_message(data, dataflow_id=dataflow)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)
        if http_resp.status_code == 404:
            return OECDResponse(kind="data", total=0)
        if http_resp.status_code == 413:
            raise OECDClientError(
                "OECD API: response too large — narrow your query "
                "(add country filter, shorten time range, or specify a key)."
            )
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise OECDClientError(f"OECD API returned unexpected type: {type(body).__name__}")
        body_dict = cast(dict[str, Any], body)

        self._cache.put(ck, body_dict)
        return _parse_data_message(body_dict, dataflow_id=dataflow)

    def _request_structure(
        self,
        resource: str,
        agency: str = "OECD",
    ) -> OECDResponse:
        """Fetch a structure resource (dataflows, data structures, etc.)."""
        url = f"{_BASE}/{resource}/{agency}"
        params: dict[str, str] = {"format": "jsondata"}

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_dataflow_list(data)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise OECDClientError(f"OECD API returned unexpected type: {type(body).__name__}")
        body_dict = cast(dict[str, Any], body)

        self._cache.put(ck, body_dict)
        return _parse_dataflow_list(body_dict)

    # ── core data fetch ──────────────────────────────────────────

    def get_indicator(
        self,
        dataflow: str | OECDDataflow,
        country: str | OECDCountry = OECDCountry.USA,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Retrieve data for a dataflow, country, and frequency.

        Args:
            dataflow: OECD dataflow identifier (use OECDDataflow enum).
            country: ISO 3166-1 alpha-3 country code.
            frequency: Frequency dimension (A, Q, M).
            start_period: Start year/quarter (e.g. "2019" or "2019-Q1").
            end_period: End year/quarter.
        """
        # SDMX key filter: dimensions separated by dots; use "." for wildcard
        # Most OECD dataflows put REF_AREA and FREQ as first dimensions
        # but positions vary. We pass them as part of the key filter.
        key = f"{country}.{frequency}"
        return self._request_data(
            str(dataflow),
            key,
            start_period=start_period,
            end_period=end_period,
        )

    def get_indicator_all_measures(
        self,
        dataflow: str | OECDDataflow,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Retrieve all measures/frequencies for a dataflow and country.

        Omits the frequency filter, returning annual, quarterly, and monthly
        data as available.
        """
        key = f"{country}"
        return self._request_data(
            str(dataflow),
            key,
            start_period=start_period,
            end_period=end_period,
        )

    def get_indicator_raw(
        self,
        dataflow: str | OECDDataflow,
        key: str = "",
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Retrieve data with an arbitrary SDMX key filter.

        Use this for dataflows where the default ``{country}.{freq}`` key
        pattern doesn't fit. Pass a full SDMX key string like
        ``"USA.A.B1GQ.V...."`` or leave empty for all data.
        """
        return self._request_data(
            str(dataflow),
            key,
            start_period=start_period,
            end_period=end_period,
        )

    # ── GDP shortcuts ────────────────────────────────────────────

    def get_gdp(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """GDP by expenditure approach (current prices, national currency).

        The DSD_NAMAIN10 structure has 12 ordered dimensions
        (FREQ.REF_AREA.SECTOR.COUNTERPART_SECTOR.TRANSACTION.INSTR_ASSET.
        ACTIVITY.EXPENDITURE.UNIT_MEASURE.PRICE_BASE.TRANSFORMATION.
        TABLE_IDENTIFIER); the bare ``{country}.{freq}`` key the generic
        ``get_indicator`` builds is rejected (HTTP 422). Pin GDP B1GQ for the
        total economy at current prices (V) in national currency (XDC).
        """
        key = f"{frequency}.{country}.S1.S1.B1GQ._Z._Z._Z.XDC.V.N.T0102"
        return self.get_indicator_raw(
            OECDDataflow.GDP,
            key=key,
            start_period=start_period,
            end_period=end_period,
        )

    def get_gdp_growth(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """GDP growth rate — annual, all available measures."""
        return self.get_indicator(
            OECDDataflow.GDP,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    def get_gdp_per_capita(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """GDP per capita — annual, all available measures."""
        return self.get_indicator(
            OECDDataflow.GDP,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── labour / unemployment ────────────────────────────────────

    def get_unemployment(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Unemployment rate (harmonised, annual)."""
        return self.get_indicator(
            OECDDataflow.UNEMPLOYMENT,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    def get_unemployment_monthly(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Unemployment rate (harmonised, monthly)."""
        return self.get_indicator(
            OECDDataflow.UNEMPLOYMENT,
            country=country,
            frequency=OECDFrequency.MONTHLY,
            start_period=start_period,
            end_period=end_period,
        )

    def get_labour_force(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Labour force statistics (annual)."""
        return self.get_indicator(
            OECDDataflow.LABOUR,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── prices / inflation ───────────────────────────────────────

    def get_cpi(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Consumer price index / inflation data."""
        return self.get_indicator(
            OECDDataflow.CPI,
            country=country,
            frequency=frequency,
            start_period=start_period,
            end_period=end_period,
        )

    # ── trade / balance of payments ──────────────────────────────

    def get_trade_balance(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Balance of payments data (annual)."""
        return self.get_indicator(
            OECDDataflow.TRADE,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── health ───────────────────────────────────────────────────

    def get_health_spending(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Health expenditure (System of Health Accounts)."""
        return self.get_indicator(
            OECDDataflow.HEALTH_SPENDING,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── R&D ──────────────────────────────────────────────────────

    def get_rd_spending(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """R&D expenditure (Main Science & Technology Indicators)."""
        return self.get_indicator(
            OECDDataflow.RD_SPENDING,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── education ────────────────────────────────────────────────

    def get_education_spending(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Education finance indicators (Education at a Glance)."""
        return self.get_indicator(
            OECDDataflow.EDUCATION,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── productivity ─────────────────────────────────────────────

    def get_productivity(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Productivity indicators (National Accounts Aggregates)."""
        return self.get_indicator(
            OECDDataflow.PRODUCTIVITY,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── FDI ──────────────────────────────────────────────────────

    def get_fdi(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Foreign direct investment flows (annual)."""
        return self.get_indicator(
            OECDDataflow.FDI,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── interest rates ───────────────────────────────────────────

    def get_interest_rates(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        frequency: str | OECDFrequency = OECDFrequency.MONTHLY,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Key economic indicators — interest rates (monthly default)."""
        return self.get_indicator(
            OECDDataflow.INTEREST_RATES,
            country=country,
            frequency=frequency,
            start_period=start_period,
            end_period=end_period,
        )

    # ── population ───────────────────────────────────────────────

    def get_population(
        self,
        country: str | OECDCountry = OECDCountry.USA,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Historical population data (annual)."""
        return self.get_indicator(
            OECDDataflow.POPULATION,
            country=country,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── national accounts: value added / consumption / employment ─

    def get_value_added_by_sector(
        self,
        ref_area: str | OECDCountry = OECDCountry.USA,
        activity: str = "_T",
        year: int | None = None,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
    ) -> OECDResponse:
        """Gross value added by NACE activity (NAMAIN10).

        Args:
            ref_area: ISO-3 country code.
            activity: NACE Rev.2 activity code (``_T`` = total economy,
                ``D`` = manufacturing, ``J`` = information & communication).
            year: Single year to filter (sets start/end period).
            frequency: A / Q.

        Note: NAMAIN10 is a wide National-Accounts cube. The key below
            pins REF_AREA + FREQ + ACTIVITY and wildcards the remaining
            dimensions; callers needing a specific transaction/measure
            should use ``get_indicator_raw`` with a fully-specified key.
        """
        # TODO(dataflow-key): NAMAIN10 dimension order/measure codes not
        # verified against list_dataflows(); wildcard tail covers them.
        key = f"{ref_area}.{frequency}..{activity}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.VALUE_ADDED), key, start_period=period, end_period=period
        )

    def get_household_consumption(
        self,
        ref_area: str | OECDCountry = OECDCountry.USA,
        coicop: str = "_T",
        year: int | None = None,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
    ) -> OECDResponse:
        """Household final consumption by COICOP purpose (NAMAIN1, table 5).

        Args:
            ref_area: ISO-3 country code.
            coicop: COICOP purpose code (``_T`` = total).
            year: Single year filter.
            frequency: A / Q.
        """
        # TODO(dataflow-key): NAMAIN1 table-5 COICOP dimension position not
        # verified; wildcard tail covers any extra dimensions.
        key = f"{ref_area}.{frequency}..{coicop}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.HOUSEHOLD_CONSUMPTION), key, start_period=period, end_period=period
        )

    def get_employment_by_sector(
        self,
        activity: str = "_T",
        ref_area: str | OECDCountry = OECDCountry.USA,
        year: int | None = None,
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
    ) -> OECDResponse:
        """Employment by NACE activity (NAMAIN10 employment table).

        Args:
            activity: NACE Rev.2 activity code (``_T`` = total economy).
            ref_area: ISO-3 country code.
            year: Single year filter.
            frequency: A / Q.
        """
        # TODO(dataflow-key): NAMAIN10 employment-table measure code not
        # verified against list_dataflows().
        key = f"{ref_area}.{frequency}..{activity}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.EMPLOYMENT_BY_SECTOR), key, start_period=period, end_period=period
        )

    # ── digital economy: ICT adoption ─────────────────────────────

    def get_ict_business_adoption(
        self,
        indicator: str = "_T",
        ref_area: str | OECDCountry = OECDCountry.USA,
        year: int | None = None,
    ) -> OECDResponse:
        """ICT access and use by businesses (Going Digital, ICT_BUS).

        Args:
            indicator: ICT indicator code (e.g. cloud/e-commerce use).
            ref_area: ISO-3 country code.
            year: Single year filter.
        """
        # TODO(dataflow-key): ICT_BUS indicator dimension codes not verified.
        key = f"{ref_area}.{OECDFrequency.ANNUAL}.{indicator}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.ICT_BUSINESS), key, start_period=period, end_period=period
        )

    def get_ict_household_adoption(
        self,
        indicator: str = "_T",
        ref_area: str | OECDCountry = OECDCountry.USA,
        year: int | None = None,
    ) -> OECDResponse:
        """ICT access and use by households / individuals (ICT_HH).

        Args:
            indicator: ICT indicator code (e.g. internet use, online purchases).
            ref_area: ISO-3 country code.
            year: Single year filter.
        """
        # TODO(dataflow-key): ICT_HH indicator dimension codes not verified.
        key = f"{ref_area}.{OECDFrequency.ANNUAL}.{indicator}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.ICT_HOUSEHOLD), key, start_period=period, end_period=period
        )

    # ── structural business statistics ────────────────────────────

    def get_business_demography(
        self,
        ref_area: str | OECDCountry = OECDCountry.USA,
        activity: str = "_T",
        indicator: str = "_T",
        year: int | None = None,
    ) -> tuple[OECDBusinessStat, ...]:
        """Business demography (births / deaths / active enterprises).

        Returns ``OECDBusinessStat`` tuples (richer than plain observations
        — carries activity + indicator). Underlying dataflow: BDS.

        Args:
            ref_area: ISO-3 country code.
            activity: NACE Rev.2 activity code.
            indicator: Business-demography indicator code.
            year: Single year filter.
        """
        # TODO(dataflow-key): BDS dimension order not verified.
        key = f"{ref_area}.{OECDFrequency.ANNUAL}.{indicator}.{activity}"
        period = str(year) if year is not None else None
        resp = self._request_data(
            str(OECDDataflow.BUSINESS_DEMOGRAPHY), key, start_period=period, end_period=period
        )
        return tuple(
            OECDBusinessStat(
                country=o.country,
                activity=activity,
                indicator=indicator,
                time_period=o.time_period,
                value=o.value,
                unit_measure=o.unit_measure,
                dataflow_id=o.dataflow_id,
            )
            for o in resp.observations
        )

    def get_patents(
        self,
        ref_area: str | OECDCountry = OECDCountry.USA,
        ipc_class: str = "_T",
        year: int | None = None,
    ) -> OECDResponse:
        """Patent counts by IPC technology class (PATS_IPC).

        Args:
            ref_area: ISO-3 country code.
            ipc_class: IPC technology class code (``_T`` = all classes).
            year: Single year filter.
        """
        # TODO(dataflow-key): PATS_IPC dimension order not verified.
        key = f"{ref_area}.{OECDFrequency.ANNUAL}.{ipc_class}"
        period = str(year) if year is not None else None
        return self._request_data(
            str(OECDDataflow.PATENTS), key, start_period=period, end_period=period
        )

    # ── multi-country ────────────────────────────────────────────

    def get_multi_country(
        self,
        dataflow: str | OECDDataflow,
        countries: list[str],
        frequency: str | OECDFrequency = OECDFrequency.ANNUAL,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Fetch data for multiple countries in one request.

        The SDMX API accepts ``+``-separated values within a key dimension.
        """
        country_str = "+".join(countries)
        key = f"{country_str}.{frequency}"
        return self._request_data(
            str(dataflow),
            key,
            start_period=start_period,
            end_period=end_period,
        )

    def get_multi_country_gdp(
        self,
        countries: list[str],
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """GDP for multiple countries (annual)."""
        return self.get_multi_country(
            OECDDataflow.GDP,
            countries,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    def get_multi_country_unemployment(
        self,
        countries: list[str],
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """Unemployment rates for multiple countries (annual)."""
        return self.get_multi_country(
            OECDDataflow.UNEMPLOYMENT,
            countries,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    def get_multi_country_cpi(
        self,
        countries: list[str],
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> OECDResponse:
        """CPI/inflation for multiple countries (annual)."""
        return self.get_multi_country(
            OECDDataflow.CPI,
            countries,
            frequency=OECDFrequency.ANNUAL,
            start_period=start_period,
            end_period=end_period,
        )

    # ── structure / metadata ─────────────────────────────────────

    def list_dataflows(self, agency: str = "OECD") -> OECDResponse:
        """List available dataflows for an agency."""
        return self._request_structure("dataflow", agency=agency)

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached OECD responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_observation(
    observations: tuple[OECDObservation, ...],
    year: int | None,
) -> OECDObservation:
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
        # SDMX typically returns chronological order; pick the latest
        return non_null[-1]

    if observations:
        return observations[-1]

    raise OECDClientError("No observations to convert")


def _snapshot_hash(
    dataflow_id: str,
    country: str,
    time_period: str,
    value: float | None,
) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "dataflow_id": dataflow_id,
            "country": country,
            "time_period": time_period,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _as_of_date(time_period: str) -> str:
    """Convert an SDMX time period to an as_of date string.

    Handles: "2023" → "2023-12-31", "2023-Q4" → "2023-12-31",
    "2023-01" → "2023-01-31".
    """
    if len(time_period) == 4:
        return f"{time_period}-12-31"
    if "-Q" in time_period:
        year, q = time_period.split("-Q")
        quarter_end = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
        return f"{year}-{quarter_end.get(q, '12-31')}"
    if len(time_period) == 7:
        # YYYY-MM format
        return f"{time_period}-28"
    return f"{time_period}-12-31"


def _slug_safe(s: str) -> str:
    """Convert a string to a slug-safe form (lowercase; punctuation to dashes).

    OECD dataflow ids carry dots, commas, ``@`` and underscores
    (e.g. ``OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE``); the
    AtomicPrimitive source slug pattern is ``^[a-z0-9][a-z0-9-]*$`` so every
    separator — including ``_`` — must collapse to ``-``.
    """
    out = s.lower()
    for ch in (".", " ", ",", "@", "_"):
        out = out.replace(ch, "-")
    return out


def oecd_observation_to_primitive_yaml(
    observations: tuple[OECDObservation, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    year: int | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "currency",
    unit_denominator: str | None = None,
    unit_currency: str | None = "USD",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert OECD observations to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    point = _pick_observation(observations, year)
    source_slug = (
        f"oecd-{_slug_safe(point.dataflow_id)}-{point.country.lower()}-{point.time_period}"
    )
    sha = _snapshot_hash(point.dataflow_id, point.country, point.time_period, point.value)

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
        "value": point.value,
        "unit": unit,
        "as_of": _as_of_date(point.time_period),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": distribution_shape,
        "delivery_mode": delivery_mode,
        "source": {
            "slug": source_slug,
            "tier": "aggregator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def oecd_observation_to_source_yaml(
    observations: tuple[OECDObservation, ...],
    *,
    source_url: str,
    year: int | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Convert OECD observations to a Strata source_registry YAML dict."""
    point = _pick_observation(observations, year)
    source_slug = (
        f"oecd-{_slug_safe(point.dataflow_id)}-{point.country.lower()}-{point.time_period}"
    )
    sha = _snapshot_hash(point.dataflow_id, point.country, point.time_period, point.value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "aggregator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or (f"OECD {point.dataflow_id} for {point.country}, {point.time_period} data."),
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="oecd",
            method="get_gdp",
            description="OECD GDP for a member country.",
            returns="atomic primitive, unit=currency USD (or local), tier=aggregator",
            args=[
                CapabilityArg(
                    name="country",
                    type="str",
                    description="ISO-3 country code",
                    example="USA",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_unemployment",
            description="OECD harmonised unemployment rate.",
            returns="atomic primitive, unit=dimensionless percent, tier=aggregator",
            args=[
                CapabilityArg(
                    name="country",
                    type="str",
                    description="ISO-3 country code",
                    example="GBR",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_health_spending",
            description="OECD health expenditure for a country.",
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="country",
                    type="str",
                    description="ISO-3 country code",
                    example="USA",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_value_added_by_sector",
            description="OECD gross value added by NACE sector (NAMAIN10).",
            returns="atomic primitive, unit=currency, tier=aggregator",
            args=[
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(
                    name="activity",
                    type="str",
                    description="NACE Rev.2 activity code",
                    example="D",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_household_consumption",
            description="OECD household final consumption by COICOP purpose (NAMAIN1).",
            returns="atomic primitive, unit=currency, tier=aggregator",
            args=[
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(
                    name="coicop", type="str", description="COICOP purpose code", example="_T"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_employment_by_sector",
            description="OECD employment by NACE sector (NAMAIN10).",
            returns="atomic primitive, unit=count people, tier=aggregator",
            args=[
                CapabilityArg(
                    name="activity",
                    type="str",
                    description="NACE Rev.2 activity code",
                    example="J",
                ),
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_ict_business_adoption",
            description="OECD ICT access and use by businesses (Going Digital).",
            returns="atomic primitive, unit=dimensionless percent, tier=aggregator",
            args=[
                CapabilityArg(
                    name="indicator", type="str", description="ICT indicator code", example="_T"
                ),
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_ict_household_adoption",
            description="OECD ICT access and use by households / individuals.",
            returns="atomic primitive, unit=dimensionless percent, tier=aggregator",
            args=[
                CapabilityArg(
                    name="indicator", type="str", description="ICT indicator code", example="_T"
                ),
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_business_demography",
            description="OECD business demography (enterprise births/deaths/active).",
            returns="OECDBusinessStat tuples, tier=aggregator",
            args=[
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(
                    name="activity",
                    type="str",
                    description="NACE Rev.2 activity code",
                    example="_T",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2021"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="oecd",
            method="get_patents",
            description="OECD patent counts by IPC technology class.",
            returns="atomic primitive, unit=count, tier=aggregator",
            args=[
                CapabilityArg(
                    name="ref_area", type="str", description="ISO-3 country code", example="USA"
                ),
                CapabilityArg(
                    name="ipc_class", type="str", description="IPC class code", example="_T"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2021"),
            ],
            source_tier="aggregator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
