"""Tests for the EIA connector's new typed helpers + capabilities."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from strata.connectors.eia import (
    EIAClient,
    EIAClientError,
    EIADataPoint,
    capabilities,
    datapoint_to_primitive_yaml,
)


def _data_payload(value: float = 12345.0, units: str = "megawatts") -> dict[str, object]:
    return {
        "response": {
            "total": 1,
            "data": [
                {
                    "period": "2023",
                    "stateId": "CA",
                    "stateDescription": "California",
                    "value": value,
                    "units": units,
                    "fuelTypeId": "SUN",
                    "fuelTypeDescription": "Solar",
                }
            ],
        }
    }


def _client_with(handler: httpx.MockTransport, tmp_path: Path) -> EIAClient:
    client = EIAClient(api_key="test", cache_dir=tmp_path)
    client._http = httpx.Client(transport=handler)  # pyright: ignore[reportPrivateUsage]
    return client


def test_get_generator_capacity_hits_route(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["fuel"] = request.url.params.get("facets[energy_source_code][]", "")
        return httpx.Response(200, json=_data_payload())

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_generator_capacity(fuel="SUN", state="CA")
    assert "operating-generator-capacity" in captured["path"]
    assert captured["fuel"] == "SUN"
    assert resp.data_points[0].value == 12345.0
    client.close()


def test_get_co2_emissions_threads_facets(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["sector"] = request.url.params.get("facets[sectorId][]", "")
        captured["path"] = request.url.path
        return httpx.Response(200, json=_data_payload(900.0, "million metric tons"))

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_co2_emissions(sector="TT", fuel="TO")
    assert "co2-emissions" in captured["path"]
    assert captured["sector"] == "TT"
    assert resp.data_points[0].value == 900.0
    client.close()


def test_get_aeo_projection_is_versioned_forecast(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "response": {
                    "total": 1,
                    "data": [
                        {
                            "period": "2030",
                            "seriesId": "cons_NA_elep",
                            "value": 42.0,
                            "units": "quads",
                            "seriesDescription": "Electricity demand",
                        }
                    ],
                }
            },
        )

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_aeo_projection(series_id="cons_NA_elep", aeo_year="2023")
    assert "aeo/2023/data" in captured["path"]
    assert resp.forecasts[0].value == 42.0
    client.close()


def test_http_error_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_natural_gas_consumption(end_use="VEU")
    client.close()


def test_api_error_payload_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "invalid route"})

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(EIAClientError, match="invalid route"):
        client.get_petroleum_consumption(product="EPM0")
    client.close()


def test_converter_emits_pinned_source() -> None:
    dp = (
        EIADataPoint(
            period="2023",
            state="CA",
            state_name="California",
            sector="SUN",
            sector_name="Solar",
            value=12345.0,
            units="megawatts",
            series_id="",
        ),
    )
    prim = datapoint_to_primitive_yaml(
        dp,
        route="electricity/operating-generator-capacity",
        concept_slug="us-solar-capacity",
        primitive_slug="ca-solar-cap-2023",
        name="CA solar capacity",
        description="EIA generator capacity",
        source_url="https://www.eia.gov/opendata/",
        unit_dimension="power",
    )
    assert prim["value"] == 12345.0
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_methods_exist() -> None:
    specs = capabilities()
    assert len(specs) >= 14
    for spec in specs:
        assert spec.connector == "eia"
        assert hasattr(EIAClient, spec.method), spec.method
    json.dumps([s.model_dump() for s in specs])
