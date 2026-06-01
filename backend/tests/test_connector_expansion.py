"""Tests for the connector-expansion methods on OECD, Eurostat, Comtrade,
World Bank.

Hermetic: every client is built with an ``httpx.MockTransport`` and a
``tmp_path`` cache dir — no network. Covers, per connector: ≥3 new-method
parses, one error path, one converter→primitive (sha256 len 64), and a
capabilities-exist assertion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from strata.connectors.comtrade import (
    ComtradeClient,
    ComtradeClientError,
    ServiceTradeRecord,
    trade_to_primitive_yaml,
)
from strata.connectors.comtrade import (
    capabilities as comtrade_capabilities,
)
from strata.connectors.eurostat import (
    EurostatClient,
    EurostatClientError,
    EurostatProductSales,
    observation_to_primitive_yaml,
)
from strata.connectors.eurostat import (
    capabilities as eurostat_capabilities,
)
from strata.connectors.oecd import (
    OECDBusinessStat,
    OECDClient,
    oecd_observation_to_primitive_yaml,
)
from strata.connectors.oecd import (
    capabilities as oecd_capabilities,
)
from strata.connectors.worldbank import (
    WorldBankClient,
    WorldBankClientError,
    indicator_to_primitive_yaml,
)
from strata.connectors.worldbank import (
    capabilities as wb_capabilities,
)

# ─────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────


def _sdmx_body(values: list[tuple[str, float | None]]) -> dict[str, Any]:
    """Build a minimal SDMX-JSON data message with one USA/annual series."""
    obs: dict[str, list[float | None]] = {str(i): [v] for i, (_, v) in enumerate(values)}
    time_values = [{"id": tp, "name": tp} for tp, _ in values]
    return {
        "dataSets": [{"series": {"0:0": {"observations": obs}}}],
        "structure": {
            "dimensions": {
                "series": [
                    {"id": "REF_AREA", "values": [{"id": "USA"}]},
                    {"id": "FREQ", "values": [{"id": "A"}]},
                ],
                "observation": [{"id": "TIME_PERIOD", "values": time_values}],
            },
            "attributes": {"observation": [], "series": []},
        },
    }


def _jsonstat_body(geo: str, year: str, value: float) -> dict[str, Any]:
    """Build a minimal JSON-stat 2.0 body with one geo × one time cell."""
    return {
        "version": "2.0",
        "id": ["geo", "time"],
        "size": [1, 1],
        "dimension": {
            "geo": {"category": {"index": {geo: 0}, "label": {geo: geo}}},
            "time": {"category": {"index": {year: 0}, "label": {year: year}}},
        },
        "value": {"0": value},
        "status": {},
    }


def _comtrade_body(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(records), "data": records}


def _comtrade_record(
    *,
    cmd: str = "85",
    value: float | None = 1000.0,
    flow: str = "M",
    period: int = 2023,
    net_wgt: float | None = None,
) -> dict[str, Any]:
    return {
        "reporterCode": 842,
        "reporterISO": "USA",
        "reporterDesc": "USA",
        "partnerCode": 0,
        "partnerISO": "W00",
        "partnerDesc": "World",
        "flowCode": flow,
        "flowDesc": "Import" if flow == "M" else "Export",
        "refYear": period,
        "cmdCode": cmd,
        "cmdDesc": f"Commodity {cmd}",
        "primaryValue": value,
        "netWgt": net_wgt,
    }


def _wb_body(rows: list[tuple[str, float | None]]) -> list[Any]:
    """Build a World Bank [meta, data] array for indicator NY.GDP.MKTP.CD."""
    data = [
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "US", "value": "United States"},
            "date": d,
            "value": v,
        }
        for d, v in rows
    ]
    meta = {"page": 1, "pages": 1, "per_page": 100, "total": len(data)}
    return [meta, data]


def _transport(body: object, status: int = 200) -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


# ─────────────────────────────────────────────────────────────────────
# OECD
# ─────────────────────────────────────────────────────────────────────


class TestOECDExpansion:
    def test_get_value_added_by_sector(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2022", 5000.0), ("2023", 5300.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_value_added_by_sector("USA", activity="D", year=2023)
        assert resp.total == 2
        assert resp.observations[0].country == "USA"
        client.close()

    def test_get_household_consumption(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2023", 9000.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_household_consumption("USA", coicop="_T", year=2023)
        assert resp.observations[0].value == 9000.0
        client.close()

    def test_get_employment_by_sector(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2023", 1234.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_employment_by_sector(activity="J", ref_area="USA")
        assert resp.observations[0].value == 1234.0
        client.close()

    def test_get_business_demography_returns_business_stats(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2021", 42.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        stats = client.get_business_demography("USA", activity="C", indicator="BIRTH")
        assert len(stats) == 1
        assert isinstance(stats[0], OECDBusinessStat)
        assert stats[0].activity == "C"
        assert stats[0].indicator == "BIRTH"
        assert stats[0].value == 42.0
        client.close()

    def test_get_patents(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2021", 777.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_patents("USA", year=2021)
        assert resp.observations[0].value == 777.0
        client.close()

    def test_error_path_http_500(self, tmp_path: Path) -> None:
        client = OECDClient(cache_dir=tmp_path, transport=_transport({}, status=500))
        with pytest.raises(httpx.HTTPStatusError):
            client.get_patents("USA", year=2021)
        client.close()

    def test_converter_snapshot_sha_len(self, tmp_path: Path) -> None:
        body = _sdmx_body([("2023", 5300.0)])
        client = OECDClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_value_added_by_sector("USA", activity="D", year=2023)
        primitive = oecd_observation_to_primitive_yaml(
            resp.observations,
            concept_slug="oecd-gva-manufacturing",
            primitive_slug="oecd-gva-d-usa-2023",
            name="US manufacturing GVA",
            description="GVA by NACE D",
            source_url="https://sdmx.oecd.org/",
            year=2023,
        )
        assert len(primitive["source"]["snapshot_sha256"]) == 64
        client.close()

    def test_capabilities_include_new_methods(self) -> None:
        methods = {c.method for c in oecd_capabilities()}
        assert {
            "get_value_added_by_sector",
            "get_household_consumption",
            "get_employment_by_sector",
            "get_ict_business_adoption",
            "get_ict_household_adoption",
            "get_business_demography",
            "get_patents",
        } <= methods


# ─────────────────────────────────────────────────────────────────────
# Eurostat
# ─────────────────────────────────────────────────────────────────────


class TestEurostatExpansion:
    def test_get_value_added_by_sector(self, tmp_path: Path) -> None:
        body = _jsonstat_body("DE", "2022", 800000.0)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_value_added_by_sector(geo="DE", nace_r2="C", start_year=2022)
        assert resp.total == 1
        assert resp.observations[0].geo == "DE"
        assert resp.observations[0].value == 800000.0
        client.close()

    def test_get_sbs_sector(self, tmp_path: Path) -> None:
        body = _jsonstat_body("FR", "2021", 12345.0)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_sbs_sector(nace_r2="J", indic_sb="V12110", geo="FR")
        assert resp.observations[0].value == 12345.0
        client.close()

    def test_get_household_consumption(self, tmp_path: Path) -> None:
        body = _jsonstat_body("EU27_2020", "2022", 7000000.0)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_household_consumption(coicop="TOTAL")
        assert resp.observations[0].value == 7000000.0
        client.close()

    def test_get_cloud_adoption(self, tmp_path: Path) -> None:
        body = _jsonstat_body("DE", "2022", 41.5)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_cloud_adoption(geo="DE")
        assert resp.observations[0].value == 41.5
        client.close()

    def test_get_prodcom_returns_product_sales(self, tmp_path: Path) -> None:
        body = _jsonstat_body("DE", "2021", 555.0)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        sales = client.get_prodcom("26201100", geo="DE", start_year=2021)
        assert len(sales) == 1
        assert isinstance(sales[0], EurostatProductSales)
        assert sales[0].prccode == "26201100"
        assert sales[0].value == 555.0
        client.close()

    def test_error_path_404(self, tmp_path: Path) -> None:
        client = EurostatClient(cache_dir=tmp_path, transport=_transport({}, status=404))
        with pytest.raises(EurostatClientError, match="not found"):
            client.get_labour_cost(nace_r2="B-S", geo="DE")
        client.close()

    def test_converter_snapshot_sha_len(self, tmp_path: Path) -> None:
        body = _jsonstat_body("DE", "2022", 800000.0)
        client = EurostatClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_value_added_by_sector(geo="DE", nace_r2="C", start_year=2022)
        primitive = observation_to_primitive_yaml(
            resp.observations,
            concept_slug="es-gva-manufacturing-de",
            primitive_slug="es-gva-c-de-2022",
            name="DE manufacturing GVA",
            description="Eurostat nama_10_a64 B1G",
            source_url="https://ec.europa.eu/eurostat",
            year=2022,
            geo_codes=("DE",),
        )
        assert len(primitive["source"]["snapshot_sha256"]) == 64
        client.close()

    def test_capabilities_include_new_methods(self) -> None:
        methods = {c.method for c in eurostat_capabilities()}
        assert {
            "get_value_added_by_sector",
            "get_sbs_sector",
            "get_household_consumption",
            "get_ecommerce",
            "get_cloud_adoption",
            "get_prodcom",
            "get_labour_cost",
        } <= methods


# ─────────────────────────────────────────────────────────────────────
# Comtrade
# ─────────────────────────────────────────────────────────────────────


class TestComtradeExpansion:
    def test_get_hs6_trade(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(cmd="854231", value=2500.0)])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_hs6_trade("854231", "842", 2023)
        assert resp.records[0].commodity_code == "854231"
        assert resp.records[0].primary_value == 2500.0
        client.close()

    def test_get_world_imports(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(cmd="85", value=9.9e11, flow="M")])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_world_imports("85", 2023)
        assert resp.records[0].flow_code == "M"
        client.close()

    def test_get_monthly_trade(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(period=2023, value=100.0)])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_monthly_trade("842", ["202301", "202302"])
        assert resp.kind == "trade_monthly"
        assert resp.total == 1
        client.close()

    def test_get_services_trade_returns_service_records(self, tmp_path: Path) -> None:
        rec = _comtrade_record(cmd="SOX", value=4321.0, flow="X")
        rec["cmdDesc"] = "Computer services"
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(_comtrade_body([rec])))
        svc = client.get_services_trade("SOX", "842", 2022)
        assert len(svc) == 1
        assert isinstance(svc[0], ServiceTradeRecord)
        assert svc[0].service_code == "SOX"
        assert svc[0].primary_value == 4321.0
        client.close()

    def test_get_unit_price(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(value=2000.0, net_wgt=100.0)])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        price = client.get_unit_price("842", 2023, "2709")
        assert price == 20.0
        client.close()

    def test_get_unit_price_none_when_no_weight(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(value=2000.0, net_wgt=None)])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        assert client.get_unit_price("842", 2023, "2709") is None
        client.close()

    def test_error_path_status_code(self, tmp_path: Path) -> None:
        body = {"statusCode": 429, "message": "rate limited"}
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        with pytest.raises(ComtradeClientError, match="rate limited"):
            client.get_world_imports("85", 2023)
        client.close()

    def test_converter_snapshot_sha_len(self, tmp_path: Path) -> None:
        body = _comtrade_body([_comtrade_record(cmd="854231", value=2500.0)])
        client = ComtradeClient(cache_dir=tmp_path, transport=_transport(body))
        records = client.get_hs6_trade("854231", "842", 2023).records
        client.close()
        primitive = trade_to_primitive_yaml(
            records,
            concept_slug="ct-semiconductors",
            primitive_slug="ct-usa-w-m-854231-2023",
            name="US semiconductor imports",
            description="HS6 854231 imports",
            source_url="https://comtradeapi.un.org/",
            flow="M",
            year=2023,
        )
        assert len(primitive["source"]["snapshot_sha256"]) == 64

    def test_capabilities_include_new_methods(self) -> None:
        methods = {c.method for c in comtrade_capabilities()}
        assert {
            "get_hs6_trade",
            "get_world_imports",
            "get_services_trade",
            "get_unit_price",
        } <= methods


# ─────────────────────────────────────────────────────────────────────
# World Bank
# ─────────────────────────────────────────────────────────────────────


class TestWorldBankExpansion:
    def test_get_gdp(self, tmp_path: Path) -> None:
        body = _wb_body([("2023", 2.7e13), ("2022", 2.5e13)])
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_gdp("US", "2022:2023")
        assert resp.values[0].indicator_id == "NY.GDP.MKTP.CD"
        assert resp.values[0].value == 2.7e13
        client.close()

    def test_get_population(self, tmp_path: Path) -> None:
        body = _wb_body([("2023", 3.3e8)])
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_population("US")
        assert resp.values[0].value == 3.3e8
        client.close()

    def test_get_internet_adoption(self, tmp_path: Path) -> None:
        body = _wb_body([("2023", 91.8)])
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_internet_adoption("US")
        assert resp.values[0].value == 91.8
        client.close()

    def test_get_broadband_subs(self, tmp_path: Path) -> None:
        body = _wb_body([("2023", 37.2)])
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_broadband_subs("US")
        assert resp.values[0].value == 37.2
        client.close()

    def test_error_path_message(self, tmp_path: Path) -> None:
        body = {"message": [{"value": "Invalid indicator"}]}
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        with pytest.raises(WorldBankClientError, match="Invalid indicator"):
            client.get_gdp("US")
        client.close()

    def test_converter_snapshot_sha_len(self, tmp_path: Path) -> None:
        body = _wb_body([("2023", 2.7e13)])
        client = WorldBankClient(cache_dir=tmp_path, transport=_transport(body))
        resp = client.get_gdp("US")
        primitive = indicator_to_primitive_yaml(
            resp.values,
            concept_slug="wb-us-gdp",
            primitive_slug="wb-ny-gdp-mktp-cd-us-2023",
            name="US GDP",
            description="World Bank GDP current US$",
            source_url="https://api.worldbank.org/v2",
            year=2023,
        )
        assert len(primitive["source"]["snapshot_sha256"]) == 64
        client.close()

    def test_capabilities_include_new_methods(self) -> None:
        methods = {c.method for c in wb_capabilities()}
        assert {
            "get_gdp",
            "get_population",
            "get_working_age_pop",
            "get_household_consumption",
            "get_services_value_added",
            "get_internet_adoption",
            "get_broadband_subs",
            "get_mobile_subscriptions",
        } <= methods
