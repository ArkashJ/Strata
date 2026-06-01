"""Tests for the BLS connector's typed series-ID builders + capabilities."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from strata.connectors.bls import (
    BLSClient,
    BLSClientError,
    DataPoint,
    Series,
    capabilities,
    series_to_primitive_yaml,
)


def _ok_payload(series_id: str, value: str = "1234.5") -> dict[str, object]:
    return {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 12,
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": series_id,
                    "data": [
                        {
                            "year": "2024",
                            "period": "M01",
                            "periodName": "January",
                            "value": value,
                            "latest": "true",
                            "footnotes": [{}],
                        }
                    ],
                }
            ]
        },
    }


def _client_with(handler: httpx.MockTransport, tmp_path: Path) -> BLSClient:
    client = BLSClient(cache_dir=tmp_path)
    client._http = httpx.Client(transport=handler)  # pyright: ignore[reportPrivateUsage]
    return client


def test_get_oes_employment_builds_series_id(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        sid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=_ok_payload(sid, "2183300"))

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    resp = client.get_oes_employment("15-1252", area="0000000", datatype="01")
    assert resp.status.value == "REQUEST_SUCCEEDED"
    # OE + U + area(7) + 000000 + occ(6) + datatype(2)
    assert captured["path"].endswith("OEU0000000000000151252" + "01")
    assert resp.series[0].data[0].value == 2183300.0
    client.close()


def test_get_cpi_and_qcew_build_distinct_ids(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sid = request.url.path.rsplit("/", 1)[-1]
        seen.append(sid)
        return httpx.Response(200, json=_ok_payload(sid))

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    client.get_cpi(item="SA0", area="0000")
    client.get_qcew_by_naics("5415", area="US000", owner="0")
    assert seen[0] == "CUUR0000SA0"  # CU + U + R + 0000 + SA0
    assert seen[1].startswith("ENU") and seen[1].endswith("5415")
    client.close()


def test_get_jolts_builds_series_id(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sid = request.url.path.rsplit("/", 1)[-1]
        seen.append(sid)
        return httpx.Response(200, json=_ok_payload(sid))

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    client.get_jolts("JO", industry="000000", region="00")
    assert seen[0].startswith("JTS") and "JO" in seen[0]
    client.close()


def test_request_failed_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "REQUEST_FAILED", "message": ["bad series"], "Results": {}},
        )

    client = _client_with(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(BLSClientError, match="REQUEST_FAILED"):
        client.get_cpi()
    client.close()


def test_converter_emits_pinned_source() -> None:
    series = Series(
        series_id="CUUR0000SA0",
        data=(DataPoint(year=2024, period="M01", period_name="January", value=314.0),),
    )
    prim = series_to_primitive_yaml(
        series,
        concept_slug="us-inflation",
        primitive_slug="cpi-2024",
        name="CPI-U all items",
        description="BLS CPI",
        source_url="https://www.bls.gov/cpi/",
        year=2024,
        unit_dimension="index",
    )
    assert prim["value"] == 314.0
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_methods_exist() -> None:
    specs = capabilities()
    assert len(specs) >= 10
    for spec in specs:
        assert spec.connector == "bls"
        assert hasattr(BLSClient, spec.method), spec.method
    # spec serialization is JSON-clean
    json.dumps([s.model_dump() for s in specs])
