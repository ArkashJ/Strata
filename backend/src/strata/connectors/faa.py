"""FAA (Federal Aviation Administration) public data client.

Typed wrappers for FAA ArcGIS Feature Services (airports) and the
Airport Status API with disk caching and conversion to Strata
AtomicPrimitive / Source YAML format.

API references:
  - Airports (ArcGIS): https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/US_Airports/FeatureServer/0
  - Airport Status: https://soa.smext.faa.gov/asws/api/airport/status/{code}
No authentication required.
"""

from __future__ import annotations

import hashlib
import json
import math
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


class FAAState(StrEnum):
    """US state / territory postal codes."""

    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"
    PR = "PR"
    GU = "GU"
    VI = "VI"
    AS = "AS"
    MP = "MP"


class FAAAirportType(StrEnum):
    """Airport facility types in the ArcGIS data."""

    AIRPORT = "AIRPORT"
    HELIPORT = "HELIPORT"
    SEAPLANE_BASE = "SEAPLANE BASE"
    ULTRALIGHT = "ULTRALIGHT"
    GLIDERPORT = "GLIDERPORT"
    STOLPORT = "STOLPORT"
    BALLOONPORT = "BALLOONPORT"


class FAAOwnerType(StrEnum):
    """Airport ownership type codes."""

    PUBLIC = "PU"
    PRIVATE = "PR"
    MILITARY = "MA"
    AIR_FORCE = "MR"
    NAVY = "MN"


class FAARegion(StrEnum):
    """FAA regional office codes."""

    ALASKA = "AAL"
    CENTRAL = "ACE"
    EASTERN = "AEA"
    GREAT_LAKES = "AGL"
    NEW_ENGLAND = "ANE"
    NORTHWEST_MOUNTAIN = "ANM"
    SOUTHERN = "ASO"
    SOUTHWEST = "ASW"
    WESTERN_PACIFIC = "AWP"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw API response shapes
# ═══════════════════════════════════════════════════════════════════


class AirportFeatureRaw(TypedDict, total=False):
    """ArcGIS feature attributes from US_Airports FeatureServer."""

    OBJECTID: int
    FAC_NAME: str
    LOCID: str
    CITY: str
    STATE: str
    COUNTY: str
    ELEV: float
    LATITUDE: float
    LONGITUDE: float
    FAC_TYPE: str
    OWNER_TYPE: str
    PASSENGERS: int
    OPERATIONS: int
    REGION: str


class AirportStatusRaw(TypedDict, total=False):
    """Airport Status API response shape."""

    Name: str
    City: str
    State: str
    IATA: str
    ICAO: str
    Delay: bool
    Status: list[dict[str, str]]
    Weather: dict[str, Any]


class FeatureQueryResponseRaw(TypedDict, total=False):
    """ArcGIS FeatureServer query response envelope."""

    objectIdFieldName: str
    fields: list[dict[str, Any]]
    features: list[dict[str, Any]]
    exceededTransferLimit: bool


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Airport:
    """Normalized airport record from the ArcGIS feature layer."""

    fac_name: str
    loc_id: str
    city: str
    state: str
    county: str
    elevation: float
    latitude: float
    longitude: float
    airport_type: str
    owner_type: str
    passengers: int
    operations: int
    region: str


@dataclass(frozen=True, slots=True)
class AirportStatus:
    """Real-time status for a single airport."""

    name: str
    city: str
    state: str
    iata: str
    icao: str
    delay: bool
    reason: str
    delay_type: str


@dataclass(frozen=True, slots=True)
class AirportSummary:
    """Aggregate statistics for a state or region."""

    state: str
    count: int
    total_passengers: int
    total_operations: int


