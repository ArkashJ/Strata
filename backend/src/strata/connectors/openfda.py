"""openFDA API client.

Typed wrappers for the openFDA API with disk caching and conversion
to Strata AtomicPrimitive / Source YAML format.

API reference: https://open.fda.gov/apis/
Rate limits: Without key 240 req/min, 1000/day.
             With key 240 req/min, 120K/day.
API key optional — passed as ``api_key`` query parameter.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.parse import quote

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class FDAEndpoint(StrEnum):
    """openFDA API endpoints."""

    DRUG_EVENT = "drug/event"
    DRUG_LABEL = "drug/label"
    DRUG_NDC = "drug/ndc"
    DRUG_ENFORCEMENT = "drug/enforcement"
    DEVICE_510K = "device/510k"
    DEVICE_PMA = "device/pma"
    DEVICE_RECALL = "device/recall"
    DEVICE_EVENT = "device/event"
    DEVICE_CLASSIFICATION = "device/classification"
    FOOD_ENFORCEMENT = "food/enforcement"
    FOOD_EVENT = "food/event"
    OTHER_NSDE = "other/nsde"


class FDARecallClass(StrEnum):
    """FDA recall classification severity levels."""

    CLASS_I = "Class I"
    CLASS_II = "Class II"
    CLASS_III = "Class III"


class FDARecallStatus(StrEnum):
    """FDA recall/enforcement status."""

    ONGOING = "Ongoing"
    COMPLETED = "Completed"
    TERMINATED = "Terminated"


class FDADeviceClass(StrEnum):
    """FDA device risk classification levels."""

    CLASS_1 = "1"
    CLASS_2 = "2"
    CLASS_3 = "3"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw openFDA JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class FDAMetaResultsRaw(TypedDict, total=False):
    skip: int
    limit: int
    total: int


class FDAMetaRaw(TypedDict, total=False):
    disclaimer: str
    terms: str
    license: str
    last_updated: str
    results: FDAMetaResultsRaw


class DrugEventRaw(TypedDict, total=False):
    safetyreportid: str
    receivedate: str
    serious: str
    seriousnessdeath: str
    seriousnesshospitalization: str
    seriousnesslifethreatening: str
    patient: dict[str, Any]
    primarysource: dict[str, str]
    occurcountry: str


class DrugLabelRaw(TypedDict, total=False):
    set_id: str
    openfda: dict[str, Any]
    indications_and_usage: list[str]
    dosage_and_administration: list[str]
    warnings: list[str]
    adverse_reactions: list[str]


class Device510kRaw(TypedDict, total=False):
    k_number: str
    applicant: str
    device_name: str
    product_code: str
    decision_date: str
    decision_description: str
    review_advisory_committee: str
    advisory_committee_description: str
    openfda: dict[str, Any]


class DevicePMARaw(TypedDict, total=False):
    pma_number: str
    applicant: str
    trade_name: str
    generic_name: str
    product_code: str
    decision_date: str
    decision_code: str
    advisory_committee: str
    openfda: dict[str, Any]


class EnforcementRaw(TypedDict, total=False):
    recall_number: str
    status: str
    classification: str
    product_description: str
    reason_for_recall: str
    recalling_firm: str
    city: str
    state: str
    country: str
    recall_initiation_date: str
    voluntary_mandated: str
    distribution_pattern: str
    product_type: str


class DeviceClassificationRaw(TypedDict, total=False):
    product_code: str
    device_name: str
    device_class: str
    regulation_number: str
    definition: str
    medical_specialty: str
    medical_specialty_description: str
    openfda: dict[str, Any]


class CountResultRaw(TypedDict, total=False):
    term: str | int
    count: int


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DrugEvent:
    safety_report_id: str
    receive_date: str
    serious: bool
    drug_names: tuple[str, ...]
    reactions: tuple[str, ...]
    outcomes: tuple[str, ...]
    report_country: str


@dataclass(frozen=True, slots=True)
class DrugLabel:
    set_id: str
    brand_name: str
    generic_name: str
    manufacturer: str
    route: str
    substance_name: str
    product_type: str


@dataclass(frozen=True, slots=True)
class Device510k:
    k_number: str
    applicant: str
    device_name: str
    product_code: str
    decision_date: str
    decision: str
    review_advisory_committee: str
    device_class: str


@dataclass(frozen=True, slots=True)
class DevicePMA:
    pma_number: str
    applicant: str
    trade_name: str
    generic_name: str
    product_code: str
    decision_date: str
    decision: str


@dataclass(frozen=True, slots=True)
class Enforcement:
    recall_number: str
    status: str
    classification: str
    product_description: str
    reason_for_recall: str
    recalling_firm: str
    city: str
    state: str
    country: str
    recall_initiation_date: str
    voluntary_mandated: str


@dataclass(frozen=True, slots=True)
class DeviceClassification:
    product_code: str
    device_name: str
    device_class: str
    regulation_number: str
    definition: str


@dataclass(frozen=True, slots=True)
class CountResult:
    term: str
    count: int


@dataclass(frozen=True, slots=True)
class FDAResponse:
    """Standard return type for every openFDA client call."""

    kind: str
    drug_events: tuple[DrugEvent, ...] = ()
    drug_labels: tuple[DrugLabel, ...] = ()
    device_510ks: tuple[Device510k, ...] = ()
    device_pmas: tuple[DevicePMA, ...] = ()
    enforcements: tuple[Enforcement, ...] = ()
    count_results: tuple[CountResult, ...] = ()
    classifications: tuple[DeviceClassification, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _first_str(obj: dict[str, Any], key: str) -> str:
    """Extract first element if value is a list, else return string."""
    val: object = obj.get(key, "")
    if isinstance(val, list):
        return str(val[0]) if val else ""
    return str(val) if val is not None else ""


def _parse_drug_event(raw: dict[str, Any]) -> DrugEvent:
    patient: dict[str, Any] = raw.get("patient", {})
    drugs_raw: list[dict[str, Any]] = patient.get("drug", [])
    reactions_raw: list[dict[str, Any]] = patient.get("reaction", [])

    drug_names: list[str] = []
    for d in drugs_raw:
        openfda: dict[str, Any] = d.get("openfda", {})
        brand: list[str] = openfda.get("brand_name", [])
        if brand:
            drug_names.append(brand[0])
        else:
            name = d.get("medicinalproduct", "")
            if name:
                drug_names.append(str(name))

    reactions = [str(r.get("reactionmeddrapt", "")) for r in reactions_raw]
    outcomes = [str(r.get("reactionoutcome", "")) for r in reactions_raw]

    serious_str = str(raw.get("serious", "2"))
    serious = serious_str == "1"

    return DrugEvent(
        safety_report_id=str(raw.get("safetyreportid", "")),
        receive_date=str(raw.get("receivedate", "")),
        serious=serious,
        drug_names=tuple(drug_names),
        reactions=tuple(reactions),
        outcomes=tuple(outcomes),
        report_country=str(raw.get("occurcountry", "")),
    )


def _parse_drug_label(raw: dict[str, Any]) -> DrugLabel:
    openfda: dict[str, Any] = raw.get("openfda", {})
    return DrugLabel(
        set_id=str(raw.get("set_id", "")),
        brand_name=_first_str(openfda, "brand_name"),
        generic_name=_first_str(openfda, "generic_name"),
        manufacturer=_first_str(openfda, "manufacturer_name"),
        route=_first_str(openfda, "route"),
        substance_name=_first_str(openfda, "substance_name"),
        product_type=_first_str(openfda, "product_type"),
    )


def _parse_device_510k(raw: dict[str, Any]) -> Device510k:
    openfda: dict[str, Any] = raw.get("openfda", {})
    device_class = _first_str(openfda, "device_class")
    return Device510k(
        k_number=str(raw.get("k_number", "")),
        applicant=str(raw.get("applicant", "")),
        device_name=str(raw.get("device_name", "")),
        product_code=str(raw.get("product_code", "")),
        decision_date=str(raw.get("decision_date", "")),
        decision=str(raw.get("decision_description", "")),
        review_advisory_committee=str(raw.get("review_advisory_committee", "")),
        device_class=device_class,
    )


def _parse_device_pma(raw: dict[str, Any]) -> DevicePMA:
    return DevicePMA(
        pma_number=str(raw.get("pma_number", "")),
        applicant=str(raw.get("applicant", "")),
        trade_name=str(raw.get("trade_name", "")),
        generic_name=str(raw.get("generic_name", "")),
        product_code=str(raw.get("product_code", "")),
        decision_date=str(raw.get("decision_date", "")),
        decision=str(raw.get("decision_code", "")),
    )


def _parse_enforcement(raw: dict[str, Any]) -> Enforcement:
    return Enforcement(
        recall_number=str(raw.get("recall_number", "")),
        status=str(raw.get("status", "")),
        classification=str(raw.get("classification", "")),
        product_description=str(raw.get("product_description", "")),
        reason_for_recall=str(raw.get("reason_for_recall", "")),
        recalling_firm=str(raw.get("recalling_firm", "")),
        city=str(raw.get("city", "")),
        state=str(raw.get("state", "")),
        country=str(raw.get("country", "")),
        recall_initiation_date=str(raw.get("recall_initiation_date", "")),
        voluntary_mandated=str(raw.get("voluntary_mandated", "")),
    )


def _parse_device_classification(raw: dict[str, Any]) -> DeviceClassification:
    return DeviceClassification(
        product_code=str(raw.get("product_code", "")),
        device_name=str(raw.get("device_name", "")),
        device_class=str(raw.get("device_class", "")),
        regulation_number=str(raw.get("regulation_number", "")),
        definition=str(raw.get("definition", "")),
    )


def _parse_count_result(raw: dict[str, Any]) -> CountResult:
    term = raw.get("term", "")
    return CountResult(
        term=str(term),
        count=int(raw.get("count", 0)),
    )


def _parse_response(
    data: list[dict[str, Any]],
    total: int,
    *,
    kind: str,
) -> FDAResponse:
    """Parse a list of result objects into typed FDAResponse fields."""
    drug_events: tuple[DrugEvent, ...] = ()
    drug_labels: tuple[DrugLabel, ...] = ()
    device_510ks: tuple[Device510k, ...] = ()
    device_pmas: tuple[DevicePMA, ...] = ()
    enforcements: tuple[Enforcement, ...] = ()
    count_results: tuple[CountResult, ...] = ()
    classifications: tuple[DeviceClassification, ...] = ()

    if kind == "drug_event":
        drug_events = tuple(_parse_drug_event(r) for r in data)
    elif kind == "drug_label":
        drug_labels = tuple(_parse_drug_label(r) for r in data)
    elif kind == "device_510k":
        device_510ks = tuple(_parse_device_510k(r) for r in data)
    elif kind == "device_pma":
        device_pmas = tuple(_parse_device_pma(r) for r in data)
    elif kind in ("drug_enforcement", "food_enforcement", "device_recall"):
        enforcements = tuple(_parse_enforcement(r) for r in data)
    elif kind == "device_classification":
        classifications = tuple(_parse_device_classification(r) for r in data)
    elif kind == "count":
        count_results = tuple(_parse_count_result(r) for r in data)

    return FDAResponse(
        kind=kind,
        drug_events=drug_events,
        drug_labels=drug_labels,
        device_510ks=device_510ks,
        device_pmas=device_pmas,
        enforcements=enforcements,
        count_results=count_results,
        classifications=classifications,
        total=total,
    )


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


class _DiskCache:
    """JSON-on-disk cache keyed by request hash, with configurable TTL."""

    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
        self._dir = directory
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"fda_{key}.json"

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
        for f in self._dir.glob("fda_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.fda.gov"


class OpenFDAClientError(RuntimeError):
    """Raised on openFDA API errors or client-side validation failures."""


def _endpoint_kind(endpoint: FDAEndpoint) -> str:
    """Map an endpoint enum to the response-parsing kind string."""
    mapping: dict[FDAEndpoint, str] = {
        FDAEndpoint.DRUG_EVENT: "drug_event",
        FDAEndpoint.DRUG_LABEL: "drug_label",
        FDAEndpoint.DRUG_NDC: "drug_label",
        FDAEndpoint.DRUG_ENFORCEMENT: "drug_enforcement",
        FDAEndpoint.DEVICE_510K: "device_510k",
        FDAEndpoint.DEVICE_PMA: "device_pma",
        FDAEndpoint.DEVICE_RECALL: "device_recall",
        FDAEndpoint.DEVICE_EVENT: "drug_event",
        FDAEndpoint.DEVICE_CLASSIFICATION: "device_classification",
        FDAEndpoint.FOOD_ENFORCEMENT: "food_enforcement",
        FDAEndpoint.FOOD_EVENT: "drug_event",
        FDAEndpoint.OTHER_NSDE: "drug_label",
    }
    return mapping.get(endpoint, "drug_event")


class OpenFDAClient:
    """Typed client for the openFDA API.

    Usage::

        client = OpenFDAClient()
        resp = client.get_drug_events("ASPIRIN", limit=10)
        for e in resp.drug_events:
            print(e.safety_report_id, e.reactions)

        resp = client.get_top_adverse_reactions("ASPIRIN", limit=20)
        for c in resp.count_results:
            print(c.term, c.count)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("STRATA_OPENFDA_API_KEY")
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "openfda"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OpenFDAClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _build_url(self, endpoint: FDAEndpoint) -> str:
        return f"{_BASE}/{endpoint.value}.json"

    def _request(
        self,
        endpoint: FDAEndpoint,
        params: dict[str, str],
        *,
        kind: str,
    ) -> FDAResponse:
        url = self._build_url(endpoint)
        if self._api_key:
            params["api_key"] = self._api_key

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            body, age = cached
            results: list[dict[str, Any]] = body.get("results", [])
            meta: dict[str, Any] = body.get("meta", {})
            meta_results: dict[str, Any] = meta.get("results", {})
            total = int(meta_results.get("total", len(results)))
            resp = _parse_response(results, total, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)

        if http_resp.status_code == 404:
            return FDAResponse(kind=kind, total=0)

        http_resp.raise_for_status()
        body_raw: Any = http_resp.json()

        if not isinstance(body_raw, dict):
            raise OpenFDAClientError(
                f"openFDA API returned unexpected type: {type(body_raw).__name__}"
            )

        body = cast(dict[str, Any], body_raw)

        error_val: object = body.get("error")
        if error_val is not None:
            msg = (
                str(error_val.get("message", error_val))
                if isinstance(error_val, dict)
                else str(error_val)
            )
            raise OpenFDAClientError(f"openFDA API error: {msg}")

        self._cache.put(ck, body)

        results: list[dict[str, Any]] = body.get("results", [])
        meta: dict[str, Any] = body.get("meta", {})
        meta_results: dict[str, Any] = meta.get("results", {})
        total = int(meta_results.get("total", len(results)))
        return _parse_response(results, total, kind=kind)

    # ── generic search / count ───────────────────────────────────

    def search(
        self,
        endpoint: FDAEndpoint,
        query: str | None = None,
        limit: int = 10,
        skip: int = 0,
    ) -> FDAResponse:
        """Generic search against any openFDA endpoint.

        Args:
            endpoint: The FDA endpoint to query.
            query: openFDA search query string (e.g. ``'patient.drug.openfda.brand_name:"ASPIRIN"'``).
            limit: Results per page (max 1000).
            skip: Pagination offset.
        """
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if skip > 0:
            params["skip"] = str(skip)
        if query:
            params["search"] = query
        kind = _endpoint_kind(endpoint)
        return self._request(endpoint, params, kind=kind)

    def count(
        self,
        endpoint: FDAEndpoint,
        field: str,
        query: str | None = None,
    ) -> FDAResponse:
        """Count results by field value for any endpoint.

        Args:
            endpoint: The FDA endpoint to query.
            field: The field to count by (e.g. ``'patient.reaction.reactionmeddrapt.exact'``).
            query: Optional search query to filter before counting.
        """
        params: dict[str, str] = {"count": field}
        if query:
            params["search"] = query
        return self._request(endpoint, params, kind="count")

    # ── drug adverse events ──────────────────────────────────────

    def get_drug_events(
        self,
        drug_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for drug adverse event reports by brand name.

        Args:
            drug_name: Drug brand name.
            start_date: Start date as YYYYMMDD.
            end_date: End date as YYYYMMDD.
            limit: Max results (max 1000).
        """
        parts = [f'patient.drug.openfda.brand_name:"{quote(drug_name)}"']
        if start_date and end_date:
            parts.append(f"receivedate:[{start_date}+TO+{end_date}]")
        elif start_date:
            parts.append(f"receivedate:[{start_date}+TO+20991231]")
        elif end_date:
            parts.append(f"receivedate:[19000101+TO+{end_date}]")
        query = "+AND+".join(parts)
        params: dict[str, str] = {
            "search": query,
            "limit": str(min(limit, 1000)),
        }
        return self._request(FDAEndpoint.DRUG_EVENT, params, kind="drug_event")

    def get_drug_event_counts(
        self,
        drug_name: str,
        count_field: str = "patient.reaction.reactionmeddrapt.exact",
    ) -> FDAResponse:
        """Count adverse event reports for a drug, grouped by a field.

        Args:
            drug_name: Drug brand name.
            count_field: Field to count by (default: reaction terms).
        """
        query = f'patient.drug.openfda.brand_name:"{quote(drug_name)}"'
        params: dict[str, str] = {
            "search": query,
            "count": count_field,
        }
        return self._request(FDAEndpoint.DRUG_EVENT, params, kind="count")

    def get_top_adverse_reactions(
        self,
        drug_name: str,
        limit: int = 10,
    ) -> FDAResponse:
        """Get the top adverse reactions reported for a drug.

        This is a convenience wrapper around :meth:`get_drug_event_counts`
        that counts by reaction term. The openFDA count endpoint returns
        up to 1000 terms sorted by frequency; ``limit`` trims client-side.

        Args:
            drug_name: Drug brand name.
            limit: Number of top reactions to return.
        """
        resp = self.get_drug_event_counts(drug_name)
        trimmed = resp.count_results[:limit]
        return replace(resp, count_results=trimmed)

    # ── drug labels ──────────────────────────────────────────────

    def get_drug_label(
        self,
        brand_name: str,
    ) -> FDAResponse:
        """Retrieve drug labeling information by brand name.

        Args:
            brand_name: The drug brand name.
        """
        query = f'openfda.brand_name:"{quote(brand_name)}"'
        params: dict[str, str] = {"search": query, "limit": "1"}
        return self._request(FDAEndpoint.DRUG_LABEL, params, kind="drug_label")

    def search_drugs(
        self,
        query: str,
        limit: int = 10,
    ) -> FDAResponse:
        """Search drug labels with a free-text query.

        Args:
            query: Free-text search string.
            limit: Max results.
        """
        params: dict[str, str] = {
            "search": query,
            "limit": str(min(limit, 1000)),
        }
        return self._request(FDAEndpoint.DRUG_LABEL, params, kind="drug_label")

    # ── drug recalls / enforcement ───────────────────────────────

    def get_drug_recalls(
        self,
        drug_name: str | None = None,
        classification: FDARecallClass | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for drug recall/enforcement reports.

        Args:
            drug_name: Product description search term.
            classification: Recall severity class filter.
            limit: Max results.
        """
        parts: list[str] = []
        if drug_name:
            parts.append(f'product_description:"{quote(drug_name)}"')
        if classification:
            parts.append(f'classification:"{classification.value}"')
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.DRUG_ENFORCEMENT, params, kind="drug_enforcement")

    # ── device 510(k) ────────────────────────────────────────────

    def get_device_510k(
        self,
        device_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for 510(k) premarket notifications.

        Args:
            device_name: Device name search term.
            start_date: Decision date start as YYYYMMDD.
            end_date: Decision date end as YYYYMMDD.
            limit: Max results.
        """
        parts: list[str] = []
        if device_name:
            parts.append(f'device_name:"{quote(device_name)}"')
        if start_date and end_date:
            parts.append(f"decision_date:[{start_date}+TO+{end_date}]")
        elif start_date:
            parts.append(f"decision_date:[{start_date}+TO+20991231]")
        elif end_date:
            parts.append(f"decision_date:[19000101+TO+{end_date}]")
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.DEVICE_510K, params, kind="device_510k")

    def get_device_510k_by_product_code(
        self,
        product_code: str,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for 510(k) clearances by product code.

        Args:
            product_code: FDA product code (e.g. "DXN").
            limit: Max results.
        """
        query = f'product_code:"{quote(product_code)}"'
        params: dict[str, str] = {
            "search": query,
            "limit": str(min(limit, 1000)),
        }
        return self._request(FDAEndpoint.DEVICE_510K, params, kind="device_510k")

    # ── device PMA ───────────────────────────────────────────────

    def get_device_pma(
        self,
        device_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for PMA (premarket approval) records.

        Args:
            device_name: Trade or generic name search term.
            start_date: Decision date start as YYYYMMDD.
            end_date: Decision date end as YYYYMMDD.
            limit: Max results.
        """
        parts: list[str] = []
        if device_name:
            parts.append(f'trade_name:"{quote(device_name)}"')
        if start_date and end_date:
            parts.append(f"decision_date:[{start_date}+TO+{end_date}]")
        elif start_date:
            parts.append(f"decision_date:[{start_date}+TO+20991231]")
        elif end_date:
            parts.append(f"decision_date:[19000101+TO+{end_date}]")
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.DEVICE_PMA, params, kind="device_pma")

    # ── device recalls ───────────────────────────────────────────

    def get_device_recalls(
        self,
        device_name: str | None = None,
        classification: FDARecallClass | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for device recall reports.

        Args:
            device_name: Product description search term.
            classification: Recall severity class filter.
            limit: Max results.
        """
        parts: list[str] = []
        if device_name:
            parts.append(f'product_description:"{quote(device_name)}"')
        if classification:
            parts.append(f'classification:"{classification.value}"')
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.DEVICE_RECALL, params, kind="device_recall")

    # ── device adverse events ────────────────────────────────────

    def get_device_events(
        self,
        device_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for medical device adverse event reports.

        Args:
            device_name: Device brand name or generic name.
            start_date: Report date start as YYYYMMDD.
            end_date: Report date end as YYYYMMDD.
            limit: Max results.
        """
        parts: list[str] = []
        if device_name:
            parts.append(f'device.brand_name:"{quote(device_name)}"')
        if start_date and end_date:
            parts.append(f"date_of_event:[{start_date}+TO+{end_date}]")
        elif start_date:
            parts.append(f"date_of_event:[{start_date}+TO+20991231]")
        elif end_date:
            parts.append(f"date_of_event:[19000101+TO+{end_date}]")
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.DEVICE_EVENT, params, kind="drug_event")

    # ── device classifications ───────────────────────────────────

    def get_device_classification(
        self,
        device_name: str | None = None,
        device_class: FDADeviceClass | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for device classification records.

        Args:
            device_name: Device name search term.
            device_class: Risk class filter (1, 2, or 3).
            limit: Max results.
        """
        parts: list[str] = []
        if device_name:
            parts.append(f'device_name:"{quote(device_name)}"')
        if device_class:
            parts.append(f"device_class:{device_class.value}")
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(
            FDAEndpoint.DEVICE_CLASSIFICATION, params, kind="device_classification"
        )

    # ── food recalls / events ────────────────────────────────────

    def get_food_recalls(
        self,
        product: str | None = None,
        classification: FDARecallClass | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for food recall/enforcement reports.

        Args:
            product: Product description search term.
            classification: Recall severity class filter.
            limit: Max results.
        """
        parts: list[str] = []
        if product:
            parts.append(f'product_description:"{quote(product)}"')
        if classification:
            parts.append(f'classification:"{classification.value}"')
        query = "+AND+".join(parts) if parts else None
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if query:
            params["search"] = query
        return self._request(FDAEndpoint.FOOD_ENFORCEMENT, params, kind="food_enforcement")

    def get_food_events(
        self,
        product: str | None = None,
        limit: int = 10,
    ) -> FDAResponse:
        """Search for food adverse event reports.

        Args:
            product: Product keyword search.
            limit: Max results.
        """
        params: dict[str, str] = {"limit": str(min(limit, 1000))}
        if product:
            params["search"] = f'products.name_brand:"{quote(product)}"'
        return self._request(FDAEndpoint.FOOD_EVENT, params, kind="drug_event")

    # ── aggregate / statistical helpers ──────────────────────────

    def get_recall_count_by_year(
        self,
        endpoint: FDAEndpoint = FDAEndpoint.DRUG_ENFORCEMENT,
        start_year: int = 2010,
        end_year: int | None = None,
    ) -> FDAResponse:
        """Count recall/enforcement events by year.

        Args:
            endpoint: Enforcement endpoint (drug/food/device recalls).
            start_year: First year (inclusive).
            end_year: Last year (inclusive). Defaults to current year.
        """
        if end_year is None:
            end_year = date.today().year
        query = f"recall_initiation_date:[{start_year}0101+TO+{end_year}1231]"
        params: dict[str, str] = {
            "search": query,
            "count": "recall_initiation_date",
        }
        return self._request(endpoint, params, kind="count")

    def get_total_events(
        self,
        endpoint: FDAEndpoint = FDAEndpoint.DRUG_EVENT,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> FDAResponse:
        """Get the total number of events for an endpoint in a date range.

        Returns an FDAResponse with only ``total`` populated (plus
        ``count_results`` if the endpoint supports it).

        Args:
            endpoint: Any openFDA endpoint.
            start_date: Start date as YYYYMMDD.
            end_date: End date as YYYYMMDD.
        """
        parts: list[str] = []
        date_field = "receivedate"
        if endpoint in (
            FDAEndpoint.DRUG_ENFORCEMENT,
            FDAEndpoint.FOOD_ENFORCEMENT,
            FDAEndpoint.DEVICE_RECALL,
        ):
            date_field = "recall_initiation_date"
        elif endpoint in (
            FDAEndpoint.DEVICE_510K,
            FDAEndpoint.DEVICE_PMA,
        ):
            date_field = "decision_date"
        elif endpoint == FDAEndpoint.DEVICE_EVENT:
            date_field = "date_of_event"

        if start_date and end_date:
            parts.append(f"{date_field}:[{start_date}+TO+{end_date}]")
        elif start_date:
            parts.append(f"{date_field}:[{start_date}+TO+20991231]")
        elif end_date:
            parts.append(f"{date_field}:[19000101+TO+{end_date}]")

        params: dict[str, str] = {"limit": "1"}
        if parts:
            params["search"] = "+AND+".join(parts)

        kind = _endpoint_kind(endpoint)
        return self._request(endpoint, params, kind=kind)

    def get_manufacturer_recalls(
        self,
        firm_name: str,
        limit: int = 10,
    ) -> FDAResponse:
        """Get recalls issued by a specific manufacturer/firm.

        Searches across drug enforcement. For device recalls use
        :meth:`get_device_recalls` with a name filter.

        Args:
            firm_name: Name of the recalling firm.
            limit: Max results.
        """
        query = f'recalling_firm:"{quote(firm_name)}"'
        params: dict[str, str] = {
            "search": query,
            "limit": str(min(limit, 1000)),
        }
        return self._request(FDAEndpoint.DRUG_ENFORCEMENT, params, kind="drug_enforcement")

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached openFDA responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _snapshot_hash(content: dict[str, Any]) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    raw = json.dumps(content, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def event_count_to_primitive_yaml(
    count_results: tuple[CountResult, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    drug_name: str,
    total: int | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
) -> dict[str, Any]:
    """Convert openFDA adverse-event count results to a Strata AtomicPrimitive YAML dict.

    Uses the total count across all reactions (or the provided ``total``)
    as the primitive value, representing total adverse-event reports.
    """
    computed_total = total if total is not None else sum(c.count for c in count_results)
    sha = _snapshot_hash(
        {
            "drug_name": drug_name,
            "total_events": computed_total,
            "top_reactions": [{"term": c.term, "count": c.count} for c in count_results[:10]],
        }
    )
    source_slug = f"fda-drug-events-{drug_name.lower().replace(' ', '-')}"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": computed_total,
        "unit": {"kind": "stock", "dimension": "events"},
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": "empirical",
        "delivery_mode": "n/a",
        "source": {
            "slug": source_slug,
            "tier": "regulator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def clearance_count_to_primitive_yaml(
    device_510ks: tuple[Device510k, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    product_code: str,
    total: int | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
) -> dict[str, Any]:
    """Convert 510(k) clearance results to a Strata AtomicPrimitive YAML dict.

    Uses the count of clearances as the primitive value.
    """
    computed_total = total if total is not None else len(device_510ks)
    sha = _snapshot_hash(
        {
            "product_code": product_code,
            "clearance_count": computed_total,
            "sample_k_numbers": [d.k_number for d in device_510ks[:10]],
        }
    )
    source_slug = f"fda-510k-{product_code.lower()}"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": computed_total,
        "unit": {"kind": "stock", "dimension": "clearances"},
        "as_of": date.today().isoformat(),
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": "empirical",
        "delivery_mode": "n/a",
        "source": {
            "slug": source_slug,
            "tier": "regulator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def fda_to_source_yaml(
    *,
    source_slug: str,
    source_url: str,
    description: str,
    snapshot_content: dict[str, Any],
) -> dict[str, Any]:
    """Create a Strata source_registry YAML dict for an openFDA data point."""
    sha = _snapshot_hash(snapshot_content)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description,
    }
