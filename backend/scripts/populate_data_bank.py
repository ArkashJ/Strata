#!/usr/bin/env python3
"""Populate the Strata data bank with real data from all 5 connectors.

Queries BLS, FRED, Census, EDGAR, and World Bank APIs and writes YAML
primitives + sources to data/primitives/ and data/sources/.

Usage:
    cd backend && uv run python scripts/populate_data_bank.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PRIMITIVES_DIR = ROOT / "data" / "primitives"
SOURCES_DIR = ROOT / "data" / "sources"


def _write_yaml(directory: Path, slug: str, data: dict) -> Path:
    path = directory / f"{slug}.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
    return path


def populate_fred() -> list[str]:
    """FRED: GDP, employment, CPI, interest rates."""
    from strata.connectors.fred import (
        FREDClient,
        observations_to_primitive_yaml,
        observations_to_source_yaml,
    )
    from strata.config import settings

    results: list[str] = []
    queries = [
        {
            "series_id": "GDP",
            "concept_slug": "us-macroeconomy",
            "primitive_slug": "fred-us-gdp-nominal-2024",
            "name": "US nominal GDP (FRED, Q4 2024)",
            "description": "Bureau of Economic Analysis nominal GDP via FRED series GDP.",
            "source_url": "https://fred.stlouisfed.org/series/GDP",
            "year": 2024,
            "unit_kind": "flow",
            "unit_dimension": "currency",
            "unit_currency": "USD",
            "unit_denominator": "per-year",
        },
        {
            "series_id": "PAYEMS",
            "concept_slug": "us-labor-market",
            "primitive_slug": "fred-us-nonfarm-payroll-2025",
            "name": "US total nonfarm payroll (FRED PAYEMS, 2025)",
            "description": "BLS Current Employment Statistics via FRED. Thousands of persons.",
            "source_url": "https://fred.stlouisfed.org/series/PAYEMS",
            "year": 2025,
            "unit_kind": "stock",
            "unit_dimension": "people",
        },
        {
            "series_id": "FEDFUNDS",
            "concept_slug": "us-interest-rates",
            "primitive_slug": "fred-us-fed-funds-rate-2025",
            "name": "US federal funds effective rate (FRED FEDFUNDS, 2025)",
            "description": "Federal Reserve effective federal funds rate via FRED.",
            "source_url": "https://fred.stlouisfed.org/series/FEDFUNDS",
            "year": 2025,
            "unit_kind": "intensive",
            "unit_dimension": "percent",
        },
        {
            "series_id": "M2SL",
            "concept_slug": "us-money-supply",
            "primitive_slug": "fred-us-m2-money-supply-2025",
            "name": "US M2 money supply (FRED M2SL, 2025)",
            "description": "Seasonally adjusted M2 money stock via FRED. Billions of dollars.",
            "source_url": "https://fred.stlouisfed.org/series/M2SL",
            "year": 2025,
            "unit_kind": "stock",
            "unit_dimension": "currency",
            "unit_currency": "USD",
        },
    ]

    with FREDClient(api_key=settings.fred_api_key) as client:
        for q in queries:
            series_id = q.pop("series_id")
            try:
                info_resp = client.get_series(series_id)
                obs_resp = client.get_observations(
                    series_id,
                    observation_start="2020-01-01",
                    sort_order="desc",
                    limit=100,
                )

                if not info_resp.series_list or not obs_resp.observations:
                    print(f"  SKIP {series_id}: no data")
                    continue

                series_info = info_resp.series_list[0]
                prim = observations_to_primitive_yaml(
                    series_info,
                    obs_resp.observations,
                    **q,
                )
                src = observations_to_source_yaml(
                    series_info,
                    obs_resp.observations,
                    source_url=q["source_url"],
                    year=q["year"],
                )

                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                results.append(f"  FRED {series_id} → {prim['slug']} (value={prim['value']})")
            except Exception as e:
                results.append(f"  FRED {series_id} FAILED: {e}")

    return results


def populate_census() -> list[str]:
    """Census CBP: software industry establishment/employee counts."""
    from strata.connectors.census import (
        CensusClient,
        CensusNAICS,
        industry_to_primitive_yaml,
        industry_to_source_yaml,
    )
    from strata.config import settings

    results: list[str] = []
    naics_queries = [
        (CensusNAICS.SOFTWARE_PUBLISHERS, "software-publishers"),
        (CensusNAICS.DATA_PROCESSING, "data-processing-hosting"),
        (CensusNAICS.COMPUTER_SYSTEMS_DESIGN, "computer-systems-design"),
        (CensusNAICS.MANAGEMENT_CONSULTING, "management-consulting"),
        (CensusNAICS.INSURANCE_AGENCIES, "insurance-agencies"),
    ]

    with CensusClient(api_key=settings.census_api_key) as client:
        for naics_code, label in naics_queries:
            try:
                resp = client.get_cbp(2022, naics=naics_code)
                if not resp.records:
                    results.append(f"  Census CBP {naics_code}: no records")
                    continue

                rec = resp.records[0]

                for field, dim in [("establishments", "organizations"), ("employees", "people")]:
                    slug = f"census-cbp-{naics_code}-{field}-2022"
                    prim = industry_to_primitive_yaml(
                        rec,
                        concept_slug=f"us-{label}",
                        primitive_slug=slug,
                        name=f"US {rec.naics_label} {field} (Census CBP 2022)",
                        description=f"Census County Business Patterns {field} count for NAICS {naics_code}.",
                        source_url=f"https://api.census.gov/data/2022/cbp",
                        value_field=field,
                        unit_dimension=dim,
                    )
                    src = industry_to_source_yaml(
                        rec,
                        source_url=f"https://api.census.gov/data/2022/cbp",
                    )

                    _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                    _write_yaml(SOURCES_DIR, src["slug"], src)

                    value = rec.establishments if field == "establishments" else rec.employees
                    results.append(f"  Census {naics_code}/{field} → {slug} (value={value:,})")

            except Exception as e:
                results.append(f"  Census {naics_code} FAILED: {e}")

    return results


def populate_edgar() -> list[str]:
    """EDGAR: revenue data for top tech companies + cross-company frames."""
    from strata.connectors.edgar import (
        EDGARClient,
        concept_to_primitive_yaml,
        concept_to_source_yaml,
        frame_to_primitive_yaml,
    )

    results: list[str] = []
    companies: list[tuple[str, str, str]] = [
        ("AAPL", "apple", "Revenues"),
        ("MSFT", "microsoft", "Revenues"),
        ("GOOGL", "alphabet", "Revenues"),
        ("AMZN", "amazon", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("META", "meta-platforms", "Revenues"),
    ]

    with EDGARClient() as client:
        for ticker, label, concept_tag in companies:
            try:
                cik = client.resolve_ticker(ticker)
                if cik is None:
                    results.append(f"  EDGAR {ticker}: CIK not found")
                    continue

                resp = client.get_company_concept(cik, "us-gaap", concept_tag)
                if resp.concept is None:
                    results.append(f"  EDGAR {ticker}: no Revenue concept")
                    continue

                prim = concept_to_primitive_yaml(
                    resp.concept,
                    concept_slug=f"{label}-financials",
                    primitive_slug=f"edgar-{ticker.lower()}-revenue-2023",
                    name=f"{resp.concept.entity_name} annual revenue (EDGAR 10-K, CY2023)",
                    description=f"SEC EDGAR XBRL Revenues for {resp.concept.entity_name}, annual 10-K filing.",
                    source_url=f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept_tag}.json",
                    year=2023,
                )
                src = concept_to_source_yaml(
                    resp.concept,
                    source_url=f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept_tag}.json",
                    year=2023,
                )

                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                results.append(
                    f"  EDGAR {ticker} → {prim['slug']} (value=${prim['value'] / 1e9:,.1f}B)"
                )

            except Exception as e:
                results.append(f"  EDGAR {ticker} FAILED: {e}")

        # Cross-company frame: total US public company revenue
        try:
            frame_resp = client.get_frames("us-gaap", "Revenues", "USD", "CY2023")
            if frame_resp.frame_entries:
                prim = frame_to_primitive_yaml(
                    frame_resp.frame_entries,
                    concept_slug="us-public-company-revenue",
                    primitive_slug="edgar-frame-us-revenues-2023",
                    name="Total US public company revenue (EDGAR XBRL frames, CY2023)",
                    description="Sum of all us-gaap Revenues reported in USD for CY2023 from SEC EDGAR XBRL frames.",
                    source_url="https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2023.json",
                    aggregation="sum",
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                results.append(
                    f"  EDGAR frames → {prim['slug']} "
                    f"(value=${prim['value'] / 1e12:,.1f}T, {len(frame_resp.frame_entries)} companies)"
                )

                # Also count of companies
                count_prim = frame_to_primitive_yaml(
                    frame_resp.frame_entries,
                    concept_slug="us-public-companies",
                    primitive_slug="edgar-frame-reporting-companies-2023",
                    name="US public companies reporting revenue (EDGAR XBRL, CY2023)",
                    description="Count of entities reporting us-gaap Revenues in USD for CY2023.",
                    source_url="https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2023.json",
                    aggregation="count",
                    unit_kind="stock",
                    unit_dimension="organizations",
                    unit_denominator=None,
                    unit_currency=None,
                )
                _write_yaml(PRIMITIVES_DIR, count_prim["slug"], count_prim)
                results.append(
                    f"  EDGAR frames → {count_prim['slug']} (count={int(count_prim['value'])})"
                )

        except Exception as e:
            results.append(f"  EDGAR frames FAILED: {e}")

    return results


def populate_worldbank() -> list[str]:
    """World Bank: GDP, population, labor force, internet penetration."""
    from strata.connectors.worldbank import (
        WorldBankClient,
        WBIndicatorGroup,
        indicator_to_primitive_yaml,
        indicator_to_source_yaml,
    )

    results: list[str] = []
    queries = [
        {
            "indicator": WBIndicatorGroup.GDP,
            "concept_slug": "global-gdp",
            "primitive_slug": "wb-us-gdp-2023",
            "name": "US GDP (World Bank, 2023)",
            "description": "Gross Domestic Product in current US$ from World Bank Open Data.",
            "year": 2023,
            "unit_kind": "flow",
            "unit_dimension": "currency",
            "unit_currency": "USD",
            "unit_denominator": "per-year",
        },
        {
            "indicator": WBIndicatorGroup.POPULATION,
            "concept_slug": "us-demographics",
            "primitive_slug": "wb-us-population-2023",
            "name": "US total population (World Bank, 2023)",
            "description": "Total population estimate from World Bank Open Data.",
            "year": 2023,
            "unit_kind": "stock",
            "unit_dimension": "people",
            "unit_currency": None,
        },
        {
            "indicator": WBIndicatorGroup.LABOR_FORCE,
            "concept_slug": "us-labor-market",
            "primitive_slug": "wb-us-labor-force-2023",
            "name": "US total labor force (World Bank, 2023)",
            "description": "Total labor force from World Bank / ILO modeled estimates.",
            "year": 2023,
            "unit_kind": "stock",
            "unit_dimension": "people",
            "unit_currency": None,
        },
        {
            "indicator": WBIndicatorGroup.INTERNET_USERS_PCT,
            "concept_slug": "us-digital-adoption",
            "primitive_slug": "wb-us-internet-users-pct-2023",
            "name": "US internet users (% of population) (World Bank, 2023)",
            "description": "Percentage of individuals using the internet, from ITU via World Bank.",
            "year": 2023,
            "unit_kind": "intensive",
            "unit_dimension": "percent",
            "unit_currency": None,
        },
        {
            "indicator": WBIndicatorGroup.GDP_PER_CAPITA,
            "concept_slug": "global-gdp",
            "primitive_slug": "wb-us-gdp-per-capita-2023",
            "name": "US GDP per capita (World Bank, 2023)",
            "description": "GDP per capita in current US$ from World Bank Open Data.",
            "year": 2023,
            "unit_kind": "intensive",
            "unit_dimension": "currency",
            "unit_currency": "USD",
            "unit_denominator": "per-person",
        },
    ]

    with WorldBankClient() as client:
        for q in queries:
            indicator = q.pop("indicator")
            year = q["year"]
            try:
                resp = client.get_indicator(
                    str(indicator), country="US", date_range=f"{year - 2}:{year}"
                )
                if not resp.values:
                    results.append(f"  WB {indicator}: no data")
                    continue

                prim = indicator_to_primitive_yaml(
                    resp.values,
                    source_url=f"https://data.worldbank.org/indicator/{indicator}",
                    **q,
                )
                src = indicator_to_source_yaml(
                    resp.values,
                    source_url=f"https://data.worldbank.org/indicator/{indicator}",
                    year=year,
                )

                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)

                val = prim["value"]
                if val and val > 1e9:
                    val_str = f"${val / 1e9:,.1f}B"
                elif val and val > 1e6:
                    val_str = f"{val / 1e6:,.1f}M"
                else:
                    val_str = f"{val}"
                results.append(f"  WB {indicator} → {prim['slug']} (value={val_str})")

            except Exception as e:
                results.append(f"  WB {indicator} FAILED: {e}")

    return results


def populate_bls() -> list[str]:
    """BLS: additional employment data beyond what's already seeded."""
    from strata.connectors.bls import BLSClient, series_to_primitive_yaml, series_to_source_yaml
    from strata.config import settings

    results: list[str] = []
    queries = [
        {
            "series_ids": ["JTS000000000000000JOL"],
            "concept_slug": "us-labor-market",
            "primitive_slug": "bls-jolts-openings-2024",
            "name": "Job openings total nonfarm (BLS JOLTS, 2024)",
            "description": "JOLTS total nonfarm job openings, seasonally adjusted, in thousands.",
            "source_url": "https://www.bls.gov/jlt/",
            "year": 2024,
            "unit_kind": "stock",
            "unit_dimension": "people",
        },
    ]

    with BLSClient(api_key=settings.bls_api_key) as client:
        for q in queries:
            series_ids = q.pop("series_ids")
            try:
                resp = client.get_multiple_series(series_ids, 2022, 2025)
                if not resp.series:
                    results.append(f"  BLS {series_ids[0]}: no data")
                    continue

                series = resp.series[0]
                prim = series_to_primitive_yaml(
                    series,
                    **q,
                )
                src = series_to_source_yaml(
                    series,
                    source_url=q["source_url"],
                    year=q["year"],
                )

                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                results.append(f"  BLS {series_ids[0]} → {prim['slug']} (value={prim['value']})")

            except Exception as e:
                results.append(f"  BLS {series_ids[0]} FAILED: {e}")

    return results


def main() -> None:
    print("=" * 60)
    print("Strata Data Bank Population")
    print("=" * 60)

    all_results: list[str] = []

    for name, func in [
        ("FRED", populate_fred),
        ("Census CBP", populate_census),
        ("EDGAR", populate_edgar),
        ("World Bank", populate_worldbank),
        ("BLS", populate_bls),
    ]:
        print(f"\n--- {name} ---")
        try:
            results = func()
            for r in results:
                print(r)
            all_results.extend(results)
        except Exception as e:
            msg = f"  {name} CONNECTOR FAILED: {e}"
            print(msg)
            all_results.append(msg)

    print("\n" + "=" * 60)
    successes = [r for r in all_results if "FAILED" not in r and "SKIP" not in r]
    failures = [r for r in all_results if "FAILED" in r]
    skips = [r for r in all_results if "SKIP" in r]
    print(f"Done: {len(successes)} succeeded, {len(failures)} failed, {len(skips)} skipped")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f)
        sys.exit(1)


if __name__ == "__main__":
    main()