@dataclass(frozen=True, slots=True)
class FAAResponse:
    """Standard return type for every FAA client call."""

    kind: str
    airports: tuple[Airport, ...] = ()
    statuses: tuple[AirportStatus, ...] = ()
    summaries: tuple[AirportSummary, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_airport(attrs: dict[str, Any]) -> Airport:
    """Parse ArcGIS feature attributes into an Airport dataclass."""
    return Airport(
        fac_name=str(attrs.get("FAC_NAME", "")),
        loc_id=str(attrs.get("LOCID", "")),
        city=str(attrs.get("CITY", "")),
        state=str(attrs.get("STATE", "")),
        county=str(attrs.get("COUNTY", "")),
        elevation=float(attrs.get("ELEV", 0) or 0),
        latitude=float(attrs.get("LATITUDE", 0) or 0),
        longitude=float(attrs.get("LONGITUDE", 0) or 0),
        airport_type=str(attrs.get("FAC_TYPE", "")),
        owner_type=str(attrs.get("OWNER_TYPE", "")),
        passengers=int(attrs.get("PASSENGERS", 0) or 0),
        operations=int(attrs.get("OPERATIONS", 0) or 0),
        region=str(attrs.get("REGION", "")),
    )


def _parse_airport_status(raw: dict[str, Any]) -> AirportStatus:
    """Parse the airport status API response."""
    statuses: list[dict[str, str]] = raw.get("Status", [])
    reason = ""
    delay_type = ""
    if statuses:
        first: dict[str, str] = statuses[0]
        reason = str(first.get("Reason", ""))
        delay_type = str(first.get("Type", ""))
    return AirportStatus(
        name=str(raw.get("Name", "")),
        city=str(raw.get("City", "")),
        state=str(raw.get("State", "")),
        iata=str(raw.get("IATA", "")),
        icao=str(raw.get("ICAO", "")),
        delay=bool(raw.get("Delay", False)),
        reason=reason,
        delay_type=delay_type,
    )


def _parse_feature_response(body: dict[str, Any]) -> tuple[tuple[Airport, ...], bool]:
    """Parse ArcGIS query response. Returns (airports, exceeded_limit)."""
    features: list[dict[str, Any]] = body.get("features", [])
    airports = tuple(
        _parse_airport(cast(dict[str, Any], f.get("attributes", {}))) for f in features
    )
    exceeded: bool = body.get("exceededTransferLimit", False)
    return airports, exceeded


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
        return self._dir / f"faa_{key}.json"

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
        for f in self._dir.glob("faa_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_ARCGIS_BASE = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services"
    "/US_Airports/FeatureServer/0/query"
)
_STATUS_BASE = "https://soa.smext.faa.gov/asws/api/airport/status"

_DEFAULT_OUT_FIELDS = (
    "FAC_NAME,LOCID,CITY,STATE,COUNTY,ELEV,LATITUDE,LONGITUDE,"
    "FAC_TYPE,OWNER_TYPE,PASSENGERS,OPERATIONS,REGION"
)


class FAAClientError(RuntimeError):
    """Raised on FAA API errors or client-side validation failures."""


class FAAClient:
    """Typed client for FAA public airport data.

    Usage::

        client = FAAClient()
        resp = client.get_airports(state="CA", limit=50)
        for a in resp.airports:
            print(a.fac_name, a.passengers)

        status = client.get_airport_status("SFO")
        for s in status.statuses:
            print(s.iata, s.delay, s.reason)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "faa"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FAAClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _arcgis_query(
        self,
        where: str = "1=1",
        out_fields: str = _DEFAULT_OUT_FIELDS,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
    ) -> FAAResponse:
        """Execute an ArcGIS FeatureServer query and return parsed airports."""
        params: dict[str, str] = {
            "where": where,
            "outFields": out_fields,
            "f": "json",
            "resultRecordCount": str(limit),
            "resultOffset": str(offset),
        }
        if order_by is not None:
            params["orderByFields"] = order_by

        ck = self._cache_key(_ARCGIS_BASE, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            airports, _ = _parse_feature_response(data)
            return FAAResponse(
                kind="airports",
                airports=airports,
                total=len(airports),
                cached=True,
                cache_age_seconds=round(age, 1),
            )

        http_resp = self._http.get(_ARCGIS_BASE, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise FAAClientError(f"ArcGIS returned unexpected type: {type(body).__name__}")
        body_dict = cast(dict[str, Any], body)

        if "error" in body_dict:
            err: dict[str, Any] = body_dict["error"]
            raise FAAClientError(
                f"ArcGIS error {err.get('code', '?')}: {err.get('message', 'unknown')}"
            )

        self._cache.put(ck, body_dict)
        airports, _ = _parse_feature_response(body_dict)
        return FAAResponse(
            kind="airports",
            airports=airports,
            total=len(airports),
        )

    def _arcgis_query_all(
        self,
        where: str = "1=1",
        out_fields: str = _DEFAULT_OUT_FIELDS,
        order_by: str | None = None,
        page_size: int = 1000,
    ) -> FAAResponse:
        """Paginate through all results for an ArcGIS query."""
        all_airports: list[Airport] = []
        offset = 0
        any_cached = False
        max_age: float = 0.0

        while True:
            resp = self._arcgis_query(
                where=where,
                out_fields=out_fields,
                limit=page_size,
                offset=offset,
                order_by=order_by,
            )
            all_airports.extend(resp.airports)
            if resp.cached:
                any_cached = True
                max_age = max(max_age, resp.cache_age_seconds)
            if len(resp.airports) < page_size:
                break
            offset += page_size

        return FAAResponse(
            kind="airports",
            airports=tuple(all_airports),
            total=len(all_airports),
            cached=any_cached,
            cache_age_seconds=round(max_age, 1),
        )

    def _status_request(self, airport_code: str) -> FAAResponse:
        """Fetch real-time status for one airport."""
        url = f"{_STATUS_BASE}/{airport_code}"
        params: dict[str, str] = {}

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            status = _parse_airport_status(data)
            return FAAResponse(
                kind="status",
                statuses=(status,),
                total=1,
                cached=True,
                cache_age_seconds=round(age, 1),
            )

        http_resp = self._http.get(url)
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise FAAClientError(
                f"Airport Status API returned unexpected type: {type(body).__name__}"
            )
        body_dict = cast(dict[str, Any], body)

        if "error" in body_dict:
            raise FAAClientError(f"Airport Status API error: {body_dict['error']}")

        self._cache.put(ck, body_dict)
        status = _parse_airport_status(body_dict)
        return FAAResponse(
            kind="status",
            statuses=(status,),
            total=1,
        )

    # ── airport queries ──────────────────────────────────────────

    def get_airports(
        self,
        state: str | None = None,
        airport_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> FAAResponse:
        """Query airports with optional state and type filters.

        Args:
            state: Two-letter state code (e.g. "CA").
            airport_type: FAC_TYPE value (e.g. "AIRPORT", "HELIPORT").
            limit: Max results per request (ArcGIS caps at 2000).
            offset: Pagination offset.
        """
        clauses: list[str] = []
        if state is not None:
            clauses.append(f"STATE='{state}'")
        if airport_type is not None:
            clauses.append(f"FAC_TYPE='{airport_type}'")
        where = " AND ".join(clauses) if clauses else "1=1"
        return self._arcgis_query(where=where, limit=limit, offset=offset)

    def get_airport_by_code(self, loc_id: str) -> FAAResponse:
        """Look up a single airport by its location identifier (e.g. 'LAX')."""
        where = f"LOCID='{loc_id.upper()}'"
        return self._arcgis_query(where=where, limit=1)

    def get_airport_status(self, airport_code: str) -> FAAResponse:
        """Fetch real-time delay/status info for a major airport.

        Args:
            airport_code: IATA code (e.g. "SFO", "JFK", "LAX").
        """
        return self._status_request(airport_code.upper())

    def get_busiest_airports(self, limit: int = 25) -> FAAResponse:
        """Return airports sorted by annual passenger count (descending).

        Args:
            limit: Number of airports to return (default 25).
        """
        return self._arcgis_query(
            where="PASSENGERS>0",
            limit=limit,
            order_by="PASSENGERS DESC",
        )

    def get_airports_by_state(self, state: str) -> FAAResponse:
        """Retrieve all airports in a given state (paginated automatically).

        Args:
            state: Two-letter state code.
        """
        where = f"STATE='{state.upper()}'"
        return self._arcgis_query_all(where=where)

    def get_state_summary(self, state: str) -> FAAResponse:
        """Compute aggregate statistics for airports in a state.

        Args:
            state: Two-letter state code.
        """
        resp = self.get_airports_by_state(state.upper())
        total_passengers = sum(a.passengers for a in resp.airports)
        total_operations = sum(a.operations for a in resp.airports)
        summary = AirportSummary(
            state=state.upper(),
            count=len(resp.airports),
            total_passengers=total_passengers,
            total_operations=total_operations,
        )
        return FAAResponse(
            kind="summary",
            summaries=(summary,),
            airports=resp.airports,
            total=1,
            cached=resp.cached,
            cache_age_seconds=resp.cache_age_seconds,
        )

    def get_all_state_summaries(self) -> FAAResponse:
        """Compute per-state summary for all US states and territories."""
        resp = self._arcgis_query_all(where="1=1")
        by_state: dict[str, list[Airport]] = {}
        for airport in resp.airports:
            by_state.setdefault(airport.state, []).append(airport)

        summaries: list[AirportSummary] = []
        for st, airports in sorted(by_state.items()):
            summaries.append(
                AirportSummary(
                    state=st,
                    count=len(airports),
                    total_passengers=sum(a.passengers for a in airports),
                    total_operations=sum(a.operations for a in airports),
                )
            )
        return FAAResponse(
            kind="summary",
            summaries=tuple(summaries),
            total=len(summaries),
            cached=resp.cached,
            cache_age_seconds=resp.cache_age_seconds,
        )

    def get_commercial_airports(self, state: str | None = None) -> FAAResponse:
        """Return airports with scheduled commercial passenger service.

        Filtered by PASSENGERS > 0 and FAC_TYPE = 'AIRPORT'.
        """
        clauses = ["PASSENGERS>0", "FAC_TYPE='AIRPORT'"]
        if state is not None:
            clauses.append(f"STATE='{state.upper()}'")
        where = " AND ".join(clauses)
        return self._arcgis_query_all(where=where, order_by="PASSENGERS DESC")

    def get_general_aviation_airports(
        self,
        state: str | None = None,
    ) -> FAAResponse:
        """Return general-aviation airports (public, no significant scheduled service).

        Filtered by OWNER_TYPE='PU' and PASSENGERS=0 (or null) and FAC_TYPE='AIRPORT'.
        """
        clauses = [
            "FAC_TYPE='AIRPORT'",
            "OWNER_TYPE='PU'",
            "(PASSENGERS=0 OR PASSENGERS IS NULL)",
        ]
        if state is not None:
            clauses.append(f"STATE='{state.upper()}'")
        where = " AND ".join(clauses)
        return self._arcgis_query_all(where=where)

    def get_heliports(self, state: str | None = None) -> FAAResponse:
        """Return heliports, optionally filtered by state."""
        clauses = ["FAC_TYPE='HELIPORT'"]
        if state is not None:
            clauses.append(f"STATE='{state.upper()}'")
        where = " AND ".join(clauses)
        return self._arcgis_query_all(where=where)

    def get_airports_by_region(self, region: str) -> FAAResponse:
        """Return all airports in an FAA region.

        Args:
            region: FAA region code (e.g. "AWP" for Western-Pacific).
        """
        where = f"REGION='{region.upper()}'"
        return self._arcgis_query_all(where=where)

    def get_airport_count(
        self,
        state: str | None = None,
        airport_type: str | None = None,
    ) -> FAAResponse:
        """Return count of airports matching the given filters.

        Uses the returnCountOnly ArcGIS parameter for efficiency, but
        falls back to a full query to stay within the cache/parse pattern.
        """
        clauses: list[str] = []
        if state is not None:
            clauses.append(f"STATE='{state.upper()}'")
        if airport_type is not None:
            clauses.append(f"FAC_TYPE='{airport_type}'")
        where = " AND ".join(clauses) if clauses else "1=1"

        params: dict[str, str] = {
            "where": where,
            "returnCountOnly": "true",
            "f": "json",
        }

        ck = self._cache_key(_ARCGIS_BASE, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            count = int(data.get("count", 0))
            return FAAResponse(
                kind="count",
                total=count,
                cached=True,
                cache_age_seconds=round(age, 1),
            )

        http_resp = self._http.get(_ARCGIS_BASE, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise FAAClientError(f"ArcGIS returned unexpected type: {type(body).__name__}")
        body_dict = cast(dict[str, Any], body)
        self._cache.put(ck, body_dict)
        count = int(body_dict.get("count", 0))
        return FAAResponse(kind="count", total=count)

    def get_total_passengers(self, state: str | None = None) -> FAAResponse:
        """Sum annual passenger counts for airports in a state (or all US).

        Returns an FAAResponse with the total in ``total`` and a single
        AirportSummary in ``summaries``.
        """
        if state is not None:
            return self.get_state_summary(state)
        # Nationwide: need all airports
        resp = self._arcgis_query_all(where="PASSENGERS>0")
        total_pax = sum(a.passengers for a in resp.airports)
        summary = AirportSummary(
            state="US",
            count=len(resp.airports),
            total_passengers=total_pax,
            total_operations=sum(a.operations for a in resp.airports),
        )
        return FAAResponse(
            kind="summary",
            summaries=(summary,),
            total=total_pax,
            cached=resp.cached,
            cache_age_seconds=resp.cache_age_seconds,
        )

    def get_airports_near(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 50.0,
        limit: int = 100,
    ) -> FAAResponse:
        """Find airports within a radius of a geographic point.

        Uses a bounding-box filter (fast) then post-filters by Haversine
        distance (accurate). ArcGIS geometry queries are not reliable on
        this layer, so we do the math client-side.

        Args:
            lat: Center latitude in decimal degrees.
            lon: Center longitude in decimal degrees.
            radius_miles: Search radius in statute miles.
            limit: Maximum airports to return.
        """
        # ~1 degree latitude = 69 miles; longitude varies by cos(lat)
        lat_delta = radius_miles / 69.0
        lon_delta = radius_miles / (69.0 * max(math.cos(math.radians(lat)), 0.01))

        where = (
            f"LATITUDE>{lat - lat_delta} AND LATITUDE<{lat + lat_delta} "
            f"AND LONGITUDE>{lon - lon_delta} AND LONGITUDE<{lon + lon_delta}"
        )
        resp = self._arcgis_query_all(where=where)

        # Post-filter by actual Haversine distance
        filtered: list[Airport] = []
        for airport in resp.airports:
            dist = _haversine_miles(lat, lon, airport.latitude, airport.longitude)
            if dist <= radius_miles:
                filtered.append(airport)
        filtered.sort(
            key=lambda a: _haversine_miles(lat, lon, a.latitude, a.longitude),
        )
        result = tuple(filtered[:limit])
        return replace(
            resp,
            airports=result,
            total=len(result),
        )

    def search_airports(
        self,
        name_query: str,
        limit: int = 50,
    ) -> FAAResponse:
        """Search airports by facility name (case-insensitive substring).

        Args:
            name_query: Search string (e.g. "international", "regional").
            limit: Maximum results.
        """
        where = f"UPPER(FAC_NAME) LIKE '%{name_query.upper()}%'"
        return self._arcgis_query(where=where, limit=limit, order_by="PASSENGERS DESC")

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached FAA responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Haversine helper
# ═══════════════════════════════════════════════════════════════════


def _haversine_miles(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Great-circle distance between two points in statute miles."""
    r = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _snapshot_hash(data: dict[str, Any]) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def airport_to_primitive_yaml(
    airport: Airport,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/US_Airports/FeatureServer/0",
    geo_level: str = "state",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "count",
    unit_denominator: str | None = None,
    distribution_shape: str = "point",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert an Airport record to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    sha = _snapshot_hash(
        {
            "loc_id": airport.loc_id,
            "fac_name": airport.fac_name,
            "state": airport.state,
            "passengers": airport.passengers,
            "operations": airport.operations,
        }
    )
    source_slug = f"faa-airport-{airport.loc_id.lower()}"

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": airport.passengers,
        "unit": unit,
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": [airport.state]},
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


def airport_to_source_yaml(
    airport: Airport,
    *,
    source_url: str = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/US_Airports/FeatureServer/0",
    description: str = "",
) -> dict[str, Any]:
    """Convert an Airport record to a Strata source_registry YAML dict."""
    sha = _snapshot_hash(
        {
            "loc_id": airport.loc_id,
            "fac_name": airport.fac_name,
            "state": airport.state,
            "passengers": airport.passengers,
            "operations": airport.operations,
        }
    )
    source_slug = f"faa-airport-{airport.loc_id.lower()}"

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or f"FAA airport data for {airport.fac_name} ({airport.loc_id}), "
        f"{airport.city}, {airport.state}.",
    }


def passenger_count_to_primitive_yaml(
    summary: AirportSummary,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/US_Airports/FeatureServer/0",
    geo_level: str = "state",
    geo_perspective: str = "demand",
    distribution_shape: str = "point",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert an AirportSummary to a Strata AtomicPrimitive YAML dict.

    The value field is ``total_passengers``. Useful for sizing air-travel,
    airport services, and aviation-adjacent TAMs.
    """
    sha = _snapshot_hash(
        {
            "state": summary.state,
            "count": summary.count,
            "total_passengers": summary.total_passengers,
            "total_operations": summary.total_operations,
        }
    )
    source_slug = f"faa-passengers-{summary.state.lower()}"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": summary.total_passengers,
        "unit": {"kind": "flow", "dimension": "people", "denominator": "year"},
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": [summary.state]},
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


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="faa",
            method="get_total_passengers",
            description="Total enplaned passengers across US commercial airports.",
            returns="atomic primitive, unit=count people, tier=regulator",
            args=[
                CapabilityArg(name="year", type="int", description="Calendar year", example="2023"),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="faa",
            method="get_airport_count",
            description="Total count of US airports of a given type.",
            returns="atomic primitive, unit=count, tier=regulator",
            args=[
                CapabilityArg(
                    name="airport_type",
                    type="str",
                    description="Airport type (commercial/general_aviation/heliport)",
                    example="commercial",
                ),
            ],
            source_tier="regulator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
