"""Tests for the connector-expansion work (CMS, openFDA, FDIC, EDGAR).

Covers the newly-wired methods, new dataclasses, the openFDA device/event
mis-parse fix, converter→primitive shape, an error path per connector, and
a capabilities-methods-exist check for each module.

All HTTP is mocked with ``httpx.MockTransport`` and an isolated ``tmp_path``
cache dir — no network is touched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from strata.connectors.cms import (
    CMSClient,
    CMSClientError,
    CountRecord,
    ServiceRecord,
    spending_to_primitive_yaml,
)
from strata.connectors.cms import SpendingRecord as CMSSpending
from strata.connectors.cms import capabilities as cms_capabilities
from strata.connectors.edgar import (
    CompanyConcept,
    EDGARClient,
    EDGARClientError,
    Fact,
    Statements,
    concept_to_primitive_yaml,
)
from strata.connectors.edgar import capabilities as edgar_capabilities
from strata.connectors.fdic import (
    DepositShareRecord,
    FDICClient,
    FDICClientError,
    FinancialRecord,
    financial_to_primitive_yaml,
)
from strata.connectors.fdic import capabilities as fdic_capabilities
from strata.connectors.openfda import Device510k as FDADevice510k
from strata.connectors.openfda import (
    DeviceEvent,
    DeviceUDI,
    FDAEndpoint,
    OpenFDAClient,
    OpenFDAClientError,
    clearance_count_to_primitive_yaml,
)
from strata.connectors.openfda import capabilities as openfda_capabilities


def _transport(payload: Any, status: int = 200) -> httpx.MockTransport:
    """Build a MockTransport that returns ``payload`` as JSON for any request."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def _install(client: Any, transport: httpx.MockTransport) -> None:
    """Swap a client's live httpx.Client for one bound to a MockTransport."""
    headers = dict(client._http.headers)
    client._http.close()
    client._http = httpx.Client(transport=transport, follow_redirects=True, headers=headers)


# ═══════════════════════════════════════════════════════════════════
# CMS
# ═══════════════════════════════════════════════════════════════════


class TestCMSExpansion:
    def test_ma_enrollment_parse(self, tmp_path: Path) -> None:
        payload = [
            {"year": "2023", "state": "CA", "medicare_advantage_enrollment": "3200000"},
        ]
        client = CMSClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_ma_enrollment(year=2023, state="CA")
        assert resp.enrollments[0].medicare_advantage == 3200000
        client.close()

    def test_provider_count_parse(self, tmp_path: Path) -> None:
        payload = [{"npi": "1"}, {"npi": "2"}, {"npi": "3"}]
        client = CMSClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_provider_count(state="TX")
        assert resp.counts and isinstance(resp.counts[0], CountRecord)
        assert resp.counts[0].count == 3
        assert resp.counts[0].state == "TX"
        client.close()

    def test_physician_service_utilization_parse(self, tmp_path: Path) -> None:
        payload = [
            {
                "hcpcs_cd": "99213",
                "hcpcs_desc": "Office visit",
                "tot_srvcs": "1500000",
                "tot_benes": "900000",
                "avg_sbmtd_chrg": "120.5",
                "avg_mdcr_pymt_amt": "75.25",
            }
        ]
        client = CMSClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_physician_service_utilization("99213")
        svc = resp.services[0]
        assert isinstance(svc, ServiceRecord)
        assert svc.total_services == 1500000
        assert svc.avg_medicare_payment == 75.25
        client.close()

    def test_error_path(self, tmp_path: Path) -> None:
        client = CMSClient(cache_dir=tmp_path)
        _install(client, _transport({"error": "boom"}))
        with pytest.raises(CMSClientError):
            client.get_ma_enrollment(year=2023)
        client.close()

    def test_converter_primitive_sha(self) -> None:
        rec = CMSSpending(
            year=2023,
            state="CA",
            total_spending=1.0e11,
            per_capita=None,
            beneficiaries=None,
            claims=None,
            hospital_spending=None,
            physician_spending=None,
        )
        out = spending_to_primitive_yaml(
            rec,
            concept_slug="medicare-spend",
            primitive_slug="cms-ca-spend-2023",
            name="CA Medicare spend",
            description="Total Medicare spend in CA",
            source_url="https://data.cms.gov/",
        )
        assert out["kind"] == "atomic_primitive"
        assert len(out["source"]["snapshot_sha256"]) == 64

    def test_capability_methods_exist(self) -> None:
        for spec in cms_capabilities():
            assert hasattr(CMSClient, spec.method), spec.method


# ═══════════════════════════════════════════════════════════════════
# openFDA
# ═══════════════════════════════════════════════════════════════════


