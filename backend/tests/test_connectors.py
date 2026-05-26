"""Tests for data connectors (FRED, Census, EDGAR, BLS).

Tests cover: client initialization, cache mechanics, response parsing,
YAML converter output shape, validation errors, and edge cases.
Uses tmp_path for isolated cache directories. Live API calls are NOT
made — all response parsing is tested against fixture dicts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from strata.connectors.bls import (
    BLSClient,
    BLSClientError,
    BLSResponse,
    BLSStatus,
    DataPoint,
    Series,
    _parse_api_response,
    _parse_data_point,
    series_to_primitive_yaml,
    series_to_source_yaml,
)
from strata.connectors.fred import (
    FREDClient,
    FREDClientError,
    Observation,
    SeriesInfo,
    _parse_observation,
    _parse_observations_response,
    _parse_series_info,
    observations_to_primitive_yaml,
    observations_to_source_yaml,
)
from strata.connectors.census import (
    CensusClient,
    CensusClientError,
    CensusDataset,
    CensusNAICS,
    IndustryRecord,
    FirmRecord,
    _safe_int,
    _rows_to_dicts,
    industry_to_primitive_yaml,
    industry_to_source_yaml,
    firm_to_primitive_yaml,
    firm_to_source_yaml,
)
from strata.connectors.edgar import (
    EDGARClient,
    EDGARClientError,
    Fact,
    CompanyConcept,
    CompanyInfo,
    Filing,
    FrameEntry,
    _parse_fact,
    _parse_company_info,
    _parse_frame_entries,
    concept_to_primitive_yaml,
    concept_to_source_yaml,
    frame_to_primitive_yaml,
)


# ═══════════════════════════════════════════════════════════════════
# BLS connector tests
# ═══════════════════════════════════════════════════════════════════


class TestBLSParsing:
    def test_parse_data_point_basic(self) -> None:
        raw: dict[str, Any] = {
            "year": "2024",
            "period": "M01",
            "periodName": "January",
            "value": "123,456.7",
            "footnotes": [{}],
        }
        dp = _parse_data_point(raw)
        assert dp.year == 2024
        assert dp.period == "M01"
        assert dp.value == 123456.7
        assert dp.is_monthly is True
        assert dp.is_annual is False

    def test_parse_data_point_annual(self) -> None:
        raw: dict[str, Any] = {
            "year": "2024",
            "period": "M13",
            "periodName": "Annual",
            "value": "100",
            "footnotes": [],
        }
        dp = _parse_data_point(raw)
        assert dp.is_annual is True
        assert dp.is_monthly is False

    def test_parse_data_point_invalid_value(self) -> None:
        raw: dict[str, Any] = {
            "year": "2024",
            "period": "M01",
            "periodName": "January",
            "value": "-",
            "footnotes": [],
        }
        dp = _parse_data_point(raw)
        assert dp.value == 0.0

    def test_parse_api_response_series(self) -> None:
        raw: dict[str, Any] = {
            "status": "REQUEST_SUCCEEDED",
            "responseTime": 42,
            "message": ["OK"],
            "Results": {
                "series": [
                    {
                        "seriesID": "TEST001",
                        "data": [
                            {
                                "year": "2024",
                                "period": "A01",
                                "periodName": "Annual",
                                "value": "500",
                                "footnotes": [],
                            }
                        ],
                    }
                ]
            },
        }
        resp = _parse_api_response(raw, kind="series")
        assert resp.status == BLSStatus.REQUEST_SUCCEEDED
        assert len(resp.series) == 1
        assert resp.series[0].series_id == "TEST001"
        assert resp.series[0].data[0].value == 500.0


class TestBLSClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = BLSClient(api_key="test-key", cache_dir=tmp_path)
        assert client._key == "test-key"
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with BLSClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_max_series_validation(self, tmp_path: Path) -> None:
        client = BLSClient(cache_dir=tmp_path)
        with pytest.raises(BLSClientError, match="Max 50"):
            client._build_payload(["S"] * 51)
        client.close()

    def test_max_years_validation(self, tmp_path: Path) -> None:
        client = BLSClient(cache_dir=tmp_path)
        with pytest.raises(BLSClientError, match="Max 20"):
            client._build_payload(["S1"], 2000, 2025)
        client.close()


class TestBLSConverters:
    def _make_series(self) -> Series:
        dp = DataPoint(year=2024, period="M01", period_name="January", value=2183300.0)
        return Series(series_id="OEUM000000015125200000003", data=(dp,))

    def test_series_to_primitive_yaml(self) -> None:
        series = self._make_series()
        result = series_to_primitive_yaml(
            series,
            concept_slug="software-eng-productivity",
            primitive_slug="bls-sw-devs-2024",
            name="US software developers",
            description="BLS OES estimate",
            source_url="https://www.bls.gov/oes/current/oes151252.htm",
            year=2024,
        )
        assert result["kind"] == "atomic_primitive"
        assert result["slug"] == "bls-sw-devs-2024"
        assert result["value"] == 2183300.0
        assert result["source"]["tier"] == "regulator"
        assert len(result["source"]["snapshot_sha256"]) == 64

    def test_series_to_source_yaml(self) -> None:
        series = self._make_series()
        result = series_to_source_yaml(
            series,
            source_url="https://www.bls.gov/oes/current/oes151252.htm",
            year=2024,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("bls-")


# ═══════════════════════════════════════════════════════════════════
# FRED connector tests
# ═══════════════════════════════════════════════════════════════════


class TestFREDParsing:
    def test_parse_observation_valid(self) -> None:
        raw: dict[str, Any] = {
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-12-31",
            "date": "2024-01-01",
            "value": "31856.3",
        }
        obs = _parse_observation(raw)
        assert obs.date == "2024-01-01"
        assert obs.value == 31856.3
        assert obs.has_value is True

    def test_parse_observation_missing_value(self) -> None:
        raw: dict[str, Any] = {
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-12-31",
            "date": "2024-01-01",
            "value": ".",
        }
        obs = _parse_observation(raw)
        assert obs.value is None
        assert obs.has_value is False

    def test_parse_observations_response(self) -> None:
        raw: dict[str, Any] = {
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-12-31",
            "observation_start": "2020-01-01",
            "observation_end": "2024-12-31",
            "count": 2,
            "observations": [
                {"date": "2023-01-01", "value": "26451.7",
                 "realtime_start": "2024-01-01", "realtime_end": "2024-12-31"},
                {"date": "2024-01-01", "value": "31856.3",
                 "realtime_start": "2024-01-01", "realtime_end": "2024-12-31"},
            ],
        }
        resp = _parse_observations_response(raw)
        assert len(resp.observations) == 2
        assert resp.count == 2

    def test_parse_series_info(self) -> None:
        raw: dict[str, Any] = {
            "id": "GDPC1",
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-12-31",
            "title": "Real Gross Domestic Product",
            "observation_start": "1947-01-01",
            "observation_end": "2024-10-01",
            "frequency": "Quarterly",
            "frequency_short": "Q",
            "units": "Billions of Chained 2017 Dollars",
            "units_short": "Bil. of Chn. 2017 $",
            "seasonal_adjustment": "Seasonally Adjusted Annual Rate",
            "seasonal_adjustment_short": "SAAR",
            "last_updated": "2024-12-19 08:41:05-06",
            "popularity": 95,
            "notes": "BEA Account Code: A191RX",
        }
        info = _parse_series_info(raw)
        assert info.id == "GDPC1"
        assert info.title == "Real Gross Domestic Product"
        assert info.frequency == "Quarterly"


class TestFREDClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = FREDClient(api_key="test-key-32chars-abcdefghijklmn", cache_dir=tmp_path)
        assert client._key == "test-key-32chars-abcdefghijklmn"
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with FREDClient(cache_dir=tmp_path) as client:
            assert client is not None


class TestFREDConverters:
    def _make_fixtures(self) -> tuple[SeriesInfo, tuple[Observation, ...]]:
        info = SeriesInfo(
            id="GDP",
            title="Gross Domestic Product",
            observation_start="1947-01-01",
            observation_end="2024-10-01",
            frequency="Quarterly",
            frequency_short="Q",
            units="Billions of Dollars",
            units_short="Bil. of $",
            seasonal_adjustment="Seasonally Adjusted Annual Rate",
            seasonal_adjustment_short="SAAR",
            last_updated="2024-12-19",
            popularity=95,
            notes="",
        )
        obs = (
            Observation(date="2023-01-01", value=26451.7),
            Observation(date="2024-01-01", value=31856.3),
        )
        return info, obs

    def test_observations_to_primitive_yaml(self) -> None:
        info, obs = self._make_fixtures()
        result = observations_to_primitive_yaml(
            info,
            obs,
            concept_slug="us-gdp",
            primitive_slug="fred-gdp-2024",
            name="US GDP",
            description="Nominal GDP",
            source_url="https://fred.stlouisfed.org/series/GDP",
            year=2024,
            unit_currency="USD",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 31856.3
        assert result["source"]["tier"] == "regulator"
        assert result["source"]["slug"] == "fred-gdp-2024"

    def test_observations_to_source_yaml(self) -> None:
        info, obs = self._make_fixtures()
        result = observations_to_source_yaml(
            info,
            obs,
            source_url="https://fred.stlouisfed.org/series/GDP",
            year=2024,
        )
        assert result["kind"] == "source_registry"
        assert result["slug"] == "fred-gdp-2024"

    def test_missing_year_raises(self) -> None:
        info, obs = self._make_fixtures()
        with pytest.raises(FREDClientError, match="No observation found"):
            observations_to_primitive_yaml(
                info,
                obs,
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
                year=1999,
            )


# ═══════════════════════════════════════════════════════════════════
# Census connector tests
# ═══════════════════════════════════════════════════════════════════


class TestCensusParsing:
    def test_safe_int_valid(self) -> None:
        assert _safe_int("12345") == 12345
        assert _safe_int("0") == 0

    def test_safe_int_suppressed(self) -> None:
        assert _safe_int("S") == 0
        assert _safe_int("D") == 0
        assert _safe_int("N") == 0
        assert _safe_int("X") == 0
        assert _safe_int("") == 0

    def test_rows_to_dicts(self) -> None:
        raw: list[list[str]] = [
            ["NAICS2017", "ESTAB", "EMP"],
            ["5112", "17438", "874707"],
            ["5182", "9876", "654321"],
        ]
        headers, rows = _rows_to_dicts(raw)
        assert headers == ("NAICS2017", "ESTAB", "EMP")
        assert len(rows) == 2
        assert rows[0]["NAICS2017"] == "5112"
        assert rows[0]["ESTAB"] == "17438"


class TestCensusClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = CensusClient(api_key="test-key", cache_dir=tmp_path)
        assert client._key == "test-key"
        client.close()

    def test_naics_codes(self) -> None:
        assert CensusNAICS.SOFTWARE_PUBLISHERS == "5112"
        assert CensusNAICS.COMPUTER_SYSTEMS_DESIGN == "5415"

    def test_dataset_enum(self) -> None:
        assert CensusDataset.CBP == "cbp"
        assert CensusDataset.SUSB == "susb"


class TestCensusConverters:
    def _make_industry_record(self) -> IndustryRecord:
        return IndustryRecord(
            naics_code="5112",
            naics_label="Software publishers",
            establishments=17438,
            employees=874707,
            annual_payroll=172774174,
            year=2022,
            geo_level="us",
            geo_code="1",
        )

    def _make_firm_record(self) -> FirmRecord:
        return FirmRecord(
            naics_code="5112",
            naics_label="Software publishers",
            firms=12345,
            establishments=17438,
            employees=874707,
            annual_payroll=172774174,
            year=2022,
        )

    def test_industry_to_primitive_yaml_establishments(self) -> None:
        rec = self._make_industry_record()
        result = industry_to_primitive_yaml(
            rec,
            concept_slug="software-market",
            primitive_slug="census-sw-publishers-2022",
            name="US software publisher establishments",
            description="Census CBP count",
            source_url="https://api.census.gov/data/2022/cbp",
            value_field="establishments",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 17438
        assert result["source"]["tier"] == "regulator"

    def test_industry_to_primitive_yaml_employees(self) -> None:
        rec = self._make_industry_record()
        result = industry_to_primitive_yaml(
            rec,
            concept_slug="software-market",
            primitive_slug="census-sw-employees-2022",
            name="US software publisher employees",
            description="Census CBP employee count",
            source_url="https://api.census.gov/data/2022/cbp",
            value_field="employees",
            unit_dimension="people",
        )
        assert result["value"] == 874707
        assert result["unit"]["dimension"] == "people"

    def test_industry_to_source_yaml(self) -> None:
        rec = self._make_industry_record()
        result = industry_to_source_yaml(
            rec,
            source_url="https://api.census.gov/data/2022/cbp",
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"

    def test_firm_to_primitive_yaml(self) -> None:
        rec = self._make_firm_record()
        result = firm_to_primitive_yaml(
            rec,
            concept_slug="software-firms",
            primitive_slug="census-sw-firms-2022",
            name="US software publisher firms",
            description="Census SUSB firm count",
            source_url="https://api.census.gov/data/2022/susb",
            value_field="firms",
        )
        assert result["value"] == 12345

    def test_firm_to_source_yaml(self) -> None:
        rec = self._make_firm_record()
        result = firm_to_source_yaml(
            rec,
            source_url="https://api.census.gov/data/2022/susb",
        )
        assert result["kind"] == "source_registry"

    def test_invalid_value_field_raises(self) -> None:
        rec = self._make_industry_record()
        with pytest.raises(CensusClientError, match="Unknown value_field"):
            industry_to_primitive_yaml(
                rec,
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
                value_field="nonexistent",
            )


# ═══════════════════════════════════════════════════════════════════
# EDGAR connector tests
# ═══════════════════════════════════════════════════════════════════


class TestEDGARParsing:
    def test_parse_fact(self) -> None:
        raw: dict[str, Any] = {
            "val": 394328000000,
            "form": "10-K",
            "filed": "2023-11-03",
            "frame": "CY2023",
            "fy": 2023,
            "fp": "FY",
            "accn": "0000320193-23-000106",
        }
        fact = _parse_fact(raw)
        assert fact.value == 394328000000.0
        assert fact.form == "10-K"
        assert fact.frame == "CY2023"
        assert fact.fiscal_year == 2023

    def test_parse_company_info(self) -> None:
        raw: dict[str, Any] = {
            "cik": "320193",
            "name": "Apple Inc.",
            "tickers": ["AAPL"],
            "exchanges": ["NASDAQ"],
            "sic": "3571",
            "sicDescription": "Electronic Computers",
            "fiscalYearEnd": "0930",
            "filings": {"recent": {}, "files": []},
        }
        info = _parse_company_info(raw)
        assert info.cik == "320193"
        assert info.name == "Apple Inc."
        assert info.ticker == "AAPL"

    def test_parse_frame_entries(self) -> None:
        raw: dict[str, Any] = {
            "data": [
                {
                    "cik": 320193,
                    "entityName": "Apple Inc.",
                    "val": 394328000000,
                    "form": "10-K",
                    "filed": "2023-11-03",
                    "frame": "CY2023",
                },
                {
                    "cik": 789019,
                    "entityName": "MICROSOFT CORP",
                    "val": 211915000000,
                    "form": "10-K",
                    "filed": "2023-07-25",
                    "frame": "CY2023",
                },
            ]
        }
        entries = _parse_frame_entries(raw)
        assert len(entries) == 2
        assert entries[0].entity_name == "Apple Inc."
        assert entries[1].value == 211915000000.0

    def test_pad_cik(self) -> None:
        assert EDGARClient._pad_cik(320193) == "0000320193"
        assert EDGARClient._pad_cik("320193") == "0000320193"
        assert EDGARClient._pad_cik("0000320193") == "0000320193"


class TestEDGARClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = EDGARClient(cache_dir=tmp_path)
        assert client._http.headers["User-Agent"].startswith("Strata/")
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with EDGARClient(cache_dir=tmp_path) as client:
            assert client is not None


class TestEDGARConverters:
    def _make_concept(self) -> CompanyConcept:
        facts = (
            Fact(value=394328000000.0, form="10-K", filed="2023-11-03",
                 frame="CY2023", fiscal_year=2023, fiscal_period="FY"),
            Fact(value=365817000000.0, form="10-K", filed="2022-10-28",
                 frame="CY2022", fiscal_year=2022, fiscal_period="FY"),
        )
        return CompanyConcept(
            cik="320193",
            entity_name="Apple Inc.",
            taxonomy="us-gaap",
            tag="Revenues",
            label="Revenues",
            description="Total revenue",
            units={"USD": facts},
        )

    def _make_frame_entries(self) -> tuple[FrameEntry, ...]:
        return (
            FrameEntry(cik=320193, entity_name="Apple Inc.",
                       value=394328000000.0, form="10-K",
                       filed="2023-11-03", frame="CY2023"),
            FrameEntry(cik=789019, entity_name="MICROSOFT CORP",
                       value=211915000000.0, form="10-K",
                       filed="2023-07-25", frame="CY2023"),
        )

    def test_concept_to_primitive_yaml(self) -> None:
        concept = self._make_concept()
        result = concept_to_primitive_yaml(
            concept,
            concept_slug="apple-revenue",
            primitive_slug="edgar-aapl-revenue-2023",
            name="Apple Inc. revenue (FY2023)",
            description="10-K annual revenue",
            source_url="https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Revenues.json",
            year=2023,
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 394328000000.0
        assert result["source"]["tier"] == "regulator"
        assert len(result["source"]["snapshot_sha256"]) == 64

    def test_concept_to_source_yaml(self) -> None:
        concept = self._make_concept()
        result = concept_to_source_yaml(
            concept,
            source_url="https://data.sec.gov/",
            year=2023,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"

    def test_frame_to_primitive_yaml_sum(self) -> None:
        entries = self._make_frame_entries()
        result = frame_to_primitive_yaml(
            entries,
            concept_slug="us-tech-revenue",
            primitive_slug="edgar-tech-revenue-2023",
            name="Aggregated tech revenue",
            description="Sum of revenues from EDGAR frames",
            source_url="https://data.sec.gov/",
            aggregation="sum",
        )
        assert result["value"] == 394328000000.0 + 211915000000.0

    def test_frame_to_primitive_yaml_count(self) -> None:
        entries = self._make_frame_entries()
        result = frame_to_primitive_yaml(
            entries,
            concept_slug="us-public-companies",
            primitive_slug="edgar-company-count-2023",
            name="Public companies count",
            description="Count of companies in EDGAR frame",
            source_url="https://data.sec.gov/",
            aggregation="count",
            unit_kind="stock",
            unit_dimension="organizations",
            unit_denominator=None,
            unit_currency=None,
        )
        assert result["value"] == 2.0

    def test_frame_to_primitive_yaml_mean(self) -> None:
        entries = self._make_frame_entries()
        result = frame_to_primitive_yaml(
            entries,
            concept_slug="avg-revenue",
            primitive_slug="avg-rev-2023",
            name="Avg revenue",
            description="Mean",
            source_url="https://data.sec.gov/",
            aggregation="mean",
        )
        expected = (394328000000.0 + 211915000000.0) / 2
        assert result["value"] == pytest.approx(expected)

    def test_frame_empty_raises(self) -> None:
        with pytest.raises(EDGARClientError, match="No frame entries"):
            frame_to_primitive_yaml(
                (),
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
            )


# ═══════════════════════════════════════════════════════════════════
# Cache tests (shared pattern)
# ═══════════════════════════════════════════════════════════════════


class TestDiskCache:
    def test_bls_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.bls import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"status": "ok", "value": 42}
        cache.put("test-params", data)
        result = cache.get("test-params")
        assert result is not None
        cached_data, age = result
        assert cached_data["value"] == 42
        assert age < 1.0

    def test_bls_cache_clear(self, tmp_path: Path) -> None:
        from strata.connectors.bls import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        cache.put("k1", {"a": 1})
        cache.put("k2", {"b": 2})
        assert cache.clear() == 2
        assert cache.get("k1") is None

    def test_fred_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.fred import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"observations": [{"date": "2024-01-01", "value": "100"}]}
        cache.put("fred-test", data)
        result = cache.get("fred-test")
        assert result is not None
        cached_data, age = result
        assert "observations" in cached_data

    def test_census_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.census import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=604800)
        data: list[list[str]] = [["A", "B"], ["1", "2"]]
        cache.put("census-test", data)
        result = cache.get("census-test")
        assert result is not None
        cached_data, age = result
        assert len(cached_data) == 2

    def test_edgar_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.edgar import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=86400)
        data: dict[str, Any] = {"cik": "320193", "entityName": "Apple"}
        cache.put("edgar-test", data)
        result = cache.get("edgar-test")
        assert result is not None
        cached_data, age = result
        assert cached_data["entityName"] == "Apple"


# ═══════════════════════════════════════════════════════════════════
# Cross-connector consistency tests
# ═══════════════════════════════════════════════════════════════════


class TestYAMLOutputConsistency:
    """Verify all connectors produce YAML dicts with the same shape."""

    def test_all_primitives_have_required_keys(self) -> None:
        required_keys = {
            "kind", "slug", "schema_version", "concept_slug", "name",
            "description", "value", "unit", "as_of", "geo",
            "geo_perspective", "distribution_shape", "delivery_mode", "source",
        }
        source_keys = {"slug", "tier", "url", "accessed", "snapshot_sha256"}

        # BLS
        bls_series = Series(
            series_id="TEST",
            data=(DataPoint(year=2024, period="A01", period_name="Annual", value=100.0),),
        )
        bls_prim = series_to_primitive_yaml(
            bls_series, concept_slug="test", primitive_slug="bls-test",
            name="test", description="test",
            source_url="https://bls.gov", year=2024,
        )
        assert required_keys.issubset(bls_prim.keys()), f"BLS missing: {required_keys - bls_prim.keys()}"
        assert source_keys.issubset(bls_prim["source"].keys())

        # FRED
        fred_info = SeriesInfo(
            id="TEST", title="Test", observation_start="2024-01-01",
            observation_end="2024-12-31", frequency="Annual", frequency_short="A",
            units="Units", units_short="U", seasonal_adjustment="NSA",
            seasonal_adjustment_short="NSA", last_updated="2024-01-01",
            popularity=50, notes="",
        )
        fred_obs = (Observation(date="2024-01-01", value=100.0),)
        fred_prim = observations_to_primitive_yaml(
            fred_info, fred_obs, concept_slug="test", primitive_slug="fred-test",
            name="test", description="test",
            source_url="https://fred.stlouisfed.org", year=2024,
        )
        assert required_keys.issubset(fred_prim.keys()), f"FRED missing: {required_keys - fred_prim.keys()}"
        assert source_keys.issubset(fred_prim["source"].keys())

        # Census
        census_rec = IndustryRecord(
            naics_code="5112", naics_label="Software", establishments=100,
            employees=1000, annual_payroll=50000, year=2022,
            geo_level="us", geo_code="1",
        )
        census_prim = industry_to_primitive_yaml(
            census_rec, concept_slug="test", primitive_slug="census-test",
            name="test", description="test",
            source_url="https://census.gov",
        )
        assert required_keys.issubset(census_prim.keys()), f"Census missing: {required_keys - census_prim.keys()}"
        assert source_keys.issubset(census_prim["source"].keys())

        # EDGAR
        edgar_concept = CompanyConcept(
            cik="320193", entity_name="Apple", taxonomy="us-gaap",
            tag="Revenue", label="Revenue", description="Rev",
            units={"USD": (
                Fact(value=100e9, form="10-K", filed="2024-01-01",
                     frame="CY2023", fiscal_year=2023, fiscal_period="FY"),
            )},
        )
        edgar_prim = concept_to_primitive_yaml(
            edgar_concept, concept_slug="test", primitive_slug="edgar-test",
            name="test", description="test",
            source_url="https://sec.gov", year=2023,
        )
        assert required_keys.issubset(edgar_prim.keys()), f"EDGAR missing: {required_keys - edgar_prim.keys()}"
        assert source_keys.issubset(edgar_prim["source"].keys())

    def test_all_sources_have_required_keys(self) -> None:
        required_keys = {"kind", "slug", "tier", "url", "accessed", "snapshot_sha256"}

        bls_series = Series(
            series_id="TEST",
            data=(DataPoint(year=2024, period="A01", period_name="Annual", value=100.0),),
        )
        bls_src = series_to_source_yaml(
            bls_series, source_url="https://bls.gov", year=2024,
        )
        assert required_keys.issubset(bls_src.keys())

        fred_info = SeriesInfo(
            id="TEST", title="Test", observation_start="2024-01-01",
            observation_end="2024-12-31", frequency="A", frequency_short="A",
            units="U", units_short="U", seasonal_adjustment="NSA",
            seasonal_adjustment_short="NSA", last_updated="2024-01-01",
            popularity=50, notes="",
        )
        fred_obs = (Observation(date="2024-01-01", value=100.0),)
        fred_src = observations_to_source_yaml(
            fred_info, fred_obs, source_url="https://fred.stlouisfed.org", year=2024,
        )
        assert required_keys.issubset(fred_src.keys())

        census_rec = IndustryRecord(
            naics_code="5112", naics_label="Sw", establishments=100,
            employees=1000, annual_payroll=50000, year=2022,
            geo_level="us", geo_code="1",
        )
        census_src = industry_to_source_yaml(
            census_rec, source_url="https://census.gov",
        )
        assert required_keys.issubset(census_src.keys())

        edgar_concept = CompanyConcept(
            cik="320193", entity_name="Apple", taxonomy="us-gaap",
            tag="Revenue", label="Revenue", description="Rev",
            units={"USD": (
                Fact(value=100e9, form="10-K", filed="2024-01-01",
                     frame="CY2023", fiscal_year=2023, fiscal_period="FY"),
            )},
        )
        edgar_src = concept_to_source_yaml(
            edgar_concept, source_url="https://sec.gov", year=2023,
        )
        assert required_keys.issubset(edgar_src.keys())
