"""Tests for the FRED connector's typed macro builders + capabilities."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from strata.connectors.fred import (
    FREDClient,
    FREDClientError,
    Observation,
    SeriesInfo,
    capabilities,
    observations_to_primitive_yaml,
)


def _obs_payload(value: str = "27000.0") -> dict[str, object]:
    return {
        "count": 1,
        "observations": [
            {
                "realtime_start": "2024-01-01",
                "realtime_end": "9999-12-31",
                "date": "2023-10-01",
                "value": value,
            }
        ],
    }


def _client_with(handler: httpx.MockTransport, tmp_path: Path) -> FREDClient:
    client = FREDClient(api_key="x" * 32, cache_dir=tmp_path)
    client._http = httpx.Client(transport=handler)  # pyright: ignore[reportPrivateUsage]
    return client


def test_get_gdp_component_maps_series_id(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["series_id"] = request.url.params.get("series_id", "")
        captured["path"] = request.url.path
        return httpx.Response(200, json=_obs_payload())

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_gdp_component("PCE")
    assert captured["series_id"] == "PCEC"
    assert captured["path"].endswith("series/observations")
    assert resp.observations[0].value == 27000.0
    client.close()


def test_get_money_supply_and_pce_map_ids(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params.get("series_id", ""))
        return httpx.Response(200, json=_obs_payload())

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    client.get_money_supply("M2")
    client.get_pce_by_category("services")
    assert seen == ["M2SL", "PCES"]
    client.close()


def test_get_observations_vintage_threads_realtime(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["rt_start"] = request.url.params.get("realtime_start", "")
        captured["rt_end"] = request.url.params.get("realtime_end", "")
        return httpx.Response(200, json=_obs_payload())

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    client.get_observations_vintage("GDP", "2020-01-01", "2020-12-31")
    assert captured["rt_start"] == "2020-01-01"
    assert captured["rt_end"] == "2020-12-31"
    client.close()


def test_observations_aggregation_method_threaded(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["agg"] = request.url.params.get("aggregation_method", "")
        captured["units"] = request.url.params.get("units", "")
        return httpx.Response(200, json=_obs_payload())

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    client.get_observations("GDP", frequency="a", aggregation_method="sum", units="pc1")
    assert captured["agg"] == "sum"
    assert captured["units"] == "pc1"
    client.close()


def test_api_error_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error_code": 400, "error_message": "bad request"})

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(FREDClientError, match="400"):
        client.get_gdp_component("GDP")
    client.close()


def test_converter_emits_pinned_source() -> None:
    info = SeriesInfo(
        id="GDP",
        title="Gross Domestic Product",
        frequency="Quarterly",
        frequency_short="Q",
        units="Billions of Dollars",
        units_short="Bil. of $",
        seasonal_adjustment="Seasonally Adjusted Annual Rate",
        seasonal_adjustment_short="SAAR",
        observation_start="1947-01-01",
        observation_end="2023-10-01",
        last_updated="2024-01-25",
    )
    obs = (Observation(date="2023-10-01", value=27000.0),)
    prim = observations_to_primitive_yaml(
        info,
        obs,
        concept_slug="us-gdp",
        primitive_slug="us-gdp-2023",
        name="US GDP",
        description="FRED GDP",
        source_url="https://fred.stlouisfed.org/series/GDP",
        unit_currency="USD",
    )
    assert prim["value"] == 27000.0
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_methods_exist() -> None:
    specs = capabilities()
    assert len(specs) >= 8
    for spec in specs:
        assert spec.connector == "fred"
        assert hasattr(FREDClient, spec.method), spec.method
    json.dumps([s.model_dump() for s in specs])