class TestOpenFDAExpansion:
    def test_device_event_typed_parse_not_drug_event(self, tmp_path: Path) -> None:
        """The device/event mis-parse fix: results land in device_events with
        device-event fields, NOT in drug_events."""
        payload = {
            "meta": {"results": {"total": 1}},
            "results": [
                {
                    "report_number": "MW123",
                    "event_type": "Malfunction",
                    "date_received": "20230101",
                    "manufacturer_name": "ACME MEDICAL",
                    "device": [{"openfda": {"device_name": ["INFUSION PUMP"]}}],
                    "product_problems": ["Battery Problem", "Failure to Deliver"],
                }
            ],
        }
        client = OpenFDAClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_device_events_typed(device_name="pump")
        assert resp.drug_events == ()
        assert len(resp.device_events) == 1
        evt = resp.device_events[0]
        assert isinstance(evt, DeviceEvent)
        assert evt.report_number == "MW123"
        assert evt.manufacturer_name == "ACME MEDICAL"
        assert evt.device_names == ("INFUSION PUMP",)
        assert "Battery Problem" in evt.product_problems
        client.close()

    def test_clearance_count_by_year_parse(self, tmp_path: Path) -> None:
        payload = {
            "meta": {"results": {"total": 0}},
            "results": [
                {"term": "2022", "count": 3100},
                {"term": "2023", "count": 3300},
            ],
        }
        client = OpenFDAClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_clearance_count_by_year()
        assert resp.count_results[0].term == "2022"
        assert resp.count_results[1].count == 3300
        client.close()

    def test_udi_parse(self, tmp_path: Path) -> None:
        payload = {
            "meta": {"results": {"total": 1}},
            "results": [
                {
                    "public_device_record_key": "abc",
                    "brand_name": "GLUCOMETER X",
                    "company_name": "DEXCO",
                    "device_description": "CGM",
                    "version_or_model_number": "G7",
                }
            ],
        }
        client = OpenFDAClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_device_udi(brand_name="glucometer")
        udi = resp.device_udis[0]
        assert isinstance(udi, DeviceUDI)
        assert udi.company_name == "DEXCO"
        assert udi.version_or_model_number == "G7"
        client.close()

    def test_error_path(self, tmp_path: Path) -> None:
        client = OpenFDAClient(cache_dir=tmp_path)
        _install(client, _transport({"error": {"code": "BAD", "message": "nope"}}))
        with pytest.raises(OpenFDAClientError):
            client.get_ndc_count()
        client.close()

    def test_converter_primitive_sha(self) -> None:
        devices = (
            FDADevice510k(
                k_number="K1",
                applicant="A",
                device_name="D",
                product_code="DXN",
                decision_date="20230101",
                decision="cleared",
                review_advisory_committee="",
                device_class="2",
            ),
        )
        out = clearance_count_to_primitive_yaml(
            devices,
            concept_slug="device-clearances",
            primitive_slug="fda-dxn-clearances",
            name="DXN clearances",
            description="510(k) clearances for DXN",
            source_url="https://api.fda.gov/device/510k.json",
            product_code="DXN",
            total=42,
        )
        assert out["value"] == 42
        assert len(out["source"]["snapshot_sha256"]) == 64

    def test_udi_enum_added(self) -> None:
        assert FDAEndpoint.DEVICE_UDI == "device/udi"

    def test_capability_methods_exist(self) -> None:
        for spec in openfda_capabilities():
            assert hasattr(OpenFDAClient, spec.method), spec.method


# ═══════════════════════════════════════════════════════════════════
# FDIC
# ═══════════════════════════════════════════════════════════════════


