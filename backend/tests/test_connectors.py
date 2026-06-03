"""Tests for data connectors (FRED, Census, EDGAR, BLS, OECD, Eurostat,
Comtrade, FDIC, CMS, EIA, USDA NASS, FAA, openFDA).

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
    BLSStatus,
    DataPoint,
    Series,
    _parse_api_response,
    _parse_data_point,
    series_to_primitive_yaml,
    series_to_source_yaml,
)
from strata.connectors.census import (
    CensusClient,
    CensusClientError,
    CensusDataset,
    CensusNAICS,
    FirmRecord,
    IndustryRecord,
    _rows_to_dicts,
    _safe_int,
    firm_to_primitive_yaml,
    firm_to_source_yaml,
    industry_to_primitive_yaml,
    industry_to_source_yaml,
)
from strata.connectors.edgar import (
    CompanyConcept,
    EDGARClient,
    EDGARClientError,
    Fact,
    FrameEntry,
    _parse_company_info,
    _parse_fact,
    _parse_frame_entries,
    concept_to_primitive_yaml,
    concept_to_source_yaml,
    frame_to_primitive_yaml,
)
from strata.connectors.fred import (
    FREDClient,
    FREDClientError,
    Observation,
    SeriesInfo,
    _parse_observation,
    _parse_observations_response,
    _parse_series_info,
    observations_only_to_primitive_yaml,
    observations_to_primitive_yaml,
    observations_to_source_yaml,
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
                {
                    "date": "2023-01-01",
                    "value": "26451.7",
                    "realtime_start": "2024-01-01",
                    "realtime_end": "2024-12-31",
                },
                {
                    "date": "2024-01-01",
                    "value": "31856.3",
                    "realtime_start": "2024-01-01",
                    "realtime_end": "2024-12-31",
                },
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

    def test_observations_only_to_primitive_yaml(self) -> None:
        """The dispatch-safe converter builds a valid primitive from observations
        alone (no SeriesInfo), deriving source slug + hash from primitive_slug."""
        _info, obs = self._make_fixtures()
        result = observations_only_to_primitive_yaml(
            obs,
            concept_slug="us-gdp",
            primitive_slug="fred-us-gdp-nominal",
            name="US nominal GDP",
            description="Nominal GDP from FRED",
            source_url="https://fred.stlouisfed.org/series/GDP",
            year=2024,
            unit_kind="flow",
            unit_dimension="currency",
            unit_currency="USD",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 31856.3
        assert result["source"]["slug"] == "fred-us-gdp-nominal-src"
        assert result["unit"]["currency"] == "USD"
        assert len(result["source"]["snapshot_sha256"]) == 64

    def test_observations_only_no_currency_on_non_currency_unit(self) -> None:
        """A people/percent unit must NOT inherit a currency."""
        _info, obs = self._make_fixtures()
        result = observations_only_to_primitive_yaml(
            obs,
            concept_slug="us-labor",
            primitive_slug="fred-us-employment",
            name="US employment",
            description="Headcount",
            source_url="https://fred.stlouisfed.org/series/PAYEMS",
            year=2024,
            unit_kind="stock",
            unit_dimension="people",
            unit_currency="USD",  # ignored: dimension is not currency
        )
        assert "currency" not in result["unit"]

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
            Fact(
                value=394328000000.0,
                form="10-K",
                filed="2023-11-03",
                frame="CY2023",
                fiscal_year=2023,
                fiscal_period="FY",
            ),
            Fact(
                value=365817000000.0,
                form="10-K",
                filed="2022-10-28",
                frame="CY2022",
                fiscal_year=2022,
                fiscal_period="FY",
            ),
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
            FrameEntry(
                cik=320193,
                entity_name="Apple Inc.",
                value=394328000000.0,
                form="10-K",
                filed="2023-11-03",
                frame="CY2023",
            ),
            FrameEntry(
                cik=789019,
                entity_name="MICROSOFT CORP",
                value=211915000000.0,
                form="10-K",
                filed="2023-07-25",
                frame="CY2023",
            ),
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
        cached_data, _age = result
        assert "observations" in cached_data

    def test_census_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.census import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=604800)
        data: list[list[str]] = [["A", "B"], ["1", "2"]]
        cache.put("census-test", data)
        result = cache.get("census-test")
        assert result is not None
        cached_data, _age = result
        assert len(cached_data) == 2

    def test_edgar_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.edgar import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=86400)
        data: dict[str, Any] = {"cik": "320193", "entityName": "Apple"}
        cache.put("edgar-test", data)
        result = cache.get("edgar-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["entityName"] == "Apple"


# ═══════════════════════════════════════════════════════════════════
# Cross-connector consistency tests
# ═══════════════════════════════════════════════════════════════════


class TestYAMLOutputConsistency:
    """Verify all connectors produce YAML dicts with the same shape."""

    def test_all_primitives_have_required_keys(self) -> None:
        required_keys = {
            "kind",
            "slug",
            "schema_version",
            "concept_slug",
            "name",
            "description",
            "value",
            "unit",
            "as_of",
            "geo",
            "geo_perspective",
            "distribution_shape",
            "delivery_mode",
            "source",
        }
        source_keys = {"slug", "tier", "url", "accessed", "snapshot_sha256"}

        # BLS
        bls_series = Series(
            series_id="TEST",
            data=(DataPoint(year=2024, period="A01", period_name="Annual", value=100.0),),
        )
        bls_prim = series_to_primitive_yaml(
            bls_series,
            concept_slug="test",
            primitive_slug="bls-test",
            name="test",
            description="test",
            source_url="https://bls.gov",
            year=2024,
        )
        assert required_keys.issubset(bls_prim.keys()), (
            f"BLS missing: {required_keys - bls_prim.keys()}"
        )
        assert source_keys.issubset(bls_prim["source"].keys())

        # FRED
        fred_info = SeriesInfo(
            id="TEST",
            title="Test",
            observation_start="2024-01-01",
            observation_end="2024-12-31",
            frequency="Annual",
            frequency_short="A",
            units="Units",
            units_short="U",
            seasonal_adjustment="NSA",
            seasonal_adjustment_short="NSA",
            last_updated="2024-01-01",
            popularity=50,
            notes="",
        )
        fred_obs = (Observation(date="2024-01-01", value=100.0),)
        fred_prim = observations_to_primitive_yaml(
            fred_info,
            fred_obs,
            concept_slug="test",
            primitive_slug="fred-test",
            name="test",
            description="test",
            source_url="https://fred.stlouisfed.org",
            year=2024,
        )
        assert required_keys.issubset(fred_prim.keys()), (
            f"FRED missing: {required_keys - fred_prim.keys()}"
        )
        assert source_keys.issubset(fred_prim["source"].keys())

        # Census
        census_rec = IndustryRecord(
            naics_code="5112",
            naics_label="Software",
            establishments=100,
            employees=1000,
            annual_payroll=50000,
            year=2022,
            geo_level="us",
            geo_code="1",
        )
        census_prim = industry_to_primitive_yaml(
            census_rec,
            concept_slug="test",
            primitive_slug="census-test",
            name="test",
            description="test",
            source_url="https://census.gov",
        )
        assert required_keys.issubset(census_prim.keys()), (
            f"Census missing: {required_keys - census_prim.keys()}"
        )
        assert source_keys.issubset(census_prim["source"].keys())

        # EDGAR
        edgar_concept = CompanyConcept(
            cik="320193",
            entity_name="Apple",
            taxonomy="us-gaap",
            tag="Revenue",
            label="Revenue",
            description="Rev",
            units={
                "USD": (
                    Fact(
                        value=100e9,
                        form="10-K",
                        filed="2024-01-01",
                        frame="CY2023",
                        fiscal_year=2023,
                        fiscal_period="FY",
                    ),
                )
            },
        )
        edgar_prim = concept_to_primitive_yaml(
            edgar_concept,
            concept_slug="test",
            primitive_slug="edgar-test",
            name="test",
            description="test",
            source_url="https://sec.gov",
            year=2023,
        )
        assert required_keys.issubset(edgar_prim.keys()), (
            f"EDGAR missing: {required_keys - edgar_prim.keys()}"
        )
        assert source_keys.issubset(edgar_prim["source"].keys())

    def test_all_sources_have_required_keys(self) -> None:
        required_keys = {"kind", "slug", "tier", "url", "accessed", "snapshot_sha256"}

        bls_series = Series(
            series_id="TEST",
            data=(DataPoint(year=2024, period="A01", period_name="Annual", value=100.0),),
        )
        bls_src = series_to_source_yaml(
            bls_series,
            source_url="https://bls.gov",
            year=2024,
        )
        assert required_keys.issubset(bls_src.keys())

        fred_info = SeriesInfo(
            id="TEST",
            title="Test",
            observation_start="2024-01-01",
            observation_end="2024-12-31",
            frequency="A",
            frequency_short="A",
            units="U",
            units_short="U",
            seasonal_adjustment="NSA",
            seasonal_adjustment_short="NSA",
            last_updated="2024-01-01",
            popularity=50,
            notes="",
        )
        fred_obs = (Observation(date="2024-01-01", value=100.0),)
        fred_src = observations_to_source_yaml(
            fred_info,
            fred_obs,
            source_url="https://fred.stlouisfed.org",
            year=2024,
        )
        assert required_keys.issubset(fred_src.keys())

        census_rec = IndustryRecord(
            naics_code="5112",
            naics_label="Sw",
            establishments=100,
            employees=1000,
            annual_payroll=50000,
            year=2022,
            geo_level="us",
            geo_code="1",
        )
        census_src = industry_to_source_yaml(
            census_rec,
            source_url="https://census.gov",
        )
        assert required_keys.issubset(census_src.keys())

        edgar_concept = CompanyConcept(
            cik="320193",
            entity_name="Apple",
            taxonomy="us-gaap",
            tag="Revenue",
            label="Revenue",
            description="Rev",
            units={
                "USD": (
                    Fact(
                        value=100e9,
                        form="10-K",
                        filed="2024-01-01",
                        frame="CY2023",
                        fiscal_year=2023,
                        fiscal_period="FY",
                    ),
                )
            },
        )
        edgar_src = concept_to_source_yaml(
            edgar_concept,
            source_url="https://sec.gov",
            year=2023,
        )
        assert required_keys.issubset(edgar_src.keys())


# ═══════════════════════════════════════════════════════════════════
# OECD connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.oecd import (
    OECDClient,
    OECDClientError,
    OECDCountry,
    OECDDataflow,
    OECDFrequency,
    OECDObservation,
    _parse_data_message,
    _parse_dataflow_list,
    _safe_lookup,
    oecd_observation_to_primitive_yaml,
    oecd_observation_to_source_yaml,
)


class TestOECDParsing:
    def test_safe_lookup_valid(self) -> None:
        values = [{"id": "USA"}, {"id": "GBR"}, {"id": "DEU"}]
        assert _safe_lookup(values, 0) == "USA"
        assert _safe_lookup(values, 2) == "DEU"

    def test_safe_lookup_out_of_range(self) -> None:
        values = [{"id": "USA"}]
        assert _safe_lookup(values, 5) == ""
        assert _safe_lookup(values, -1) == ""

    def test_safe_lookup_missing_id(self) -> None:
        values: list[dict[str, str]] = [{"name": "United States"}]
        assert _safe_lookup(values, 0) == "United States"

    def test_parse_data_message_basic(self) -> None:
        body: dict[str, Any] = {
            "dataSets": [
                {
                    "series": {
                        "0:0": {
                            "observations": {
                                "0": [25462.7, None],
                                "1": [26949.6, None],
                            }
                        }
                    }
                }
            ],
            "structure": {
                "dimensions": {
                    "series": [
                        {
                            "id": "REF_AREA",
                            "values": [{"id": "USA", "name": "United States"}],
                        },
                        {
                            "id": "FREQ",
                            "values": [{"id": "A", "name": "Annual"}],
                        },
                    ],
                    "observation": [
                        {
                            "id": "TIME_PERIOD",
                            "values": [
                                {"id": "2022", "name": "2022"},
                                {"id": "2023", "name": "2023"},
                            ],
                        }
                    ],
                },
                "attributes": {"observation": [], "series": []},
            },
        }
        resp = _parse_data_message(body, dataflow_id="TEST_GDP")
        assert resp.kind == "data"
        assert resp.total == 2
        assert len(resp.observations) == 2
        assert resp.observations[0].country == "USA"
        assert resp.observations[0].value == 25462.7
        assert resp.observations[1].time_period == "2023"

    def test_parse_data_message_empty(self) -> None:
        body: dict[str, Any] = {"dataSets": [], "structure": {"dimensions": {}}}
        resp = _parse_data_message(body, dataflow_id="EMPTY")
        assert resp.total == 0
        assert len(resp.observations) == 0

    def test_parse_data_message_null_value(self) -> None:
        body: dict[str, Any] = {
            "dataSets": [
                {
                    "series": {
                        "0:0": {
                            "observations": {"0": [None]},
                        }
                    }
                }
            ],
            "structure": {
                "dimensions": {
                    "series": [
                        {"id": "REF_AREA", "values": [{"id": "USA"}]},
                        {"id": "FREQ", "values": [{"id": "A"}]},
                    ],
                    "observation": [
                        {"id": "TIME_PERIOD", "values": [{"id": "2023"}]},
                    ],
                },
                "attributes": {"observation": [], "series": []},
            },
        }
        resp = _parse_data_message(body, dataflow_id="NULL_TEST")
        assert resp.observations[0].value is None

    def test_parse_dataflow_list(self) -> None:
        body: dict[str, Any] = {
            "data": {
                "dataflows": [
                    {
                        "id": "DF_GDP",
                        "name": {"en": "GDP expenditure approach"},
                        "description": {"en": "GDP by expenditure"},
                        "agencyID": "OECD",
                        "version": "1.0",
                    },
                    {
                        "id": "DF_CPI",
                        "name": "CPI All Items",
                        "description": "",
                        "agencyID": "OECD",
                        "version": "2.0",
                    },
                ]
            }
        }
        resp = _parse_dataflow_list(body)
        assert resp.kind == "dataflows"
        assert resp.total == 2
        assert resp.dataflows[0].id == "DF_GDP"
        assert resp.dataflows[0].name == "GDP expenditure approach"
        assert resp.dataflows[1].name == "CPI All Items"


class TestOECDClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = OECDClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with OECDClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert OECDFrequency.ANNUAL == "A"
        assert OECDCountry.USA == "USA"
        assert OECDDataflow.GDP.value.startswith("OECD.")


class TestOECDConverters:
    def _make_observations(self) -> tuple[OECDObservation, ...]:
        return (
            OECDObservation(
                country="USA",
                frequency="A",
                time_period="2022",
                value=25462.7,
                unit_measure="USD",
                flags="",
                series_key="0:0",
                dataflow_id="DF_GDP",
            ),
            OECDObservation(
                country="USA",
                frequency="A",
                time_period="2023",
                value=26949.6,
                unit_measure="USD",
                flags="",
                series_key="0:0",
                dataflow_id="DF_GDP",
            ),
        )

    def test_observation_to_primitive_yaml(self) -> None:
        obs = self._make_observations()
        result = oecd_observation_to_primitive_yaml(
            obs,
            concept_slug="us-gdp",
            primitive_slug="oecd-gdp-2023",
            name="US GDP (OECD)",
            description="Nominal GDP",
            source_url="https://sdmx.oecd.org/",
            year=2023,
        )
        assert result["kind"] == "atomic_primitive"
        assert result["slug"] == "oecd-gdp-2023"
        assert result["value"] == 26949.6
        assert result["source"]["tier"] == "aggregator"
        assert len(result["source"]["snapshot_sha256"]) == 64

    def test_observation_to_source_yaml(self) -> None:
        obs = self._make_observations()
        result = oecd_observation_to_source_yaml(
            obs,
            source_url="https://sdmx.oecd.org/",
            year=2023,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "aggregator"
        assert result["slug"].startswith("oecd-")

    def test_pick_latest_when_year_missing(self) -> None:
        obs = self._make_observations()
        result = oecd_observation_to_primitive_yaml(
            obs,
            concept_slug="test",
            primitive_slug="oecd-test",
            name="test",
            description="test",
            source_url="https://test",
            year=1999,
        )
        # Should fall back to latest (2023)
        assert result["value"] == 26949.6

    def test_empty_observations_raises(self) -> None:
        with pytest.raises(OECDClientError, match="No observations"):
            oecd_observation_to_primitive_yaml(
                (),
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
            )


# ═══════════════════════════════════════════════════════════════════
# Eurostat connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.eurostat import (
    EurostatClient,
    EurostatClientError,
    EurostatCountry,
    EurostatDataset,
    EurostatFrequency,
    EurostatObservation,
    _extract_dimension_values,
    _parse_json_stat_response,
    _parse_observations,
    observation_to_primitive_yaml,
    observation_to_source_yaml,
)


class TestEurostatParsing:
    def test_extract_dimension_values(self) -> None:
        raw = {
            "geo": {
                "label": "geo",
                "category": {
                    "index": {"DE": 0, "FR": 1},
                    "label": {"DE": "Germany", "FR": "France"},
                },
            },
        }
        result = _extract_dimension_values(raw, ["geo"])
        assert result["geo"] == ["DE", "FR"]

    def test_parse_observations_basic(self) -> None:
        body: dict[str, Any] = {
            "id": ["geo", "time"],
            "size": [2, 2],
            "dimension": {
                "geo": {
                    "label": "geo",
                    "category": {
                        "index": {"DE": 0, "FR": 1},
                        "label": {"DE": "Germany", "FR": "France"},
                    },
                },
                "time": {
                    "label": "time",
                    "category": {
                        "index": {"2022": 0, "2023": 1},
                        "label": {"2022": "2022", "2023": "2023"},
                    },
                },
            },
            "value": {"0": 3876.8, "1": 4082.3, "2": 2788.5, "3": 2923.1},
            "status": {},
        }
        obs = _parse_observations(body, "nama_10_gdp")
        assert len(obs) == 4
        assert obs[0].geo == "DE"
        assert obs[0].time_period == "2022"
        assert obs[0].value == 3876.8
        assert obs[3].geo == "FR"
        assert obs[3].time_period == "2023"

    def test_parse_observations_empty(self) -> None:
        body: dict[str, Any] = {"id": [], "size": [], "dimension": {}, "value": {}}
        obs = _parse_observations(body, "empty")
        assert len(obs) == 0

    def test_parse_json_stat_response(self) -> None:
        body: dict[str, Any] = {
            "id": ["geo", "time"],
            "size": [1, 1],
            "dimension": {
                "geo": {
                    "label": "geo",
                    "category": {
                        "index": {"DE": 0},
                        "label": {"DE": "Germany"},
                    },
                },
                "time": {
                    "label": "time",
                    "category": {
                        "index": {"2023": 0},
                        "label": {"2023": "2023"},
                    },
                },
            },
            "value": {"0": 4082.3},
            "status": {},
        }
        resp = _parse_json_stat_response(body, "nama_10_gdp")
        assert resp.kind == "data"
        assert resp.total == 1
        assert resp.observations[0].value == 4082.3


class TestEurostatClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = EurostatClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with EurostatClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert EurostatCountry.DE == "DE"
        assert EurostatDataset.GDP == "nama_10_gdp"
        assert EurostatFrequency.ANNUAL == "A"


class TestEurostatConverters:
    def _make_observations(self) -> tuple[EurostatObservation, ...]:
        return (
            EurostatObservation(
                dataset="nama_10_gdp",
                geo="DE",
                time_period="2022",
                value=3876800.0,
                unit="CP_MEUR",
                freq="A",
                status_flag="",
            ),
            EurostatObservation(
                dataset="nama_10_gdp",
                geo="DE",
                time_period="2023",
                value=4082300.0,
                unit="CP_MEUR",
                freq="A",
                status_flag="",
            ),
        )

    def test_observation_to_primitive_yaml(self) -> None:
        obs = self._make_observations()
        result = observation_to_primitive_yaml(
            obs,
            concept_slug="eu-gdp",
            primitive_slug="es-gdp-de-2023",
            name="Germany GDP",
            description="Eurostat GDP",
            source_url="https://ec.europa.eu/eurostat",
            year=2023,
            geo_codes=("DE",),
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 4082300.0
        assert result["source"]["tier"] == "regulator"
        assert len(result["source"]["snapshot_sha256"]) == 64

    def test_observation_to_source_yaml(self) -> None:
        obs = self._make_observations()
        result = observation_to_source_yaml(
            obs,
            source_url="https://ec.europa.eu/eurostat",
            year=2023,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("es-")

    def test_empty_observations_raises(self) -> None:
        with pytest.raises(EurostatClientError, match="No observations"):
            observation_to_primitive_yaml(
                (),
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
            )


# ═══════════════════════════════════════════════════════════════════
# Comtrade connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.comtrade import (
    ComtradeClient,
    ComtradeClientError,
    ComtradeFlowCode,
    ComtradeHSChapter,
    ComtradeReporter,
    TradeRecord,
    _parse_response,
    _parse_trade_record,
    trade_to_primitive_yaml,
    trade_to_source_yaml,
)


class TestComtradeParsing:
    def test_parse_trade_record_basic(self) -> None:
        raw: dict[str, Any] = {
            "reporterCode": 842,
            "reporterISO": "USA",
            "reporterDesc": "United States",
            "partnerCode": 0,
            "partnerISO": "W00",
            "partnerDesc": "World",
            "flowCode": "X",
            "flowDesc": "Export",
            "refYear": 2023,
            "cmdCode": "TOTAL",
            "cmdDesc": "All commodities",
            "primaryValue": 2065221543210.0,
            "netWgt": 1234567890.0,
            "fobvalue": 2065221543210.0,
            "cifvalue": None,
        }
        rec = _parse_trade_record(raw)
        assert rec.reporter_iso == "USA"
        assert rec.partner_name == "World"
        assert rec.flow_code == "X"
        assert rec.primary_value == 2065221543210.0
        assert rec.period == 2023
        assert rec.net_weight == 1234567890.0
        assert rec.cif_value is None

    def test_parse_trade_record_missing_values(self) -> None:
        raw: dict[str, Any] = {
            "reporterCode": 156,
            "reporterISO": "CHN",
            "reporterDesc": "China",
            "partnerCode": 0,
            "partnerISO": "W00",
            "partnerDesc": "World",
            "flowCode": "M",
            "flowDesc": "Import",
            "refYear": 2023,
            "cmdCode": "27",
            "cmdDesc": "Mineral fuels",
            "primaryValue": None,
            "netWgt": None,
            "fobvalue": None,
            "cifvalue": None,
        }
        rec = _parse_trade_record(raw)
        assert rec.primary_value is None
        assert rec.net_weight is None

    def test_parse_trade_record_invalid_value(self) -> None:
        raw: dict[str, Any] = {
            "reporterCode": 842,
            "reporterISO": "USA",
            "reporterDesc": "US",
            "partnerCode": 0,
            "partnerISO": "W00",
            "partnerDesc": "World",
            "flowCode": "X",
            "flowDesc": "Export",
            "refYear": 2023,
            "cmdCode": "TOTAL",
            "cmdDesc": "All",
            "primaryValue": "N/A",
            "netWgt": None,
            "fobvalue": None,
            "cifvalue": None,
        }
        rec = _parse_trade_record(raw)
        assert rec.primary_value is None

    def test_parse_response(self) -> None:
        body: dict[str, Any] = {
            "count": 2,
            "data": [
                {
                    "reporterCode": 842,
                    "reporterISO": "USA",
                    "reporterDesc": "US",
                    "partnerCode": 0,
                    "partnerISO": "W00",
                    "partnerDesc": "World",
                    "flowCode": "X",
                    "flowDesc": "Export",
                    "refYear": 2023,
                    "cmdCode": "TOTAL",
                    "cmdDesc": "All",
                    "primaryValue": 1000000.0,
                },
                {
                    "reporterCode": 842,
                    "reporterISO": "USA",
                    "reporterDesc": "US",
                    "partnerCode": 0,
                    "partnerISO": "W00",
                    "partnerDesc": "World",
                    "flowCode": "M",
                    "flowDesc": "Import",
                    "refYear": 2023,
                    "cmdCode": "TOTAL",
                    "cmdDesc": "All",
                    "primaryValue": 2000000.0,
                },
            ],
        }
        resp = _parse_response(body, kind="trade")
        assert resp.total == 2
        assert len(resp.records) == 2
        assert resp.records[0].flow_code == "X"
        assert resp.records[1].flow_code == "M"


class TestComtradeClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = ComtradeClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with ComtradeClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert ComtradeFlowCode.EXPORTS == "X"
        assert ComtradeReporter.USA == "842"
        assert ComtradeHSChapter.PHARMA == "30"


class TestComtradeConverters:
    def _make_records(self) -> tuple[TradeRecord, ...]:
        return (
            TradeRecord(
                reporter_code=842,
                reporter_iso="USA",
                reporter_name="United States",
                partner_code=0,
                partner_iso="W00",
                partner_name="World",
                flow_code="X",
                flow_desc="Export",
                period=2023,
                commodity_code="TOTAL",
                commodity_desc="All commodities",
                primary_value=2065221543210.0,
                net_weight=None,
                fob_value=None,
                cif_value=None,
            ),
        )

    def test_trade_to_primitive_yaml(self) -> None:
        recs = self._make_records()
        result = trade_to_primitive_yaml(
            recs,
            concept_slug="us-exports",
            primitive_slug="ct-usa-exports-2023",
            name="US total exports",
            description="UN Comtrade total exports",
            source_url="https://comtradeapi.un.org/",
            flow="X",
            year=2023,
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 2065221543210.0
        assert result["source"]["tier"] == "aggregator"

    def test_trade_to_source_yaml(self) -> None:
        recs = self._make_records()
        result = trade_to_source_yaml(
            recs,
            source_url="https://comtradeapi.un.org/",
            flow="X",
            year=2023,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "aggregator"
        assert result["slug"].startswith("ct-")

    def test_empty_records_raises(self) -> None:
        with pytest.raises(ComtradeClientError, match="No trade records"):
            trade_to_primitive_yaml(
                (),
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
            )


# ═══════════════════════════════════════════════════════════════════
# FDIC connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.fdic import (
    FDICClient,
    _parse_failure,
    _parse_financial,
    _parse_institution,
    financial_to_primitive_yaml,
    financial_to_source_yaml,
    institution_count_to_primitive_yaml,
)
from strata.connectors.fdic import (
    FinancialRecord as FDICFinancialRecord,
)
from strata.connectors.fdic import (
    _safe_float as fdic_safe_float,
)
from strata.connectors.fdic import (
    _safe_int as fdic_safe_int,
)


class TestFDICParsing:
    def test_safe_float_valid(self) -> None:
        assert fdic_safe_float("123456.78") == 123456.78
        assert fdic_safe_float(42) == 42.0
        assert fdic_safe_float(0) == 0.0

    def test_safe_float_none(self) -> None:
        assert fdic_safe_float(None) is None
        assert fdic_safe_float("abc") is None

    def test_safe_int_valid(self) -> None:
        assert fdic_safe_int("12345") == 12345
        assert fdic_safe_int(42) == 42

    def test_safe_int_none(self) -> None:
        assert fdic_safe_int(None) is None
        assert fdic_safe_int("abc") is None

    def test_parse_financial(self) -> None:
        raw: dict[str, Any] = {
            "data": {
                "CERT": "12345",
                "REPNM": "Test Bank",
                "REPDTE": "20231231",
                "ASSET": "5000000",
                "DEP": "4000000",
                "NETINC": "100000",
                "INTINC": "200000",
                "NONII": "50000",
                "ROA": "1.25",
                "ROE": "10.5",
                "STNAME": "California",
                "CITY": "San Francisco",
            }
        }
        rec = _parse_financial(raw)
        assert rec.cert == 12345
        assert rec.name == "Test Bank"
        assert rec.assets == 5000000.0
        assert rec.deposits == 4000000.0
        assert rec.roa == 1.25

    def test_parse_institution(self) -> None:
        raw: dict[str, Any] = {
            "data": {
                "CERTNUM": "99999",
                "INSTNAME": "Big National Bank",
                "CITY": "New York",
                "STNAME": "New York",
                "ZIP": "10001",
                "ASSET": "100000000",
                "DEP": "80000000",
                "ACTIVE": "1",
                "SPECGRP": "Commercial Lending",
                "CHARTER_CLASS": "N",
                "FED_RSSD": "54321",
            }
        }
        rec = _parse_institution(raw)
        assert rec.cert == 99999
        assert rec.name == "Big National Bank"
        assert rec.active is True
        assert rec.assets == 100000000.0

    def test_parse_failure(self) -> None:
        raw: dict[str, Any] = {
            "data": {
                "CERT": "11111",
                "NAME": "Failed Bank Inc.",
                "CITY": "Somewhere",
                "STATE": "TX",
                "FAILDATE": "20230315",
                "SAVR": "Acquiring Corp",
                "FUND": "DIF",
                "COST": "5000000",
            }
        }
        rec = _parse_failure(raw)
        assert rec.cert == 11111
        assert rec.name == "Failed Bank Inc."
        assert rec.closing_date == "20230315"
        assert rec.estimated_loss == 5000000.0


class TestFDICClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = FDICClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with FDICClient(cache_dir=tmp_path) as client:
            assert client is not None


class TestFDICConverters:
    def _make_financial_record(self) -> FDICFinancialRecord:
        return FDICFinancialRecord(
            cert=12345,
            name="Test Bank",
            report_date="20231231",
            assets=5000000.0,
            deposits=4000000.0,
            net_income=100000.0,
            interest_income=200000.0,
            non_interest_income=50000.0,
            roa=1.25,
            roe=10.5,
            state="California",
            city="San Francisco",
        )

    def test_financial_to_primitive_yaml(self) -> None:
        rec = self._make_financial_record()
        result = financial_to_primitive_yaml(
            rec,
            concept_slug="banking-assets",
            primitive_slug="fdic-bank-assets-2023",
            name="Test Bank assets",
            description="FDIC Call Report assets",
            field="ASSET",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 5000000.0
        assert result["source"]["tier"] == "regulator"
        assert result["as_of"] == "2023-12-31"

    def test_financial_to_source_yaml(self) -> None:
        rec = self._make_financial_record()
        result = financial_to_source_yaml(rec, field="DEP")
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("fdic-")

    def test_institution_count_to_primitive_yaml(self) -> None:
        result = institution_count_to_primitive_yaml(
            4500,
            concept_slug="us-banking",
            primitive_slug="fdic-active-banks",
            name="Active FDIC-insured banks",
            description="Count of active banks",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 4500
        assert result["unit"]["dimension"] == "count"

    def test_financial_field_mapping(self) -> None:
        rec = self._make_financial_record()
        result = financial_to_primitive_yaml(
            rec,
            concept_slug="test",
            primitive_slug="test",
            name="test",
            description="test",
            field="NETINC",
        )
        assert result["value"] == 100000.0


# ═══════════════════════════════════════════════════════════════════
# CMS connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.cms import (
    CMSClient,
    CMSDataset,
    CMSState,
    EnrollmentRecord,
    SpendingRecord,
    _parse_enrollment,
    _parse_spending,
    cms_to_source_yaml,
    enrollment_to_primitive_yaml,
    spending_to_primitive_yaml,
)
from strata.connectors.cms import (
    _safe_float as cms_safe_float,
)
from strata.connectors.cms import (
    _safe_int as cms_safe_int,
)


class TestCMSParsing:
    def test_safe_float_with_dollar_sign(self) -> None:
        assert cms_safe_float("$1,234,567.89") == 1234567.89

    def test_safe_float_none(self) -> None:
        assert cms_safe_float(None) is None

    def test_safe_int_with_comma(self) -> None:
        assert cms_safe_int("1,234,567") == 1234567

    def test_parse_enrollment_basic(self) -> None:
        raw: dict[str, Any] = {
            "year": "2022",
            "state": "CA",
            "total_enrollment": "6543210",
            "part_a_enrollment": "5000000",
            "part_b_enrollment": "4500000",
            "part_d_enrollment": "3000000",
            "medicare_advantage_enrollment": "2000000",
            "original_medicare_enrollment": "4543210",
        }
        rec = _parse_enrollment(raw)
        assert rec.year == 2022
        assert rec.state == "CA"
        assert rec.total_enrollment == 6543210
        assert rec.part_a == 5000000

    def test_parse_enrollment_alt_keys(self) -> None:
        raw: dict[str, Any] = {
            "Year": "2023",
            "State": "NY",
            "Total_Enrollment": "4000000",
        }
        rec = _parse_enrollment(raw)
        assert rec.year == 2023
        assert rec.state == "NY"
        assert rec.total_enrollment == 4000000

    def test_parse_spending_basic(self) -> None:
        raw: dict[str, Any] = {
            "year": "2022",
            "state": "TX",
            "total_spending": "50000000000",
            "per_capita_spending": "12500",
            "beneficiaries": "4000000",
            "total_claims": "100000000",
            "hospital_spending": "20000000000",
            "physician_spending": "15000000000",
        }
        rec = _parse_spending(raw)
        assert rec.year == 2022
        assert rec.state == "TX"
        assert rec.total_spending == 50000000000.0
        assert rec.per_capita == 12500.0


class TestCMSClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = CMSClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with CMSClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert CMSDataset.MEDICARE_ENROLLMENT == "medicare-total-enrollment"
        assert CMSState.CA == "CA"


class TestCMSConverters:
    def _make_enrollment(self) -> EnrollmentRecord:
        return EnrollmentRecord(
            year=2022,
            state="CA",
            total_enrollment=6543210,
            part_a=5000000,
            part_b=4500000,
            part_d=3000000,
            medicare_advantage=2000000,
            original_medicare=4543210,
        )

    def _make_spending(self) -> SpendingRecord:
        return SpendingRecord(
            year=2022,
            state="TX",
            total_spending=50000000000.0,
            per_capita=12500.0,
            beneficiaries=4000000,
            claims=100000000,
            hospital_spending=20000000000.0,
            physician_spending=15000000000.0,
        )

    def test_enrollment_to_primitive_yaml(self) -> None:
        rec = self._make_enrollment()
        result = enrollment_to_primitive_yaml(
            rec,
            concept_slug="medicare-enrollment",
            primitive_slug="cms-enrollment-ca-2022",
            name="Medicare enrollment CA",
            description="Total Medicare enrollment in CA",
            source_url="https://data.cms.gov/",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 6543210
        assert result["source"]["tier"] == "regulator"
        assert result["unit"]["dimension"] == "people"

    def test_spending_to_primitive_yaml(self) -> None:
        rec = self._make_spending()
        result = spending_to_primitive_yaml(
            rec,
            concept_slug="medicare-spending",
            primitive_slug="cms-spending-tx-2022",
            name="Medicare spending TX",
            description="Total Medicare spending in TX",
            source_url="https://data.cms.gov/",
            value_field="total_spending",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 50000000000.0
        assert result["source"]["tier"] == "regulator"

    def test_spending_per_capita_field(self) -> None:
        rec = self._make_spending()
        result = spending_to_primitive_yaml(
            rec,
            concept_slug="test",
            primitive_slug="test",
            name="test",
            description="test",
            source_url="test",
            value_field="per_capita",
        )
        assert result["value"] == 12500.0

    def test_cms_to_source_yaml(self) -> None:
        result = cms_to_source_yaml(
            dataset=CMSDataset.MEDICARE_ENROLLMENT,
            state="CA",
            year=2022,
            source_url="https://data.cms.gov/",
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert "cms-" in result["slug"]


# ═══════════════════════════════════════════════════════════════════
# EIA connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.eia import (
    EIAClient,
    EIAClientError,
    EIADataPoint,
    EIAFrequency,
    EIARoute,
    EIASector,
    _parse_metadata,
    datapoint_to_primitive_yaml,
    datapoint_to_source_yaml,
)
from strata.connectors.eia import (
    _parse_data_point as eia_parse_data_point,
)
from strata.connectors.eia import (
    _parse_data_response as eia_parse_data_response,
)
from strata.connectors.eia import (
    _safe_float as eia_safe_float,
)


class TestEIAParsing:
    def test_safe_float_valid(self) -> None:
        assert eia_safe_float(123.45) == 123.45
        assert eia_safe_float("100") == 100.0

    def test_safe_float_none(self) -> None:
        assert eia_safe_float(None) is None
        assert eia_safe_float("N/A") is None

    def test_parse_data_point(self) -> None:
        raw: dict[str, Any] = {
            "period": "2023-12",
            "stateId": "US",
            "stateDescription": "United States",
            "sectorId": "RES",
            "sectorName": "Residential",
            "value": 15.72,
            "units": "cents per kilowatthour",
            "seriesId": "ELEC.PRICE.US-RES.M",
        }
        dp = eia_parse_data_point(raw)
        assert dp.period == "2023-12"
        assert dp.state == "US"
        assert dp.value == 15.72
        assert dp.units == "cents per kilowatthour"
        assert dp.series_id == "ELEC.PRICE.US-RES.M"

    def test_parse_data_point_null_value(self) -> None:
        raw: dict[str, Any] = {
            "period": "2023-01",
            "stateId": "US",
            "stateDescription": "US",
            "sectorId": "ALL",
            "sectorName": "All",
            "value": None,
            "units": "kWh",
        }
        dp = eia_parse_data_point(raw)
        assert dp.value is None

    def test_parse_data_response(self) -> None:
        raw: dict[str, Any] = {
            "response": {
                "total": 2,
                "data": [
                    {
                        "period": "2023-12",
                        "stateId": "US",
                        "stateDescription": "US",
                        "sectorId": "RES",
                        "sectorName": "Residential",
                        "value": 15.72,
                        "units": "cents/kWh",
                    },
                    {
                        "period": "2023-11",
                        "stateId": "US",
                        "stateDescription": "US",
                        "sectorId": "RES",
                        "sectorName": "Residential",
                        "value": 15.50,
                        "units": "cents/kWh",
                    },
                ],
            }
        }
        resp = eia_parse_data_response(raw, kind="data")
        assert resp.total == 2
        assert len(resp.data_points) == 2
        assert resp.data_points[0].value == 15.72

    def test_parse_metadata(self) -> None:
        raw: dict[str, Any] = {
            "name": "Electricity Retail Sales",
            "description": "Monthly retail electricity data",
            "frequency": [{"id": "monthly"}, {"id": "annual"}],
            "facets": {"stateId": {}, "sectorId": {}},
            "data": {"price": {}, "sales": {}},
        }
        meta = _parse_metadata(raw, route="electricity/retail-sales")
        assert meta.name == "Electricity Retail Sales"
        assert "monthly" in meta.frequency
        assert "stateId" in meta.facets


class TestEIAClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = EIAClient(api_key="test-key", cache_dir=tmp_path)
        assert client._key == "test-key"
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with EIAClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert EIARoute.ELECTRICITY_RETAIL == "electricity/retail-sales"
        assert EIAFrequency.ANNUAL == "annual"
        assert EIASector.RESIDENTIAL == "RES"


class TestEIAConverters:
    def _make_data_points(self) -> tuple[EIADataPoint, ...]:
        return (
            EIADataPoint(
                period="2023-12",
                state="US",
                state_name="United States",
                sector="RES",
                sector_name="Residential",
                value=15.72,
                units="cents per kilowatthour",
                series_id="ELEC.PRICE.US-RES.M",
            ),
            EIADataPoint(
                period="2023-11",
                state="US",
                state_name="United States",
                sector="RES",
                sector_name="Residential",
                value=15.50,
                units="cents per kilowatthour",
                series_id="ELEC.PRICE.US-RES.M",
            ),
        )

    def test_datapoint_to_primitive_yaml(self) -> None:
        dps = self._make_data_points()
        result = datapoint_to_primitive_yaml(
            dps,
            route="electricity/retail-sales",
            concept_slug="us-electricity-prices",
            primitive_slug="eia-elec-price-2023",
            name="US residential electricity price",
            description="EIA retail electricity price",
            source_url="https://www.eia.gov/",
            unit_kind="rate",
            unit_dimension="price",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 15.72
        assert result["source"]["tier"] == "regulator"

    def test_datapoint_to_source_yaml(self) -> None:
        dps = self._make_data_points()
        result = datapoint_to_source_yaml(
            dps,
            route="electricity/retail-sales",
            source_url="https://www.eia.gov/",
            year=2023,
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("eia-")

    def test_empty_data_points_raises(self) -> None:
        with pytest.raises(EIAClientError, match="No data points"):
            datapoint_to_primitive_yaml(
                (),
                route="test",
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
                source_url="test",
            )


# ═══════════════════════════════════════════════════════════════════
# USDA NASS connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.usda_nass import (
    NASSAggLevel,
    NASSClient,
    NASSClientError,
    NASSCommodity,
    NASSRecord,
    NASSSource,
    NASSStatistic,
    record_to_primitive_yaml,
    record_to_source_yaml,
)
from strata.connectors.usda_nass import (
    _parse_data_response as nass_parse_data_response,
)
from strata.connectors.usda_nass import (
    _parse_record as nass_parse_record,
)
from strata.connectors.usda_nass import (
    _parse_value as nass_parse_value,
)


class TestNASSParsing:
    def test_parse_value_valid(self) -> None:
        assert nass_parse_value("15,148,000,000") == 15148000000.0
        assert nass_parse_value("123.45") == 123.45

    def test_parse_value_suppressed(self) -> None:
        assert nass_parse_value("(D)") is None
        assert nass_parse_value("(NA)") is None
        assert nass_parse_value("(Z)") is None
        assert nass_parse_value("(S)") is None
        assert nass_parse_value("") is None

    def test_parse_record_basic(self) -> None:
        raw: dict[str, Any] = {
            "source_desc": "SURVEY",
            "sector_desc": "CROPS",
            "group_desc": "FIELD CROPS",
            "commodity_desc": "CORN",
            "class_desc": "ALL CLASSES",
            "prodn_practice_desc": "ALL PRODUCTION PRACTICES",
            "util_practice_desc": "ALL UTILIZATION PRACTICES",
            "statisticcat_desc": "PRODUCTION",
            "unit_desc": "BU",
            "short_desc": "CORN - PRODUCTION, MEASURED IN BU",
            "domain_desc": "TOTAL",
            "domaincat_desc": "NOT SPECIFIED",
            "agg_level_desc": "NATIONAL",
            "state_alpha": "US",
            "state_name": "US TOTAL",
            "state_fips_code": "00",
            "county_name": "",
            "county_code": "",
            "year": 2023,
            "freq_desc": "ANNUAL",
            "begin_code": 0,
            "end_code": 0,
            "reference_period_desc": "YEAR",
            "Value": "15,148,000,000",
        }
        rec = nass_parse_record(raw)
        assert rec.commodity == "CORN"
        assert rec.statistic_category == "PRODUCTION"
        assert rec.value == 15148000000.0
        assert rec.year == 2023
        assert rec.state_alpha == "US"

    def test_parse_data_response(self) -> None:
        raw: dict[str, Any] = {
            "data": [
                {
                    "commodity_desc": "CORN",
                    "statisticcat_desc": "PRODUCTION",
                    "year": 2023,
                    "Value": "15,148,000,000",
                    "unit_desc": "BU",
                    "agg_level_desc": "NATIONAL",
                    "state_alpha": "US",
                    "state_name": "US TOTAL",
                    "freq_desc": "ANNUAL",
                    "reference_period_desc": "YEAR",
                    "source_desc": "SURVEY",
                    "sector_desc": "CROPS",
                    "group_desc": "FIELD CROPS",
                    "class_desc": "ALL CLASSES",
                    "prodn_practice_desc": "ALL",
                    "util_practice_desc": "ALL",
                    "short_desc": "CORN - PRODUCTION",
                    "domain_desc": "TOTAL",
                    "domaincat_desc": "NOT SPECIFIED",
                    "state_fips_code": "00",
                    "county_name": "",
                    "county_code": "",
                }
            ]
        }
        resp = nass_parse_data_response(raw)
        assert resp.kind == "data"
        assert len(resp.records) == 1
        assert resp.records[0].commodity == "CORN"


class TestNASSClient:
    def test_client_requires_api_key(self, tmp_path: Path) -> None:
        # Should raise when no key provided and env var not set
        import os

        old_val = os.environ.pop("STRATA_USDA_NASS_API_KEY", None)
        try:
            with pytest.raises(NASSClientError, match="API key required"):
                NASSClient(cache_dir=tmp_path)
        finally:
            if old_val is not None:
                os.environ["STRATA_USDA_NASS_API_KEY"] = old_val

    def test_client_init_with_key(self, tmp_path: Path) -> None:
        client = NASSClient(api_key="test-key-123", cache_dir=tmp_path)
        assert client._key == "test-key-123"
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with NASSClient(api_key="test-key", cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert NASSCommodity.CORN == "CORN"
        assert NASSStatistic.PRODUCTION == "PRODUCTION"
        assert NASSSource.SURVEY == "SURVEY"
        assert NASSAggLevel.NATIONAL == "NATIONAL"


class TestNASSConverters:
    def _make_records(self) -> tuple[NASSRecord, ...]:
        return (
            NASSRecord(
                source="SURVEY",
                sector="CROPS",
                group="FIELD CROPS",
                commodity="CORN",
                class_desc="ALL CLASSES",
                prodn_practice="ALL PRODUCTION PRACTICES",
                util_practice="ALL UTILIZATION PRACTICES",
                statistic_category="PRODUCTION",
                unit="BU",
                short_desc="CORN - PRODUCTION, MEASURED IN BU",
                domain="TOTAL",
                domaincat="NOT SPECIFIED",
                agg_level="NATIONAL",
                state_alpha="US",
                state_name="US TOTAL",
                state_fips="00",
                county_name="",
                county_code="",
                year=2023,
                frequency="ANNUAL",
                reference_period="YEAR",
                value=15148000000.0,
                cv_pct="",
            ),
        )

    def test_record_to_primitive_yaml(self) -> None:
        recs = self._make_records()
        result = record_to_primitive_yaml(
            recs,
            concept_slug="us-corn-production",
            primitive_slug="nass-corn-prod-2023",
            name="US corn production",
            description="USDA NASS corn production",
            year=2023,
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 15148000000.0
        assert result["source"]["tier"] == "regulator"
        assert result["geo"]["level"] == "country"

    def test_record_to_source_yaml(self) -> None:
        recs = self._make_records()
        result = record_to_source_yaml(recs, year=2023)
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("nass-")

    def test_empty_records_raises(self) -> None:
        with pytest.raises(NASSClientError, match="No NASS records"):
            record_to_primitive_yaml(
                (),
                concept_slug="test",
                primitive_slug="test",
                name="test",
                description="test",
            )


# ═══════════════════════════════════════════════════════════════════
# FAA connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.faa import (
    Airport,
    AirportSummary,
    FAAAirportType,
    FAAClient,
    FAAState,
    _parse_airport,
    _parse_airport_status,
    _parse_feature_response,
    airport_to_primitive_yaml,
    airport_to_source_yaml,
    passenger_count_to_primitive_yaml,
)


class TestFAAParsing:
    def test_parse_airport_basic(self) -> None:
        attrs: dict[str, Any] = {
            "FAC_NAME": "SAN FRANCISCO INTL",
            "LOCID": "SFO",
            "CITY": "SAN FRANCISCO",
            "STATE": "CA",
            "COUNTY": "SAN MATEO",
            "ELEV": 13.0,
            "LATITUDE": 37.6189,
            "LONGITUDE": -122.3750,
            "FAC_TYPE": "AIRPORT",
            "OWNER_TYPE": "PU",
            "PASSENGERS": 57000000,
            "OPERATIONS": 450000,
            "REGION": "AWP",
        }
        airport = _parse_airport(attrs)
        assert airport.loc_id == "SFO"
        assert airport.state == "CA"
        assert airport.passengers == 57000000
        assert airport.elevation == 13.0

    def test_parse_airport_missing_fields(self) -> None:
        attrs: dict[str, Any] = {
            "FAC_NAME": "SMALL FIELD",
            "LOCID": "XYZ",
        }
        airport = _parse_airport(attrs)
        assert airport.loc_id == "XYZ"
        assert airport.passengers == 0
        assert airport.elevation == 0.0
        assert airport.state == ""

    def test_parse_airport_status(self) -> None:
        raw: dict[str, Any] = {
            "Name": "San Francisco International",
            "City": "San Francisco",
            "State": "California",
            "IATA": "SFO",
            "ICAO": "KSFO",
            "Delay": True,
            "Status": [{"Reason": "Weather", "Type": "Ground Delay"}],
            "Weather": {"temp": "60"},
        }
        status = _parse_airport_status(raw)
        assert status.iata == "SFO"
        assert status.delay is True
        assert status.reason == "Weather"
        assert status.delay_type == "Ground Delay"

    def test_parse_airport_status_no_delay(self) -> None:
        raw: dict[str, Any] = {
            "Name": "Test",
            "City": "Test",
            "State": "CA",
            "IATA": "TST",
            "ICAO": "KTST",
            "Delay": False,
            "Status": [],
        }
        status = _parse_airport_status(raw)
        assert status.delay is False
        assert status.reason == ""

    def test_parse_feature_response(self) -> None:
        body: dict[str, Any] = {
            "features": [
                {
                    "attributes": {
                        "FAC_NAME": "SFO",
                        "LOCID": "SFO",
                        "CITY": "SF",
                        "STATE": "CA",
                        "PASSENGERS": 57000000,
                    }
                },
                {
                    "attributes": {
                        "FAC_NAME": "LAX",
                        "LOCID": "LAX",
                        "CITY": "LA",
                        "STATE": "CA",
                        "PASSENGERS": 88000000,
                    }
                },
            ],
            "exceededTransferLimit": False,
        }
        airports, exceeded = _parse_feature_response(body)
        assert len(airports) == 2
        assert exceeded is False
        assert airports[0].loc_id == "SFO"


class TestFAAClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = FAAClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with FAAClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert FAAState.CA == "CA"
        assert FAAAirportType.AIRPORT == "AIRPORT"


class TestFAAConverters:
    def _make_airport(self) -> Airport:
        return Airport(
            fac_name="SAN FRANCISCO INTL",
            loc_id="SFO",
            city="SAN FRANCISCO",
            state="CA",
            county="SAN MATEO",
            elevation=13.0,
            latitude=37.6189,
            longitude=-122.375,
            airport_type="AIRPORT",
            owner_type="PU",
            passengers=57000000,
            operations=450000,
            region="AWP",
        )

    def _make_summary(self) -> AirportSummary:
        return AirportSummary(
            state="CA",
            count=250,
            total_passengers=200000000,
            total_operations=3000000,
        )

    def test_airport_to_primitive_yaml(self) -> None:
        airport = self._make_airport()
        result = airport_to_primitive_yaml(
            airport,
            concept_slug="us-aviation",
            primitive_slug="faa-sfo-passengers",
            name="SFO annual passengers",
            description="FAA airport passenger data",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 57000000
        assert result["source"]["tier"] == "regulator"
        assert result["geo"]["codes"] == ["CA"]

    def test_airport_to_source_yaml(self) -> None:
        airport = self._make_airport()
        result = airport_to_source_yaml(airport)
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert result["slug"].startswith("faa-airport-")

    def test_passenger_count_to_primitive_yaml(self) -> None:
        summary = self._make_summary()
        result = passenger_count_to_primitive_yaml(
            summary,
            concept_slug="us-aviation",
            primitive_slug="faa-ca-passengers",
            name="California total passengers",
            description="FAA aggregate passenger count",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 200000000
        assert result["unit"]["dimension"] == "people"
        assert result["unit"]["kind"] == "flow"


# ═══════════════════════════════════════════════════════════════════
# openFDA connector tests
# ═══════════════════════════════════════════════════════════════════

from strata.connectors.openfda import (
    CountResult,
    Device510k,
    FDAEndpoint,
    FDARecallClass,
    OpenFDAClient,
    _parse_count_result,
    _parse_device_510k,
    _parse_drug_event,
    _parse_drug_label,
    _parse_enforcement,
    clearance_count_to_primitive_yaml,
    event_count_to_primitive_yaml,
    fda_to_source_yaml,
)


class TestOpenFDAParsing:
    def test_parse_drug_event_basic(self) -> None:
        raw: dict[str, Any] = {
            "safetyreportid": "10001234",
            "receivedate": "20230615",
            "serious": "1",
            "patient": {
                "drug": [
                    {
                        "openfda": {"brand_name": ["Aspirin"]},
                        "medicinalproduct": "ASPIRIN",
                    }
                ],
                "reaction": [
                    {"reactionmeddrapt": "Nausea", "reactionoutcome": "1"},
                    {"reactionmeddrapt": "Headache", "reactionoutcome": "1"},
                ],
            },
            "occurcountry": "US",
        }
        event = _parse_drug_event(raw)
        assert event.safety_report_id == "10001234"
        assert event.serious is True
        assert "Aspirin" in event.drug_names
        assert "Nausea" in event.reactions
        assert event.report_country == "US"

    def test_parse_drug_event_not_serious(self) -> None:
        raw: dict[str, Any] = {
            "safetyreportid": "10005678",
            "receivedate": "20230101",
            "serious": "2",
            "patient": {"drug": [], "reaction": []},
            "occurcountry": "GB",
        }
        event = _parse_drug_event(raw)
        assert event.serious is False
        assert event.drug_names == ()
        assert event.reactions == ()

    def test_parse_drug_label(self) -> None:
        raw: dict[str, Any] = {
            "set_id": "abc-def-123",
            "openfda": {
                "brand_name": ["TestDrug"],
                "generic_name": ["testdruggeneric"],
                "manufacturer_name": ["Pharma Inc."],
                "route": ["ORAL"],
                "substance_name": ["TEST SUBSTANCE"],
                "product_type": ["HUMAN PRESCRIPTION DRUG"],
            },
        }
        label = _parse_drug_label(raw)
        assert label.set_id == "abc-def-123"
        assert label.brand_name == "TestDrug"
        assert label.manufacturer == "Pharma Inc."

    def test_parse_device_510k(self) -> None:
        raw: dict[str, Any] = {
            "k_number": "K230001",
            "applicant": "MedTech Inc.",
            "device_name": "Blood Glucose Monitor",
            "product_code": "NBW",
            "decision_date": "20230301",
            "decision_description": "SUBSTANTIALLY EQUIVALENT",
            "review_advisory_committee": "Clinical Chemistry",
            "openfda": {"device_class": ["2"]},
        }
        device = _parse_device_510k(raw)
        assert device.k_number == "K230001"
        assert device.applicant == "MedTech Inc."
        assert device.device_class == "2"

    def test_parse_enforcement(self) -> None:
        raw: dict[str, Any] = {
            "recall_number": "D-1234-2023",
            "status": "Ongoing",
            "classification": "Class II",
            "product_description": "Test Product",
            "reason_for_recall": "Mislabeling",
            "recalling_firm": "PharmaCorp",
            "city": "Boston",
            "state": "MA",
            "country": "United States",
            "recall_initiation_date": "20230901",
            "voluntary_mandated": "Voluntary: Firm Initiated",
        }
        enforcement = _parse_enforcement(raw)
        assert enforcement.recall_number == "D-1234-2023"
        assert enforcement.classification == "Class II"
        assert enforcement.recalling_firm == "PharmaCorp"

    def test_parse_count_result(self) -> None:
        raw: dict[str, Any] = {"term": "Nausea", "count": 45678}
        cr = _parse_count_result(raw)
        assert cr.term == "Nausea"
        assert cr.count == 45678


class TestOpenFDAClient:
    def test_client_init(self, tmp_path: Path) -> None:
        client = OpenFDAClient(cache_dir=tmp_path)
        assert client._http is not None
        client.close()

    def test_client_context_manager(self, tmp_path: Path) -> None:
        with OpenFDAClient(cache_dir=tmp_path) as client:
            assert client is not None

    def test_enum_values(self) -> None:
        assert FDAEndpoint.DRUG_EVENT == "drug/event"
        assert FDAEndpoint.DEVICE_510K == "device/510k"
        assert FDARecallClass.CLASS_I == "Class I"


class TestOpenFDAConverters:
    def test_event_count_to_primitive_yaml(self) -> None:
        counts = (
            CountResult(term="Nausea", count=45678),
            CountResult(term="Headache", count=23456),
            CountResult(term="Fatigue", count=12345),
        )
        result = event_count_to_primitive_yaml(
            counts,
            concept_slug="drug-safety",
            primitive_slug="fda-aspirin-events",
            name="Aspirin adverse events",
            description="Total adverse event reports for Aspirin",
            source_url="https://api.fda.gov/drug/event.json",
            drug_name="Aspirin",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 45678 + 23456 + 12345
        assert result["source"]["tier"] == "regulator"
        assert result["unit"]["dimension"] == "events"

    def test_event_count_with_explicit_total(self) -> None:
        counts = (CountResult(term="Nausea", count=100),)
        result = event_count_to_primitive_yaml(
            counts,
            concept_slug="test",
            primitive_slug="test",
            name="test",
            description="test",
            source_url="test",
            drug_name="test",
            total=999,
        )
        assert result["value"] == 999

    def test_clearance_count_to_primitive_yaml(self) -> None:
        devices = (
            Device510k(
                k_number="K230001",
                applicant="MedTech",
                device_name="BGM",
                product_code="NBW",
                decision_date="20230301",
                decision="SE",
                review_advisory_committee="CC",
                device_class="2",
            ),
            Device510k(
                k_number="K230002",
                applicant="MedTech2",
                device_name="BGM v2",
                product_code="NBW",
                decision_date="20230401",
                decision="SE",
                review_advisory_committee="CC",
                device_class="2",
            ),
        )
        result = clearance_count_to_primitive_yaml(
            devices,
            concept_slug="medtech",
            primitive_slug="fda-510k-nbw",
            name="510(k) clearances for BGM",
            description="Count of 510(k) clearances",
            source_url="https://api.fda.gov/device/510k.json",
            product_code="NBW",
        )
        assert result["kind"] == "atomic_primitive"
        assert result["value"] == 2
        assert result["unit"]["dimension"] == "clearances"

    def test_fda_to_source_yaml(self) -> None:
        result = fda_to_source_yaml(
            source_slug="fda-drug-events-aspirin",
            source_url="https://api.fda.gov/drug/event.json",
            description="openFDA adverse event data for Aspirin",
            snapshot_content={"drug": "Aspirin", "total": 81479},
        )
        assert result["kind"] == "source_registry"
        assert result["tier"] == "regulator"
        assert len(result["snapshot_sha256"]) == 64


# ═══════════════════════════════════════════════════════════════════
# Extended cache tests for new connectors
# ═══════════════════════════════════════════════════════════════════


class TestDiskCacheNewConnectors:
    def test_oecd_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.oecd import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"dataSets": [{"observations": {"0": [42.0]}}]}
        cache.put("oecd-test", data)
        result = cache.get("oecd-test")
        assert result is not None
        cached_data, age = result
        assert "dataSets" in cached_data
        assert age < 1.0

    def test_eurostat_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.eurostat import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"id": ["geo", "time"], "value": {"0": 100.0}}
        cache.put("es-test", data)
        result = cache.get("es-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["id"] == ["geo", "time"]

    def test_comtrade_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.comtrade import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"data": [{"reporterISO": "USA"}], "count": 1}
        cache.put("ct-test", data)
        result = cache.get("ct-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["count"] == 1

    def test_fdic_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.fdic import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"data": [{"ASSET": "100000"}], "meta": {"total": 1}}
        cache.put("fdic-test", data)
        result = cache.get("fdic-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["meta"]["total"] == 1

    def test_cms_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.cms import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: list[Any] = [{"year": "2022", "state": "CA"}]
        cache.put("cms-test", data)
        result = cache.get("cms-test")
        assert result is not None
        cached_data, _age = result
        assert len(cached_data) == 1

    def test_eia_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.eia import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"response": {"data": [{"value": 15.72}], "total": 1}}
        cache.put("eia-test", data)
        result = cache.get("eia-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["response"]["total"] == 1

    def test_nass_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.usda_nass import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"data": [{"Value": "15148000000"}]}
        cache.put("nass-test", data)
        result = cache.get("nass-test")
        assert result is not None
        cached_data, _age = result
        assert "data" in cached_data

    def test_faa_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.faa import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {"features": [{"attributes": {"LOCID": "SFO"}}]}
        cache.put("faa-test", data)
        result = cache.get("faa-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["features"][0]["attributes"]["LOCID"] == "SFO"

    def test_openfda_cache_roundtrip(self, tmp_path: Path) -> None:
        from strata.connectors.openfda import _DiskCache

        cache = _DiskCache(tmp_path, ttl_seconds=3600)
        data: dict[str, Any] = {
            "meta": {"results": {"total": 100}},
            "results": [{"safetyreportid": "123"}],
        }
        cache.put("fda-test", data)
        result = cache.get("fda-test")
        assert result is not None
        cached_data, _age = result
        assert cached_data["meta"]["results"]["total"] == 100


# ═══════════════════════════════════════════════════════════════════
# Extended cross-connector consistency tests for new connectors
# ═══════════════════════════════════════════════════════════════════


class TestYAMLOutputConsistencyNewConnectors:
    """Verify all new connectors produce YAML dicts with the same shape."""

    def test_new_primitives_have_required_keys(self) -> None:
        required_keys = {
            "kind",
            "slug",
            "schema_version",
            "concept_slug",
            "name",
            "description",
            "value",
            "unit",
            "as_of",
            "geo",
            "geo_perspective",
            "distribution_shape",
            "delivery_mode",
            "source",
        }
        source_keys = {"slug", "tier", "url", "accessed", "snapshot_sha256"}

        # OECD
        oecd_obs = (
            OECDObservation(
                country="USA",
                frequency="A",
                time_period="2023",
                value=26949.6,
                unit_measure="USD",
                flags="",
                series_key="0:0",
                dataflow_id="DF_GDP",
            ),
        )
        oecd_prim = oecd_observation_to_primitive_yaml(
            oecd_obs,
            concept_slug="test",
            primitive_slug="oecd-test",
            name="test",
            description="test",
            source_url="https://oecd.org",
            year=2023,
        )
        assert required_keys.issubset(oecd_prim.keys()), (
            f"OECD missing: {required_keys - oecd_prim.keys()}"
        )
        assert source_keys.issubset(oecd_prim["source"].keys())

        # Eurostat
        es_obs = (
            EurostatObservation(
                dataset="nama_10_gdp",
                geo="DE",
                time_period="2023",
                value=4082300.0,
                unit="CP_MEUR",
                freq="A",
                status_flag="",
            ),
        )
        es_prim = observation_to_primitive_yaml(
            es_obs,
            concept_slug="test",
            primitive_slug="es-test",
            name="test",
            description="test",
            source_url="https://eurostat.eu",
            year=2023,
        )
        assert required_keys.issubset(es_prim.keys()), (
            f"Eurostat missing: {required_keys - es_prim.keys()}"
        )
        assert source_keys.issubset(es_prim["source"].keys())

        # Comtrade
        ct_recs = (
            TradeRecord(
                reporter_code=842,
                reporter_iso="USA",
                reporter_name="US",
                partner_code=0,
                partner_iso="W00",
                partner_name="World",
                flow_code="X",
                flow_desc="Export",
                period=2023,
                commodity_code="TOTAL",
                commodity_desc="All",
                primary_value=1000000.0,
                net_weight=None,
                fob_value=None,
                cif_value=None,
            ),
        )
        ct_prim = trade_to_primitive_yaml(
            ct_recs,
            concept_slug="test",
            primitive_slug="ct-test",
            name="test",
            description="test",
            source_url="https://comtrade.un.org",
        )
        assert required_keys.issubset(ct_prim.keys()), (
            f"Comtrade missing: {required_keys - ct_prim.keys()}"
        )
        assert source_keys.issubset(ct_prim["source"].keys())

        # FDIC
        fdic_rec = FDICFinancialRecord(
            cert=12345,
            name="Test",
            report_date="20231231",
            assets=5e6,
            deposits=4e6,
            net_income=1e5,
            interest_income=2e5,
            non_interest_income=5e4,
            roa=1.25,
            roe=10.5,
            state="CA",
            city="SF",
        )
        fdic_prim = financial_to_primitive_yaml(
            fdic_rec,
            concept_slug="test",
            primitive_slug="fdic-test",
            name="test",
            description="test",
        )
        assert required_keys.issubset(fdic_prim.keys()), (
            f"FDIC missing: {required_keys - fdic_prim.keys()}"
        )
        assert source_keys.issubset(fdic_prim["source"].keys())

        # CMS enrollment
        cms_enr = EnrollmentRecord(
            year=2022,
            state="CA",
            total_enrollment=6543210,
            part_a=5000000,
            part_b=4500000,
            part_d=3000000,
            medicare_advantage=2000000,
            original_medicare=4543210,
        )
        cms_prim = enrollment_to_primitive_yaml(
            cms_enr,
            concept_slug="test",
            primitive_slug="cms-test",
            name="test",
            description="test",
            source_url="https://cms.gov",
        )
        assert required_keys.issubset(cms_prim.keys()), (
            f"CMS missing: {required_keys - cms_prim.keys()}"
        )
        assert source_keys.issubset(cms_prim["source"].keys())

        # EIA
        eia_dps = (
            EIADataPoint(
                period="2023",
                state="US",
                state_name="US",
                sector="RES",
                sector_name="Residential",
                value=15.72,
                units="cents/kWh",
                series_id="TEST",
            ),
        )
        eia_prim = datapoint_to_primitive_yaml(
            eia_dps,
            route="electricity/retail-sales",
            concept_slug="test",
            primitive_slug="eia-test",
            name="test",
            description="test",
            source_url="https://eia.gov",
        )
        assert required_keys.issubset(eia_prim.keys()), (
            f"EIA missing: {required_keys - eia_prim.keys()}"
        )
        assert source_keys.issubset(eia_prim["source"].keys())

        # NASS
        nass_recs = (
            NASSRecord(
                source="SURVEY",
                sector="CROPS",
                group="FIELD CROPS",
                commodity="CORN",
                class_desc="ALL",
                prodn_practice="ALL",
                util_practice="ALL",
                statistic_category="PRODUCTION",
                unit="BU",
                short_desc="CORN PRODUCTION",
                domain="TOTAL",
                domaincat="",
                agg_level="NATIONAL",
                state_alpha="US",
                state_name="US TOTAL",
                state_fips="00",
                county_name="",
                county_code="",
                year=2023,
                frequency="ANNUAL",
                reference_period="YEAR",
                value=15148000000.0,
                cv_pct="",
            ),
        )
        nass_prim = record_to_primitive_yaml(
            nass_recs,
            concept_slug="test",
            primitive_slug="nass-test",
            name="test",
            description="test",
        )
        assert required_keys.issubset(nass_prim.keys()), (
            f"NASS missing: {required_keys - nass_prim.keys()}"
        )
        assert source_keys.issubset(nass_prim["source"].keys())

        # FAA
        faa_airport = Airport(
            fac_name="SFO",
            loc_id="SFO",
            city="SF",
            state="CA",
            county="SM",
            elevation=13.0,
            latitude=37.6,
            longitude=-122.4,
            airport_type="AIRPORT",
            owner_type="PU",
            passengers=57000000,
            operations=450000,
            region="AWP",
        )
        faa_prim = airport_to_primitive_yaml(
            faa_airport,
            concept_slug="test",
            primitive_slug="faa-test",
            name="test",
            description="test",
        )
        assert required_keys.issubset(faa_prim.keys()), (
            f"FAA missing: {required_keys - faa_prim.keys()}"
        )
        assert source_keys.issubset(faa_prim["source"].keys())

        # openFDA
        fda_counts = (CountResult(term="Nausea", count=100),)
        fda_prim = event_count_to_primitive_yaml(
            fda_counts,
            concept_slug="test",
            primitive_slug="fda-test",
            name="test",
            description="test",
            source_url="https://api.fda.gov",
            drug_name="test",
        )
        assert required_keys.issubset(fda_prim.keys()), (
            f"openFDA missing: {required_keys - fda_prim.keys()}"
        )
        assert source_keys.issubset(fda_prim["source"].keys())

    def test_new_sources_have_required_keys(self) -> None:
        required_keys = {"kind", "slug", "tier", "url", "accessed", "snapshot_sha256"}

        # OECD
        oecd_obs = (
            OECDObservation(
                country="USA",
                frequency="A",
                time_period="2023",
                value=100.0,
                unit_measure="USD",
                flags="",
                series_key="0",
                dataflow_id="TEST",
            ),
        )
        oecd_src = oecd_observation_to_source_yaml(
            oecd_obs,
            source_url="https://oecd.org",
            year=2023,
        )
        assert required_keys.issubset(oecd_src.keys())

        # Eurostat
        es_obs = (
            EurostatObservation(
                dataset="test",
                geo="DE",
                time_period="2023",
                value=100.0,
                unit="CP_MEUR",
                freq="A",
                status_flag="",
            ),
        )
        es_src = observation_to_source_yaml(
            es_obs,
            source_url="https://eurostat.eu",
            year=2023,
        )
        assert required_keys.issubset(es_src.keys())

        # Comtrade
        ct_recs = (
            TradeRecord(
                reporter_code=842,
                reporter_iso="USA",
                reporter_name="US",
                partner_code=0,
                partner_iso="W00",
                partner_name="World",
                flow_code="X",
                flow_desc="Export",
                period=2023,
                commodity_code="TOTAL",
                commodity_desc="All",
                primary_value=100.0,
                net_weight=None,
                fob_value=None,
                cif_value=None,
            ),
        )
        ct_src = trade_to_source_yaml(
            ct_recs,
            source_url="https://comtrade.un.org",
        )
        assert required_keys.issubset(ct_src.keys())

        # FDIC
        fdic_rec = FDICFinancialRecord(
            cert=1,
            name="T",
            report_date="20231231",
            assets=1e6,
            deposits=1e6,
            net_income=1e4,
            interest_income=1e4,
            non_interest_income=1e3,
            roa=1.0,
            roe=10.0,
            state="CA",
            city="SF",
        )
        fdic_src = financial_to_source_yaml(fdic_rec)
        assert required_keys.issubset(fdic_src.keys())

        # CMS
        cms_src = cms_to_source_yaml(
            dataset="medicare-total-enrollment",
            source_url="https://cms.gov",
            year=2022,
        )
        assert required_keys.issubset(cms_src.keys())

        # EIA
        eia_dps = (
            EIADataPoint(
                period="2023",
                state="US",
                state_name="US",
                sector="ALL",
                sector_name="All",
                value=100.0,
                units="test",
                series_id="TEST",
            ),
        )
        eia_src = datapoint_to_source_yaml(
            eia_dps,
            route="electricity/retail-sales",
            source_url="https://eia.gov",
            year=2023,
        )
        assert required_keys.issubset(eia_src.keys())

        # NASS
        nass_recs = (
            NASSRecord(
                source="SURVEY",
                sector="CROPS",
                group="",
                commodity="CORN",
                class_desc="",
                prodn_practice="",
                util_practice="",
                statistic_category="PRODUCTION",
                unit="BU",
                short_desc="",
                domain="",
                domaincat="",
                agg_level="NATIONAL",
                state_alpha="US",
                state_name="US",
                state_fips="00",
                county_name="",
                county_code="",
                year=2023,
                frequency="ANNUAL",
                reference_period="YEAR",
                value=100.0,
                cv_pct="",
            ),
        )
        nass_src = record_to_source_yaml(nass_recs, year=2023)
        assert required_keys.issubset(nass_src.keys())

        # FAA
        faa_airport = Airport(
            fac_name="T",
            loc_id="TST",
            city="T",
            state="CA",
            county="",
            elevation=0,
            latitude=0,
            longitude=0,
            airport_type="AIRPORT",
            owner_type="PU",
            passengers=100,
            operations=10,
            region="",
        )
        faa_src = airport_to_source_yaml(faa_airport)
        assert required_keys.issubset(faa_src.keys())

        # openFDA
        fda_src = fda_to_source_yaml(
            source_slug="fda-test",
            source_url="https://api.fda.gov",
            description="test",
            snapshot_content={"test": True},
        )
        assert required_keys.issubset(fda_src.keys())
