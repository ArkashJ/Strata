"""UN Comtrade API v1 client.

Typed wrappers for the UN Comtrade International Trade Statistics API
with disk caching and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://comtradeapi.un.org/
Free tier: 100 req/hr, 250 req/day. Subscription key required for full access.
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

from strata.config import settings

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class ComtradeFlowCode(StrEnum):
    """Trade flow direction."""

    IMPORTS = "M"
    EXPORTS = "X"
    BOTH = "MX"


class ComtradeFrequency(StrEnum):
    """Data frequency."""

    ANNUAL = "A"
    MONTHLY = "M"


class ComtradeReporter(StrEnum):
    """Common reporter country codes (ISO numeric)."""

    USA = "842"
    CHN = "156"
    DEU = "276"
    JPN = "392"
    GBR = "826"
    FRA = "251"
    IND = "356"
    KOR = "410"
    CAN = "124"
    AUS = "036"
    BRA = "076"
    MEX = "484"
    ITA = "380"
    NLD = "528"
    SGP = "702"
    CHE = "756"
    ESP = "724"
    TWN = "490"
    THA = "764"
    VNM = "704"


class ComtradeHSChapter(StrEnum):
    """Harmonized System commodity chapter codes."""

    TOTAL = "TOTAL"
    # Live animals (01-05)
    LIVE_ANIMALS = "01"
    MEAT = "02"
    FISH = "03"
    DAIRY_EGGS = "04"
    ANIMAL_PRODUCTS_OTHER = "05"
    # Vegetable products (06-14)
    LIVE_TREES = "06"
    VEGETABLES = "07"
    FRUITS_NUTS = "08"
    COFFEE_TEA = "09"
    CEREALS = "10"
    MILLING_PRODUCTS = "11"
    OIL_SEEDS = "12"
    LACS_GUMS = "13"
    VEGETABLE_PLAITING = "14"
    # Fats/oils (15)
    FATS_OILS = "15"
    # Food preparations (16-24)
    MEAT_PREPARATIONS = "16"
    SUGARS = "17"
    COCOA = "18"
    CEREAL_PREPARATIONS = "19"
    VEGETABLE_PREPARATIONS = "20"
    MISC_FOOD = "21"
    BEVERAGES = "22"
    RESIDUES_ANIMAL_FEED = "23"
    TOBACCO = "24"
    # Minerals (25-27)
    SALT_SULPHUR_EARTH = "25"
    ORES_SLAG = "26"
    MINERAL_FUELS = "27"
    # Chemicals (28-38)
    INORGANIC_CHEMICALS = "28"
    ORGANIC_CHEMICALS = "29"
    PHARMA = "30"
    FERTILIZERS = "31"
    TANNING_EXTRACTS = "32"
    ESSENTIAL_OILS = "33"
    SOAP_WAX = "34"
    ALBUMINOIDAL = "35"
    EXPLOSIVES = "36"
    PHOTO_CHEMICALS = "37"
    MISC_CHEMICALS = "38"
    # Plastics/rubber (39-40)
    PLASTICS = "39"
    RUBBER = "40"
    # Leather (41-43)
    HIDES_SKINS = "41"
    LEATHER_ARTICLES = "42"
    FURSKINS = "43"
    # Wood (44-46)
    WOOD = "44"
    CORK = "45"
    STRAW_BASKETWARE = "46"
    # Paper (47-49)
    PULP = "47"
    PAPER = "48"
    PRINTED_BOOKS = "49"
    # Textiles (50-63)
    SILK = "50"
    WOOL = "51"
    COTTON = "52"
    VEGETABLE_FIBERS = "53"
    MANMADE_FILAMENTS = "54"
    MANMADE_STAPLE = "55"
    WADDING = "56"
    CARPETS = "57"
    SPECIAL_WOVEN = "58"
    COATED_FABRICS = "59"
    KNITTED_FABRICS = "60"
    APPAREL_KNITTED = "61"
    APPAREL_NOT_KNITTED = "62"
    TEXTILE_ARTICLES = "63"
    # Footwear/headgear (64-67)
    FOOTWEAR = "64"
    HEADGEAR = "65"
    UMBRELLAS = "66"
    FEATHERS = "67"
    # Stone/glass (68-70)
    STONE_CEMENT = "68"
    CERAMICS = "69"
    GLASS = "70"
    # Gems (71)
    GEMS_PRECIOUS_METALS = "71"
    # Metals (72-83)
    IRON_STEEL = "72"
    IRON_STEEL_ARTICLES = "73"
    COPPER = "74"
    NICKEL = "75"
    ALUMINIUM = "76"
    LEAD = "78"
    ZINC = "79"
    TIN = "80"
    BASE_METALS_OTHER = "81"
    TOOLS = "82"
    MISC_BASE_METALS = "83"
    # Machinery/electronics (84-85)
    MACHINERY = "84"
    ELECTRICAL_EQUIPMENT = "85"
    # Transport (86-89)
    RAILWAY = "86"
    VEHICLES = "87"
    AIRCRAFT = "88"
    SHIPS = "89"
    # Instruments (90-92)
    OPTICAL_INSTRUMENTS = "90"
    CLOCKS = "91"
    MUSICAL_INSTRUMENTS = "92"
    # Arms (93)
    ARMS_AMMUNITION = "93"
    # Miscellaneous (94-96)
    FURNITURE = "94"
    TOYS_GAMES = "95"
    MISC_MANUFACTURED = "96"
    # Art (97)
    ART_ANTIQUES = "97"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw UN Comtrade JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class TradeRecordRaw(TypedDict, total=False):
    typeCode: str
    freqCode: str
    refPeriodId: int
    refYear: int
    reporterCode: int
    reporterISO: str
    reporterDesc: str
    flowCode: str
    flowDesc: str
    partnerCode: int
    partnerISO: str
    partnerDesc: str
    partner2Code: int
    cmdCode: str
    cmdDesc: str
    aggrLevel: int
    isLeaf: bool
    customsCode: str
    mosCode: str
    primaryValue: float | None
    netWgt: float | None
    grossWgt: float | None
    qty: float | None
    qtyUnitCode: int
    qtyUnitAbbr: str
    cifvalue: float | None
    fobvalue: float | None


class TradeResponseRaw(TypedDict, total=False):
    elapsedTime: str
    count: int
    data: list[TradeRecordRaw]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """A single trade data point from UN Comtrade."""

    reporter_code: int
    reporter_iso: str
    reporter_name: str
    partner_code: int
    partner_iso: str
    partner_name: str
    flow_code: str
    flow_desc: str
    period: int
    commodity_code: str
    commodity_desc: str
    primary_value: float | None
    net_weight: float | None
    fob_value: float | None
    cif_value: float | None


@dataclass(frozen=True, slots=True)
class ServiceTradeRecord:
    """A single services-trade data point (EBOPS classification)."""

    reporter_code: int
    reporter_iso: str
    reporter_name: str
    partner_code: int
    flow_code: str
    flow_desc: str
    period: int
    service_code: str
    service_desc: str
    primary_value: float | None


@dataclass(frozen=True, slots=True)
class TradePartnerSummary:
    """Aggregated trade summary for a single partner."""

    partner_iso: str
    partner_name: str
    export_value: float | None
    import_value: float | None


# ═══════════════════════════════════════════════════════════════════
# Standard return type
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ComtradeResponse:
    """Standard return type for every Comtrade client call."""

    kind: str
    records: tuple[TradeRecord, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_trade_record(raw: dict[str, Any]) -> TradeRecord:
    """Parse a single raw trade data element into a TradeRecord."""
    raw_primary: object = raw.get("primaryValue")
    primary_value: float | None = None
    if raw_primary is not None:
        try:
            primary_value = float(raw_primary)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            primary_value = None

    raw_net: object = raw.get("netWgt")
    net_weight: float | None = None
    if raw_net is not None:
        try:
            net_weight = float(raw_net)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            net_weight = None

    raw_fob: object = raw.get("fobvalue")
    fob_value: float | None = None
    if raw_fob is not None:
        try:
            fob_value = float(raw_fob)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            fob_value = None

    raw_cif: object = raw.get("cifvalue")
    cif_value: float | None = None
    if raw_cif is not None:
        try:
            cif_value = float(raw_cif)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            cif_value = None

    return TradeRecord(
        reporter_code=int(raw.get("reporterCode", 0)),
        reporter_iso=str(raw.get("reporterISO", "")),
        reporter_name=str(raw.get("reporterDesc", "")),
        partner_code=int(raw.get("partnerCode", 0)),
        partner_iso=str(raw.get("partnerISO", "")),
        partner_name=str(raw.get("partnerDesc", "")),
        flow_code=str(raw.get("flowCode", "")),
        flow_desc=str(raw.get("flowDesc", "")),
        period=int(raw.get("refYear", raw.get("refPeriodId", 0))),
        commodity_code=str(raw.get("cmdCode", "")),
        commodity_desc=str(raw.get("cmdDesc", "")),
        primary_value=primary_value,
        net_weight=net_weight,
        fob_value=fob_value,
        cif_value=cif_value,
    )


def _parse_response(
    body: dict[str, Any],
    *,
    kind: str,
) -> ComtradeResponse:
    """Parse a full Comtrade JSON response into a ComtradeResponse."""
    data_list: list[dict[str, Any]] = body.get("data", [])
    total = int(body.get("count", len(data_list)))
    records = tuple(_parse_trade_record(r) for r in data_list)
    return ComtradeResponse(kind=kind, records=records, total=total)


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
        return self._dir / f"ct_{key}.json"

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
        for f in self._dir.glob("ct_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_ROOT_PUBLIC = "https://comtradeapi.un.org/public/v1/preview"
_ROOT_DATA = "https://comtradeapi.un.org/data/v1/get"
# Back-compat: default commodities · annual · HS path used by older callers.
_BASE_PUBLIC = f"{_ROOT_PUBLIC}/C/A/HS"
_BASE_DATA = f"{_ROOT_DATA}/C/A/HS"


class ComtradeClientError(RuntimeError):
    """Raised on UN Comtrade API errors or client-side validation failures."""


class ComtradeClient:
    """Typed client for the UN Comtrade International Trade Statistics API.

    Usage::

        client = ComtradeClient()
        resp = client.get_trade(
            reporter=ComtradeReporter.USA,
            period=2023,
            flow=ComtradeFlowCode.EXPORTS,
        )
        for rec in resp.records:
            print(rec.period, rec.commodity_desc, rec.primary_value)

    With a subscription key for full access::

        client = ComtradeClient(subscription_key="your-key")
        resp = client.get_total_trade(ComtradeReporter.CHN, 2023)
    """

    def __init__(
        self,
        subscription_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._key = subscription_key or settings.comtrade_api_key
        headers: dict[str, str] = {}
        if self._key:
            headers["Ocp-Apim-Subscription-Key"] = self._key
        self._http = httpx.Client(timeout=timeout, headers=headers, transport=transport)
        default_cache = Path.home() / ".strata" / "cache" / "comtrade"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ComtradeClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _base_url(
        self,
        *,
        type_code: str = "C",
        freq: str = "A",
        classification: str = "HS",
    ) -> str:
        """Build the base URL for a given type/frequency/classification.

        ``type_code``: ``C`` commodities, ``S`` services.
        ``freq``: ``A`` annual, ``M`` monthly.
        ``classification``: ``HS`` (goods) or ``EB`` (services, EBOPS).
        """
        root = _ROOT_DATA if self._key else _ROOT_PUBLIC
        return f"{root}/{type_code}/{freq}/{classification}"

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        params: dict[str, str],
        *,
        kind: str,
        type_code: str = "C",
        freq: str = "A",
        classification: str = "HS",
    ) -> ComtradeResponse:
        url = self._base_url(type_code=type_code, freq=freq, classification=classification)
        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_response(data, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()

        if not isinstance(body, dict):
            raise ComtradeClientError(
                f"Comtrade API returned unexpected type: {type(body).__name__}"
            )

        body_dict = cast(dict[str, Any], body)
        # Check for error responses
        if "statusCode" in body_dict and int(body_dict.get("statusCode", 200)) >= 400:
            msg = str(body_dict.get("message", body_dict.get("statusCode", "")))
            raise ComtradeClientError(f"Comtrade API error: {msg}")

        self._cache.put(ck, body_dict)
        return _parse_response(body_dict, kind=kind)

    # ── core trade data ──────────────────────────────────────────

    def get_trade(
        self,
        reporter: str,
        period: int,
        *,
        partner: str = "0",
        flow: str = ComtradeFlowCode.BOTH,
        commodity: str = ComtradeHSChapter.TOTAL,
        customs_code: str = "C00",
        mot_code: str = "0",
    ) -> ComtradeResponse:
        """Fetch trade data for a reporter/partner/period/flow/commodity combination.

        Args:
            reporter: ISO numeric country code (e.g. "842" for USA).
            period: Year (e.g. 2023).
            partner: Partner country code. "0" = World (default).
            flow: Flow direction — M, X, or MX.
            commodity: HS commodity code (TOTAL, chapter, or 6-digit).
            customs_code: Customs procedure code. "C00" = standard.
            mot_code: Mode of transport. "0" = all.
        """
        params: dict[str, str] = {
            "reporterCode": reporter,
            "partnerCode": partner,
            "period": str(period),
            "flowCode": flow,
            "cmdCode": commodity,
            "customsCode": customs_code,
            "motCode": mot_code,
        }
        return self._request(params, kind="trade")

    # ── convenience shortcuts ────────────────────────────────────

    def get_exports(
        self,
        reporter: str,
        period: int,
        *,
        partner: str = "0",
        commodity: str = ComtradeHSChapter.TOTAL,
    ) -> ComtradeResponse:
        """Fetch export data for a reporter."""
        return self.get_trade(
            reporter,
            period,
            partner=partner,
            flow=ComtradeFlowCode.EXPORTS,
            commodity=commodity,
        )

    def get_imports(
        self,
        reporter: str,
        period: int,
        *,
        partner: str = "0",
        commodity: str = ComtradeHSChapter.TOTAL,
    ) -> ComtradeResponse:
        """Fetch import data for a reporter."""
        return self.get_trade(
            reporter,
            period,
            partner=partner,
            flow=ComtradeFlowCode.IMPORTS,
            commodity=commodity,
        )

    def get_bilateral_trade(
        self,
        reporter: str,
        partner: str,
        period: int,
    ) -> ComtradeResponse:
        """Fetch bilateral trade (imports + exports) between two countries."""
        return self.get_trade(
            reporter,
            period,
            partner=partner,
            flow=ComtradeFlowCode.BOTH,
            commodity=ComtradeHSChapter.TOTAL,
        )

    def get_total_trade(
        self,
        reporter: str,
        period: int,
    ) -> ComtradeResponse:
        """Fetch total trade (imports + exports) with the world."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=ComtradeFlowCode.BOTH,
            commodity=ComtradeHSChapter.TOTAL,
        )

    def get_commodity_exports(
        self,
        reporter: str,
        period: int,
        commodity_code: str,
    ) -> ComtradeResponse:
        """Fetch exports for a specific HS commodity code."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=ComtradeFlowCode.EXPORTS,
            commodity=commodity_code,
        )

    def get_commodity_imports(
        self,
        reporter: str,
        period: int,
        commodity_code: str,
    ) -> ComtradeResponse:
        """Fetch imports for a specific HS commodity code."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=ComtradeFlowCode.IMPORTS,
            commodity=commodity_code,
        )

    def get_top_partners(
        self,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.EXPORTS,
        limit: int = 10,
    ) -> ComtradeResponse:
        """Fetch top trading partners for a reporter/flow, sorted by value.

        Note: The API returns data for all partners with code 0 (World)
        excluded. This method fetches all partner data (partner=0 excluded
        from results) and returns the top N by primary_value.
        We request with partnerCode omitted or set to empty to get
        per-partner breakdown, but the preview API may limit results.
        For full partner breakdowns a subscription key is recommended.
        """
        # Fetch bilateral with all partners — use the core request directly
        # so we can control the partner parameter for breakdown.
        # With the public preview we get limited results; subscription gives all.
        params: dict[str, str] = {
            "reporterCode": reporter,
            "period": str(period),
            "flowCode": flow,
            "cmdCode": ComtradeHSChapter.TOTAL,
            "customsCode": "C00",
            "motCode": "0",
        }
        resp = self._request(params, kind="trade")
        # Filter out World aggregate (partnerCode=0) and sort by value
        non_world = [r for r in resp.records if r.partner_code != 0]
        sorted_recs = sorted(
            non_world,
            key=lambda r: r.primary_value or 0.0,
            reverse=True,
        )
        limited = tuple(sorted_recs[:limit])
        return replace(resp, records=limited, total=len(limited))

    def get_trade_balance(
        self,
        reporter: str,
        period: int,
        *,
        partner: str = "0",
    ) -> ComtradeResponse:
        """Fetch both imports and exports to compute trade balance.

        Returns a ComtradeResponse with both import and export records.
        The caller can compute balance as:
            exports.primary_value - imports.primary_value
        """
        return self.get_trade(
            reporter,
            period,
            partner=partner,
            flow=ComtradeFlowCode.BOTH,
            commodity=ComtradeHSChapter.TOTAL,
        )

    def get_multi_year(
        self,
        reporter: str,
        periods: list[int],
        *,
        partner: str = "0",
        flow: str = ComtradeFlowCode.BOTH,
        commodity: str = ComtradeHSChapter.TOTAL,
    ) -> ComtradeResponse:
        """Fetch trade data across multiple years and merge results.

        Args:
            reporter: ISO numeric country code.
            periods: List of years (e.g. [2020, 2021, 2022, 2023]).
            partner: Partner country code.
            flow: Flow direction.
            commodity: HS commodity code.
        """
        all_records: list[TradeRecord] = []
        any_cached = False
        max_age = 0.0

        for period in periods:
            resp = self.get_trade(
                reporter,
                period,
                partner=partner,
                flow=flow,
                commodity=commodity,
            )
            all_records.extend(resp.records)
            if resp.cached:
                any_cached = True
                max_age = max(max_age, resp.cache_age_seconds)

        return ComtradeResponse(
            kind="trade_multi_year",
            records=tuple(all_records),
            total=len(all_records),
            cached=any_cached,
            cache_age_seconds=round(max_age, 1),
        )

    def get_multi_reporter(
        self,
        reporters: list[str],
        period: int,
        *,
        flow: str = ComtradeFlowCode.BOTH,
        commodity: str = ComtradeHSChapter.TOTAL,
    ) -> ComtradeResponse:
        """Compare trade data across multiple reporter countries.

        Args:
            reporters: List of ISO numeric country codes.
            period: Year.
            flow: Flow direction.
            commodity: HS commodity code.
        """
        all_records: list[TradeRecord] = []
        any_cached = False
        max_age = 0.0

        for reporter in reporters:
            resp = self.get_trade(
                reporter,
                period,
                partner="0",
                flow=flow,
                commodity=commodity,
            )
            all_records.extend(resp.records)
            if resp.cached:
                any_cached = True
                max_age = max(max_age, resp.cache_age_seconds)

        return ComtradeResponse(
            kind="trade_multi_reporter",
            records=tuple(all_records),
            total=len(all_records),
            cached=any_cached,
            cache_age_seconds=round(max_age, 1),
        )

    def get_chapter_breakdown(
        self,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.EXPORTS,
    ) -> ComtradeResponse:
        """Fetch trade breakdown by HS chapter for a reporter.

        Requests data without specifying a commodity code to get
        the chapter-level aggregation from the API.
        """
        params: dict[str, str] = {
            "reporterCode": reporter,
            "partnerCode": "0",
            "period": str(period),
            "flowCode": flow,
            "customsCode": "C00",
            "motCode": "0",
        }
        resp = self._request(params, kind="trade_chapter_breakdown")
        # Filter to chapter-level aggregation (aggrLevel 2 in raw data)
        # or records with 2-digit commodity codes
        chapter_records = tuple(
            r for r in resp.records if len(r.commodity_code) == 2 or r.commodity_code == "TOTAL"
        )
        return replace(resp, records=chapter_records, total=len(chapter_records))

    # ── sector shortcuts ─────────────────────────────────────────

    def get_tech_exports(
        self,
        reporter: str,
        period: int,
    ) -> ComtradeResponse:
        """Fetch HS 84 (machinery) + HS 85 (electrical equipment) exports.

        These chapters cover computers, semiconductors, telecom equipment,
        and other tech goods — useful for tech-sector TAM sizing.
        """
        records: list[TradeRecord] = []
        any_cached = False
        max_age = 0.0

        for chapter in (ComtradeHSChapter.MACHINERY, ComtradeHSChapter.ELECTRICAL_EQUIPMENT):
            resp = self.get_trade(
                reporter,
                period,
                partner="0",
                flow=ComtradeFlowCode.EXPORTS,
                commodity=chapter,
            )
            records.extend(resp.records)
            if resp.cached:
                any_cached = True
                max_age = max(max_age, resp.cache_age_seconds)

        return ComtradeResponse(
            kind="trade_tech_exports",
            records=tuple(records),
            total=len(records),
            cached=any_cached,
            cache_age_seconds=round(max_age, 1),
        )

    def get_energy_trade(
        self,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.BOTH,
    ) -> ComtradeResponse:
        """Fetch HS 27 (mineral fuels, oils, distillation products) trade."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=flow,
            commodity=ComtradeHSChapter.MINERAL_FUELS,
        )

    def get_pharma_trade(
        self,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.BOTH,
    ) -> ComtradeResponse:
        """Fetch HS 30 (pharmaceutical products) trade."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=flow,
            commodity=ComtradeHSChapter.PHARMA,
        )

    # ── HS6 granularity ──────────────────────────────────────────

    def get_hs6_trade(
        self,
        cmd_code_hs6: str,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.IMPORTS,
        partner: str = "0",
    ) -> ComtradeResponse:
        """Fetch trade for a specific 6-digit HS commodity code.

        Args:
            cmd_code_hs6: 6-digit HS commodity code (e.g. "854231").
            reporter: ISO numeric reporter code.
            period: Year.
            flow: Flow direction (default imports).
            partner: Partner country code ("0" = World).
        """
        return self.get_trade(
            reporter,
            period,
            partner=partner,
            flow=flow,
            commodity=cmd_code_hs6,
        )

    def get_world_imports(
        self,
        cmd_code: str,
        period: int,
        *,
        reporter: str = "0",
    ) -> ComtradeResponse:
        """Fetch world-aggregate imports for a commodity.

        Uses the World reporter (``reporterCode=0``) and World partner so the
        result is the global import value for the commodity.

        Args:
            cmd_code: HS commodity code (TOTAL, chapter, or HS6).
            period: Year.
            reporter: Reporter code; ``"0"`` (World) by default.
        """
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=ComtradeFlowCode.IMPORTS,
            commodity=cmd_code,
        )

    def get_world_exports(
        self,
        cmd_code: str,
        period: int,
        *,
        reporter: str = "0",
    ) -> ComtradeResponse:
        """Fetch world-aggregate exports for a commodity (mirror of imports)."""
        return self.get_trade(
            reporter,
            period,
            partner="0",
            flow=ComtradeFlowCode.EXPORTS,
            commodity=cmd_code,
        )

    # ── monthly frequency ────────────────────────────────────────

    def get_monthly_trade(
        self,
        reporter: str,
        period_range: list[str],
        *,
        partner: str = "0",
        flow: str = ComtradeFlowCode.BOTH,
        commodity: str = ComtradeHSChapter.TOTAL,
    ) -> ComtradeResponse:
        """Fetch monthly trade data for one or more YYYYMM periods.

        Threads the monthly frequency (``ComtradeFrequency.MONTHLY``) into the
        request path.

        Args:
            reporter: ISO numeric reporter code.
            period_range: List of ``YYYYMM`` strings (e.g. ["202301", "202302"]).
            partner: Partner country code.
            flow: Flow direction.
            commodity: HS commodity code.
        """
        params: dict[str, str] = {
            "reporterCode": reporter,
            "partnerCode": partner,
            "period": ",".join(period_range),
            "flowCode": flow,
            "cmdCode": commodity,
            "customsCode": "C00",
            "motCode": "0",
        }
        return self._request(
            params, kind="trade_monthly", freq=ComtradeFrequency.MONTHLY, classification="HS"
        )

    # ── services trade (EBOPS) ────────────────────────────────────

    def get_services_trade(
        self,
        eb_code: str,
        reporter: str,
        period: int,
        *,
        partner: str = "0",
        flow: str = ComtradeFlowCode.BOTH,
    ) -> tuple[ServiceTradeRecord, ...]:
        """Fetch services trade by EBOPS service code (/S/A/EB endpoint).

        Returns ``ServiceTradeRecord`` tuples.

        Args:
            eb_code: EBOPS service classification code (e.g. "SOX" computer
                services). ``TOTAL`` for all services.
            reporter: ISO numeric reporter code.
            period: Year.
            partner: Partner country code.
            flow: Flow direction.
        """
        params: dict[str, str] = {
            "reporterCode": reporter,
            "partnerCode": partner,
            "period": str(period),
            "flowCode": flow,
            "cmdCode": eb_code,
        }
        resp = self._request(params, kind="services", type_code="S", freq="A", classification="EB")
        # Re-parse the cached/fresh body would lose service-specific fields; the
        # generic TradeRecord already captured the shared columns, so map across.
        return tuple(
            ServiceTradeRecord(
                reporter_code=r.reporter_code,
                reporter_iso=r.reporter_iso,
                reporter_name=r.reporter_name,
                partner_code=r.partner_code,
                flow_code=r.flow_code,
                flow_desc=r.flow_desc,
                period=r.period,
                service_code=r.commodity_code,
                service_desc=r.commodity_desc,
                primary_value=r.primary_value,
            )
            for r in resp.records
        )

    # ── derived metrics ──────────────────────────────────────────

    def get_unit_price(
        self,
        reporter: str,
        period: int,
        commodity: str,
        *,
        flow: str = ComtradeFlowCode.IMPORTS,
        partner: str = "0",
    ) -> float | None:
        """Compute implied unit price (value ÷ net weight) for a commodity.

        Returns ``None`` when value or quantity is missing/zero.

        Args:
            reporter: ISO numeric reporter code.
            period: Year.
            commodity: HS commodity code.
            flow: Flow direction.
            partner: Partner country code.
        """
        resp = self.get_trade(reporter, period, partner=partner, flow=flow, commodity=commodity)
        record = _pick_record(resp.records, flow=flow, year=period)
        value = record.primary_value
        qty = record.net_weight
        if value is None or qty is None or qty == 0.0:
            return None
        return value / qty

    def get_reexports(
        self,
        reporter: str,
        period: int,
        *,
        flow: str = ComtradeFlowCode.EXPORTS,
        commodity: str = ComtradeHSChapter.TOTAL,
        partner: str = "0",
    ) -> ComtradeResponse:
        """Fetch re-export / re-import flows via a non-standard customs code.

        Re-exports use customs procedure code ``C02`` (vs ``C00`` for normal
        domestic trade). Pass ``flow=ComtradeFlowCode.IMPORTS`` for re-imports.

        Args:
            reporter: ISO numeric reporter code.
            period: Year.
            flow: Flow direction (exports → re-exports).
            commodity: HS commodity code.
            partner: Partner country code.
        """
        params: dict[str, str] = {
            "reporterCode": reporter,
            "partnerCode": partner,
            "period": str(period),
            "flowCode": flow,
            "cmdCode": commodity,
            "customsCode": "C02",
            "motCode": "0",
        }
        return self._request(params, kind="trade_reexports")

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached Comtrade responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_record(
    records: tuple[TradeRecord, ...],
    *,
    flow: str | None = None,
    year: int | None = None,
) -> TradeRecord:
    """Select the best record from a result set.

    Filters by flow and year if specified, prefers non-null primary_value.
    """
    candidates = list(records)

    if flow is not None:
        flow_filtered = [r for r in candidates if r.flow_code == flow]
        if flow_filtered:
            candidates = flow_filtered

    if year is not None:
        year_filtered = [r for r in candidates if r.period == year]
        if year_filtered:
            candidates = year_filtered

    non_null = [r for r in candidates if r.primary_value is not None]
    if non_null:
        return non_null[0]

    if candidates:
        return candidates[0]

    if records:
        return records[0]

    raise ComtradeClientError("No trade records to convert")


