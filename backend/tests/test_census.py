"""Tests for the Census connector's new dataset methods + capabilities."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from strata.connectors.census import (
    CensusClient,
    CensusClientError,
    EconomicCensusRecord,
    capabilities,
    economic_to_primitive_yaml,
)


def _client_with(handler: httpx.MockTransport, tmp_path: Path) -> CensusClient:
    client = CensusClient(cache_dir=tmp_path)
    client._http = httpx.Client(  # pyright: ignore[reportPrivateUsage]
        transport=handler, follow_redirects=True
    )
    return client


def test_get_economic_census_parses_receipts(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["get"] = request.url.params.get("get", "")
        body = [
            ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "PAYANN", "ESTAB", "EMP", "us"],
            ["5415", "Computer systems design", "500000000", "120000000", "90000", "1500000", "1"],
        ]
        return httpx.Response(200, json=body)

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_economic_census("5415", year=2017)
    assert "ecnbasic" in captured["path"]
    assert "RCPTOT" in captured["get"]
    rec = resp.records[0]
    assert isinstance(rec, EconomicCensusRecord)
    assert rec.receipts == 500000000
    assert rec.naics_code == "5415"
    client.close()


def test_get_pep_population_parses_pop(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        body = [["NAME", "POP", "us"], ["United States", "331000000", "1"]]
        return httpx.Response(200, json=body)

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_pep_population(2023)
    rec = resp.records[0]
    assert rec.naics_code == "POP"
    assert rec.employees == 331000000
    client.close()


def test_get_susb_by_size_threads_predicate(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["empszfi"] = request.url.params.get("EMPSZFI", "")
        body = [
            ["NAICS2017", "NAICS2017_LABEL", "FIRM", "ESTAB", "EMP", "PAYANN", "us"],
            ["5415", "Computer systems design", "100000", "120000", "1500000", "120000000", "1"],
        ]
        return httpx.Response(200, json=body)

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_susb_by_size(2021, naics="5415", empszfi="270")
    assert captured["empszfi"] == "270"
    assert resp.records[0].naics_code == "5415"
    client.close()


def test_http_error_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(CensusClientError, match="HTTP 400"):
        client.get_bds(naics="00", year=2021)
    client.close()


def test_economic_converter_emits_pinned_source() -> None:
    rec = EconomicCensusRecord(
        naics_code="5415",
        naics_label="Computer systems design",
        receipts=500000000,
        establishments=90000,
        employees=1500000,
        annual_payroll=120000000,
        year=2017,
        geo_level="us",
        geo_code="1",
    )
    prim = economic_to_primitive_yaml(
        rec,
        concept_slug="it-services-us",
        primitive_slug="ecn-5415-receipts-2017",
        name="IT services receipts",
        description="Economic Census",
        source_url="https://www.census.gov/programs-surveys/economic-census.html",
        value_field="receipts",
    )
    assert prim["value"] == 500000000
    assert prim["unit"]["currency"] == "USD"
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_methods_exist() -> None:
    specs = capabilities()
    assert len(specs) >= 8
    for spec in specs:
        assert spec.connector == "census"
        assert hasattr(CensusClient, spec.method), spec.method
    json.dumps([s.model_dump() for s in specs])
