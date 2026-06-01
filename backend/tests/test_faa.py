"""Tests for the FAA connector — new aggregate methods + capability gap close.

HTTP is mocked via ``httpx.MockTransport``; no network. The mock returns a
fixed three-airport feature set (small enough that ``_arcgis_query_all`` stops
after one page).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from strata.connectors.faa import (
    FAAClient,
    capabilities,
    passenger_count_to_primitive_yaml,
)

_FEATURES = {
    "features": [
        {
            "attributes": {
                "FAC_NAME": "SAN FRANCISCO INTL",
                "LOCID": "SFO",
                "STATE": "CA",
                "FAC_TYPE": "AIRPORT",
                "OWNER_TYPE": "PU",
                "PASSENGERS": 50_000_000,
                "OPERATIONS": 400_000,
                "BASED_ACFT": 100,
            }
        },
        {
            "attributes": {
                "FAC_NAME": "LOS ANGELES INTL",
                "LOCID": "LAX",
                "STATE": "CA",
                "FAC_TYPE": "AIRPORT",
                "OWNER_TYPE": "PU",
                "PASSENGERS": 88_000_000,
                "OPERATIONS": 700_000,
                "BASED_ACFT": 50,
            }
        },
        {
            "attributes": {
                "FAC_NAME": "SOME HELIPORT",
                "LOCID": "H01",
                "STATE": "CA",
                "FAC_TYPE": "HELIPORT",
                "OWNER_TYPE": "PR",
                "PASSENGERS": 0,
                "OPERATIONS": 1_200,
                "BASED_ACFT": 3,
            }
        },
    ],
    "exceededTransferLimit": False,
}


def _client(tmp_path: Path) -> FAAClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_FEATURES)

    return FAAClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler))


def test_get_national_totals(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_national_totals()
    assert len(resp.summaries) == 1
    s = resp.summaries[0]
    assert s.state == "US"
    assert s.count == 3
    assert s.total_passengers == 138_000_000
    assert s.total_operations == 1_101_200


def test_get_operations_total(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_operations_total("CA")
    assert resp.total == 1_101_200
    assert resp.summaries[0].state == "CA"


def test_get_based_aircraft(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_based_aircraft("CA")
    assert resp.total == 153
    assert resp.summaries[0].count == 3


def test_get_enplanements_ranked(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_enplanements_ranked(limit=10)
    assert resp.kind == "airports"
    # mock ignores order; just confirm rows came back parsed
    assert len(resp.airports) == 3


def test_count_by_facility_type(tmp_path: Path) -> None:
    resp = _client(tmp_path).count_by_facility_type()
    by_type = {s.state: s.count for s in resp.summaries}
    assert by_type["AIRPORT"] == 2
    assert by_type["HELIPORT"] == 1


def test_hub_size_breakdown_buckets(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_hub_size_breakdown()
    tiers = {s.state: s.count for s in resp.summaries}
    # SFO + LAX are both >1% of national enplanements -> large hubs
    assert tiers["large_hub"] == 2


def test_airports_by_owner_type(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_airports_by_owner_type("PU")
    # mock returns all features regardless of WHERE; method still parses rows
    assert resp.kind == "airports"
    assert len(resp.airports) == 3


def test_arcgis_error_raises(tmp_path: Path) -> None:
    import pytest

    from strata.connectors.faa import FAAClientError

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 400, "message": "bad where"}})

    client = FAAClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    with pytest.raises(FAAClientError, match="bad where"):
        client.get_national_totals()


def test_national_totals_converts_to_primitive(tmp_path: Path) -> None:
    resp = _client(tmp_path).get_national_totals()
    prim = passenger_count_to_primitive_yaml(
        resp.summaries[0],
        concept_slug="us-aviation",
        primitive_slug="faa-us-passengers",
        name="US total air passengers",
        description="FAA national enplanements rollup",
    )
    assert prim["value"] == 138_000_000
    assert prim["source"]["tier"] == "regulator"
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_cover_new_methods_and_exist() -> None:
    specs = capabilities()
    methods = {s.method for s in specs}
    for new in (
        "get_operations_total",
        "get_enplanements_ranked",
        "get_based_aircraft",
        "get_national_totals",
        "get_airports_by_owner_type",
        "get_hub_size_breakdown",
        "count_by_facility_type",
    ):
        assert new in methods, f"{new} missing from capabilities()"
        assert hasattr(FAAClient, new)
    for spec in specs:
        assert hasattr(FAAClient, spec.method)
        assert spec.source_tier == "regulator"
    assert len(specs) >= 9