def _snapshot_hash(
    reporter_iso: str,
    partner_iso: str,
    flow_code: str,
    period: int,
    commodity_code: str,
    primary_value: float | None,
) -> str:
    """Content-hash a trade data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "reporter_iso": reporter_iso,
            "partner_iso": partner_iso,
            "flow_code": flow_code,
            "period": period,
            "commodity_code": commodity_code,
            "primary_value": primary_value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def trade_to_primitive_yaml(
    records: tuple[TradeRecord, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    flow: str | None = None,
    year: int | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "flow",
    unit_dimension: str = "currency",
    unit_denominator: str | None = "year",
    unit_currency: str | None = "USD",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert Comtrade trade records to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    record = _pick_record(records, flow=flow, year=year)
    source_slug = (
        f"ct-{record.reporter_iso.lower()}-{record.partner_iso.lower()}"
        f"-{record.flow_code.lower()}-{record.commodity_code.lower()}"
        f"-{record.period}"
    )
    sha = _snapshot_hash(
        record.reporter_iso,
        record.partner_iso,
        record.flow_code,
        record.period,
        record.commodity_code,
        record.primary_value,
    )

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
        "value": record.primary_value,
        "unit": unit,
        "as_of": f"{record.period}-12-31",
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


def trade_to_source_yaml(
    records: tuple[TradeRecord, ...],
    *,
    source_url: str,
    flow: str | None = None,
    year: int | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Convert Comtrade trade records to a Strata source_registry YAML dict."""
    record = _pick_record(records, flow=flow, year=year)
    source_slug = (
        f"ct-{record.reporter_iso.lower()}-{record.partner_iso.lower()}"
        f"-{record.flow_code.lower()}-{record.commodity_code.lower()}"
        f"-{record.period}"
    )
    sha = _snapshot_hash(
        record.reporter_iso,
        record.partner_iso,
        record.flow_code,
        record.period,
        record.commodity_code,
        record.primary_value,
    )

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "aggregator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or (
            f"UN Comtrade {record.flow_desc} for {record.reporter_name}"
            f" ({record.commodity_desc}), {record.period} data."
        ),
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="comtrade",
            method="get_bilateral_trade",
            description=(
                "Bilateral trade flow value between two countries for an HS commodity code."
            ),
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="reporter",
                    type="str",
                    description="Reporter ISO code",
                    example="USA",
                ),
                CapabilityArg(
                    name="partner",
                    type="str",
                    description="Partner ISO code",
                    example="CHN",
                ),
                CapabilityArg(
                    name="hs_code",
                    type="str",
                    description="HS commodity code",
                    example="85",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="comtrade",
            method="get_total_trade",
            description="Total trade value (exports + imports) for a reporter in a year.",
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="reporter",
                    type="str",
                    description="Reporter ISO code",
                    example="USA",
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="comtrade",
            method="get_hs6_trade",
            description="UN Comtrade trade value for a 6-digit HS commodity code.",
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="cmd_code_hs6",
                    type="str",
                    description="6-digit HS code",
                    example="854231",
                ),
                CapabilityArg(
                    name="reporter", type="str", description="Reporter code", example="842"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="comtrade",
            method="get_world_imports",
            description="UN Comtrade world-aggregate import value for a commodity.",
            returns="atomic primitive, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="cmd_code", type="str", description="HS commodity code", example="85"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="comtrade",
            method="get_services_trade",
            description="UN Comtrade services trade by EBOPS service code.",
            returns="ServiceTradeRecord tuples, unit=currency USD, tier=aggregator",
            args=[
                CapabilityArg(
                    name="eb_code", type="str", description="EBOPS service code", example="SOX"
                ),
                CapabilityArg(
                    name="reporter", type="str", description="Reporter code", example="842"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2022"),
            ],
            source_tier="aggregator",
        ),
        CapabilitySpec(
            connector="comtrade",
            method="get_unit_price",
            description="UN Comtrade implied unit price (trade value ÷ net weight).",
            returns="float (USD per kg) or None",
            args=[
                CapabilityArg(
                    name="reporter", type="str", description="Reporter code", example="842"
                ),
                CapabilityArg(name="year", type="int", description="Year", example="2023"),
                CapabilityArg(
                    name="commodity", type="str", description="HS commodity code", example="2709"
                ),
            ],
            source_tier="aggregator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