class TestFDICExpansion:
    def test_institution_count(self, tmp_path: Path) -> None:
        payload = {"meta": {"total": 4587}, "data": [{"data": {"CERTNUM": "1"}}]}
        client = FDICClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        assert client.get_institution_count() == 4587
        client.close()

    def test_total_loans_aggregation(self, tmp_path: Path) -> None:
        payload = {
            "meta": {"total": 1},
            "data": [{"data": {"ASSET": "1.5e10"}}],
        }
        client = FDICClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        assert client.get_total_loans("20231231") == 1.5e10
        client.close()

    def test_deposit_market_share_parse(self, tmp_path: Path) -> None:
        payload = {
            "meta": {"total": 1},
            "data": [
                {
                    "data": {
                        "CERT": "628",
                        "NAMEFULL": "BANK OF X",
                        "STALPBR": "CA",
                        "CNTYNAMB": "Los Angeles",
                        "DEPSUMBR": "950000",
                        "BRNUM": "12",
                        "YEAR": "2023",
                    }
                }
            ],
        }
        client = FDICClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_deposit_market_share("CA", county="Los Angeles", year=2023)
        share = resp.deposit_shares[0]
        assert isinstance(share, DepositShareRecord)
        assert share.deposits == 950000.0
        assert share.branch_count == 12
        assert share.county == "Los Angeles"
        client.close()

    def test_error_path(self, tmp_path: Path) -> None:
        client = FDICClient(cache_dir=tmp_path)
        _install(client, _transport({"error": "invalid filter"}))
        with pytest.raises(FDICClientError):
            client.get_total_securities("20231231")
        client.close()

    def test_converter_primitive_sha(self) -> None:
        rec = FinancialRecord(
            cert=628,
            name="BANK OF X",
            report_date="20231231",
            assets=1.0e10,
            deposits=None,
            net_income=None,
            interest_income=None,
            non_interest_income=None,
            roa=None,
            roe=None,
            state="California",
            city="LA",
        )
        out = financial_to_primitive_yaml(
            rec,
            concept_slug="bank-assets",
            primitive_slug="fdic-628-asset-2023",
            name="Bank of X assets",
            description="Total assets",
        )
        assert out["value"] == 1.0e10
        assert len(out["source"]["snapshot_sha256"]) == 64

    def test_value_scale_lifts_thousands_to_absolute(self) -> None:
        """FDIC dollar fields are in $thousands; value_scale=1000 → absolute USD."""
        rec = FinancialRecord(
            cert=628,
            name="BANK OF X",
            report_date="20231231",
            assets=1.0e10,
            deposits=None,
            net_income=None,
            interest_income=None,
            non_interest_income=None,
            roa=None,
            roe=None,
            state="California",
            city="LA",
        )
        out = financial_to_primitive_yaml(
            rec,
            concept_slug="bank-assets",
            primitive_slug="fdic-628-asset-scaled",
            name="Bank of X assets",
            description="Total assets, absolute USD",
            value_scale=1000,
        )
        assert out["value"] == 1.0e13
        assert out["unit"]["currency"] == "USD"

    def test_capability_methods_exist(self) -> None:
        for spec in fdic_capabilities():
            assert hasattr(FDICClient, spec.method), spec.method


# ═══════════════════════════════════════════════════════════════════
# EDGAR
# ═══════════════════════════════════════════════════════════════════


def _concept_payload(cik: int, tag: str, val: float, unit: str = "USD") -> dict[str, Any]:
    return {
        "cik": cik,
        "entityName": "Apple Inc.",
        "taxonomy": "us-gaap",
        "tag": tag,
        "label": tag,
        "description": tag,
        "units": {
            unit: [
                {
                    "val": val,
                    "form": "10-K",
                    "filed": "2023-11-03",
                    "frame": "CY2023",
                    "fy": 2023,
                    "fp": "FY",
                }
            ]
        },
    }


class TestEDGARExpansion:
    def test_get_concepts_batch(self, tmp_path: Path) -> None:
        payload = _concept_payload(320193, "Revenues", 3.94e11)
        client = EDGARClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_concepts("0000320193", tags=("Revenues", "Assets"))
        assert resp.concepts is not None
        assert "Revenues" in resp.concepts
        assert "Assets" in resp.concepts
        client.close()

    def test_shares_outstanding(self, tmp_path: Path) -> None:
        payload = _concept_payload(
            320193, "EntityCommonStockSharesOutstanding", 1.55e10, unit="shares"
        )
        client = EDGARClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_shares_outstanding("0000320193")
        assert resp.concept is not None
        assert resp.concept.units["shares"][0].value == 1.55e10
        client.close()

    def test_financial_statements_assembly(self, tmp_path: Path) -> None:
        payload = _concept_payload(320193, "Revenues", 3.94e11)
        client = EDGARClient(cache_dir=tmp_path)
        _install(client, _transport(payload))
        resp = client.get_financial_statements("0000320193", year=2023)
        stmt = resp.statements
        assert isinstance(stmt, Statements)
        assert stmt.revenue == 3.94e11
        assert stmt.fiscal_year == 2023
        # shares_outstanding is requested in the "shares" unit; payload has
        # only USD facts → None.
        assert stmt.shares_outstanding is None
        client.close()

    def test_error_path(self, tmp_path: Path) -> None:
        client = EDGARClient(cache_dir=tmp_path)
        _install(client, _transport({}, status=404))
        with pytest.raises(EDGARClientError):
            client.get_facts_by_concept("0000320193", "Revenues")
        client.close()

    def test_converter_primitive_sha(self) -> None:
        concept = CompanyConcept(
            cik="320193",
            entity_name="Apple Inc.",
            taxonomy="us-gaap",
            tag="Revenues",
            label="Revenues",
            description="Total revenue",
            units={
                "USD": (
                    Fact(
                        value=3.94e11,
                        form="10-K",
                        filed="2023-11-03",
                        frame="CY2023",
                        fiscal_year=2023,
                        fiscal_period="FY",
                    ),
                )
            },
        )
        out = concept_to_primitive_yaml(
            concept,
            concept_slug="apple-revenue",
            primitive_slug="edgar-aapl-rev-2023",
            name="Apple revenue",
            description="FY23 revenue",
            source_url="https://data.sec.gov/",
            year=2023,
        )
        assert len(out["source"]["snapshot_sha256"]) == 64

    def test_capability_methods_exist(self) -> None:
        for spec in edgar_capabilities():
            assert hasattr(EDGARClient, spec.method), spec.method
