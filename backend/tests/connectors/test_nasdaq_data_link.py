"""Tests for the Nasdaq Data Link connector capability + client."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from strata.connectors.nasdaq_data_link import (
    NasdaqDataLinkClient,
    NasdaqDataLinkClientError,
    NasdaqDatasetMeta,
    NasdaqDatatable,
    NasdaqObservation,
    NasdaqOrder,
    NasdaqResponse,
    capabilities,
    observation_to_primitive_yaml,
)


def _client(
    cache_dir: Path, payload: dict[str, object], *, status: int = 200
) -> tuple[NasdaqDataLinkClient, dict[str, str]]:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["order"] = request.url.params.get("order", "")
        seen["path"] = request.url.path
        return httpx.Response(status, json=payload)

    client = NasdaqDataLinkClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        cache_dir=cache_dir,
    )
    return client, seen


def test_get_dataset_parses(tmp_path: Path) -> None:
    payload = {
        "dataset_data": {
            "column_names": ["Date", "USD"],
            "data": [["2024-01-02", 2050.0], ["2024-01-01", 2040.0]],
        }
    }
    client, seen = _client(tmp_path, payload)
    resp = client.get_dataset("LBMA", "GOLD", order=NasdaqOrder.DESC, limit=2)
    assert isinstance(resp, NasdaqResponse)
    assert seen["order"] == "desc"
    assert resp.column_names == ("Date", "USD")
    assert len(resp.observations) == 2
    assert resp.latest().value == 2050.0
    assert resp.latest().series_date == date(2024, 1, 2)


def test_get_dataset_metadata_parses(tmp_path: Path) -> None:
    payload = {
        "dataset": {
            "database_code": "USTREASURY",
            "dataset_code": "YIELD",
            "name": "Treasury Yield Curve Rates",
            "description": "US Treasury daily yield curve",
            "frequency": "daily",
            "newest_available_date": "2024-01-02",
            "oldest_available_date": "1990-01-02",
            "column_names": ["Date", "10 YR"],
        }
    }
    client, _ = _client(tmp_path, payload)
    meta = client.get_dataset_metadata("USTREASURY", "YIELD")
    assert isinstance(meta, NasdaqDatasetMeta)
    assert meta.frequency == "daily"
    assert meta.newest_available_date == "2024-01-02"
    assert meta.column_names == ("Date", "10 YR")


def test_get_datatable_parses(tmp_path: Path) -> None:
    payload = {
        "datatable": {
            "columns": [
                {"name": "ticker", "type": "String"},
                {"name": "close", "type": "double"},
            ],
            "data": [["AAPL", 190.1], ["MSFT", 410.2]],
        },
        "meta": {"next_cursor_id": "abc123"},
    }
    client, _ = _client(tmp_path, payload)
    dt = client.get_datatable("WIKI/PRICES", per_page=2)
    assert isinstance(dt, NasdaqDatatable)
    assert [c.name for c in dt.columns] == ["ticker", "close"]
    assert dt.rows[0] == ("AAPL", 190.1)
    assert dt.next_cursor_id == "abc123"
    assert dt.has_more is True


def test_quandl_error_raises(tmp_path: Path) -> None:
    payload = {
        "quandl_error": {"code": "QECx02", "message": "You have submitted an incorrect code."}
    }
    client, _ = _client(tmp_path, payload, status=400)
    with pytest.raises(NasdaqDataLinkClientError, match="QECx02"):
        client.get_dataset("BAD", "CODE")


def test_observation_converter() -> None:
    obs = NasdaqObservation(dataset_code="GOLD", series_date=date(2024, 1, 2), values=(2050.0,))
    prim = observation_to_primitive_yaml(
        obs,
        slug="nasdaq-gold-2024-01-02",
        concept_slug="gold-price",
        meta=None,
        accessed=date(2024, 1, 3),
    )
    assert prim["value"] == 2050.0
    assert prim["unit"]["currency"] == "USD"
    assert prim["source"]["tier"] == "aggregator"
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_capabilities_methods_exist_and_premium_gated() -> None:
    specs = capabilities()
    assert specs
    for spec in specs:
        assert hasattr(NasdaqDataLinkClient, spec.method)
    assert any(s.requires_paid_tier for s in specs)
