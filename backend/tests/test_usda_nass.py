"""Tests for the USDA NASS connector — new query methods + capability gap close.

All HTTP is mocked via ``httpx.MockTransport``; no network and no key budget
is spent. The mock dispatches on the ``statisticcat_desc`` query param so each
convenience method round-trips through ``_request`` and the parser.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from strata.connectors.usda_nass import (
    NASSAggLevel,
    NASSClient,
    NASSCommodity,
    capabilities,
    record_to_primitive_yaml,
)


def _client(tmp_path: Path, handler: object) -> NASSClient:
    return NASSClient(
        api_key="test-key",
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def _data_payload(stat: str, value: str, unit: str) -> dict[str, object]:
    return {
        "data": [
            {
                "commodity_desc": "CORN",
                "statisticcat_desc": stat,
                "year": 2023,
                "Value": value,
                "unit_desc": unit,
                "agg_level_desc": "NATIONAL",
                "state_alpha": "US",
                "state_name": "US TOTAL",
                "freq_desc": "ANNUAL",
                "reference_period_desc": "YEAR",
            }
        ]
    }


def test_get_sales_value_parses(tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["stat"] = request.url.params.get("statisticcat_desc", "")
        return httpx.Response(200, json=_data_payload("SALES", "1,200,000,000", "$"))

    client = _client(tmp_path, handler)
    resp = client.get_sales_value(NASSCommodity.CORN, year=2023)
    assert seen["stat"] == "SALES"
    assert resp.records[0].value == 1_200_000_000.0
    assert resp.records[0].unit == "$"


def test_get_operations_count_parses(tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["stat"] = request.url.params.get("statisticcat_desc", "")
        seen["agg"] = request.url.params.get("agg_level_desc", "")
        return httpx.Response(200, json=_data_payload("OPERATIONS", "89,400", "OPERATIONS"))

    client = _client(tmp_path, handler)
    resp = client.get_operations_count(NASSCommodity.CORN, year=2023)
    assert seen["stat"] == "OPERATIONS"
    assert seen["agg"] == NASSAggLevel.STATE
    assert resp.records[0].value == 89_400.0


def test_get_stocks_parses(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_data_payload("STOCKS", "1,360,000,000", "BU"))

    client = _client(tmp_path, handler)
    resp = client.get_stocks(NASSCommodity.CORN, year=2023)
    assert resp.records[0].statistic_category == "STOCKS"
    assert resp.records[0].value == 1_360_000_000.0


def test_get_organic_sets_domain(tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["domain"] = request.url.params.get("domain_desc", "")
        seen["source"] = request.url.params.get("source_desc", "")
        return httpx.Response(200, json=_data_payload("SALES", "55,000,000", "$"))

    client = _client(tmp_path, handler)
    client.get_organic(NASSCommodity.CORN, year=2023)
    assert seen["domain"] == "ORGANIC STATUS"
    assert seen["source"] == "CENSUS"


def test_get_by_county_sets_county_agg(tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["agg"] = request.url.params.get("agg_level_desc", "")
        seen["state"] = request.url.params.get("state_alpha", "")
        return httpx.Response(200, json=_data_payload("PRODUCTION", "5,000,000", "BU"))

    client = _client(tmp_path, handler)
    client.get_by_county(NASSCommodity.CORN, "IA", year=2023)
    assert seen["agg"] == NASSAggLevel.COUNTY
    assert seen["state"] == "IA"


def test_api_error_raises(tmp_path: Path) -> None:
    import pytest

    from strata.connectors.usda_nass import NASSClientError

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": ["bad query"]})

    client = _client(tmp_path, handler)
    with pytest.raises(NASSClientError, match="bad query"):
        client.get_sales_value(NASSCommodity.CORN, year=2023)


def test_sales_value_converts_to_primitive(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_data_payload("SALES", "1,200,000,000", "$"))

    client = _client(tmp_path, handler)
    resp = client.get_sales_value(NASSCommodity.CORN, year=2023)
    prim = record_to_primitive_yaml(
        resp.records,
        concept_slug="us-corn-market",
        primitive_slug="nass-corn-sales-2023",
        name="US corn sales value",
        description="USDA NASS corn sales receipts",
        year=2023,
    )
    assert prim["kind"] == "atomic_primitive"
    assert prim["value"] == 1_200_000_000.0
    assert prim["source"]["tier"] == "regulator"
    assert prim["unit"]["dimension"] == "currency"
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_cover_new_methods_and_exist() -> None:
    specs = capabilities()
    methods = {s.method for s in specs}
    for new in (
        "get_sales_value",
        "get_operations_count",
        "get_stocks",
        "get_area_bearing",
        "get_by_county",
        "get_economic_class",
        "get_organic",
    ):
        assert new in methods, f"{new} missing from capabilities()"
        assert hasattr(NASSClient, new)
    for spec in specs:
        assert hasattr(NASSClient, spec.method)
        assert spec.source_tier == "regulator"
    # gap-close: was 2/16, now covers the full query surface
    assert len(specs) >= 14
