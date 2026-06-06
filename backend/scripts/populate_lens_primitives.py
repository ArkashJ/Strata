#!/usr/bin/env python3
"""Populate the Strata data bank with 100+ lens-aligned primitives.

Queries BLS, FRED, Census, EDGAR, and World Bank APIs targeting
all six TAM analysis lenses. Writes YAML to data/primitives/ and
data/sources/.

Usage:
    cd backend && uv run python scripts/populate_lens_primitives.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PRIMITIVES_DIR = ROOT / "data" / "primitives"
SOURCES_DIR = ROOT / "data" / "sources"

RESULTS: list[str] = []
FAILURES: list[str] = []


def _write_yaml(directory: Path, slug: str, data: dict) -> Path:
    path = directory / f"{slug}.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
    return path


def _log(msg: str, fail: bool = False) -> None:
    print(msg)
    if fail:
        FAILURES.append(msg)
    else:
        RESULTS.append(msg)


# ═══════════════════════════════════════════════════════════════════
# FRED queries — macro indicators + industry series
# ═══════════════════════════════════════════════════════════════════


def populate_fred_macro() -> None:
    """FRED: GDP, employment, interest, money supply, consumption, investment."""
    from strata.connectors.fred import (
        FREDClient,
        observations_to_primitive_yaml,
        observations_to_source_yaml,
    )
    from strata.config import settings

    queries = [
        # L2: revenue_generation — macro spending signals
        (
            "GDPC1",
            "us-macroeconomy",
            "fred-real-gdp-2024",
            "US real GDP (FRED GDPC1, 2024)",
            "Bureau of Economic Analysis real GDP in chained 2017 dollars via FRED.",
            "https://fred.stlouisfed.org/series/GDPC1",
            2024,
            "flow",
            "currency",
            "USD",
            "per-year",
            "L2",
        ),
        (
            "PCE",
            "us-consumer-spending",
            "fred-personal-consumption-2024",
            "US personal consumption expenditures (FRED PCE, 2024)",
            "BEA personal consumption expenditures via FRED, billions of dollars.",
            "https://fred.stlouisfed.org/series/PCE",
            2024,
            "flow",
            "currency",
            "USD",
            "per-year",
            "L2",
        ),
        (
            "PCEPI",
            "us-consumer-spending",
            "fred-pce-price-index-2025",
            "US PCE price index (FRED PCEPI, 2025)",
            "BEA PCE price index, Fed's preferred inflation measure.",
            "https://fred.stlouisfed.org/series/PCEPI",
            2025,
            "intensive",
            "percent",
            None,
            None,
            "L2",
        ),
        (
            "TOTALSA",
            "us-consumer-spending",
            "fred-total-vehicle-sales-2025",
            "US total vehicle sales (FRED TOTALSA, 2025)",
            "Total light vehicle sales, millions of units annualized.",
            "https://fred.stlouisfed.org/series/TOTALSA",
            2025,
            "flow",
            "transactions",
            None,
            "per-year",
            "L4",
        ),
        (
            "RSAFS",
            "us-consumer-spending",
            "fred-retail-sales-2025",
            "US advance retail sales (FRED RSAFS, 2025)",
            "Advance monthly retail and food services sales, millions of dollars.",
            "https://fred.stlouisfed.org/series/RSAFS",
            2025,
            "flow",
            "currency",
            "USD",
            "per-month",
            "L2",
        ),
        # L1: cost_efficiency — labor market signals
        (
            "AHETPI",
            "us-labor-market",
            "fred-avg-hourly-earnings-private-2025",
            "US average hourly earnings, private sector (FRED AHETPI, 2025)",
            "Average hourly earnings of production and nonsupervisory employees.",
            "https://fred.stlouisfed.org/series/AHETPI",
            2025,
            "intensive",
            "currency",
            "USD",
            "per-hour",
            "L1",
        ),
        (
            "CES6500000001",
            "us-tech-employment",
            "fred-info-sector-employment-2025",
            "US information sector employment (FRED CES6500000001, 2025)",
            "Total employees in the information sector (NAICS 51), thousands.",
            "https://fred.stlouisfed.org/series/CES6500000001",
            2025,
            "stock",
            "people",
            None,
            None,
            "L1",
        ),
        (
            "CES6054000001",
            "us-tech-employment",
            "fred-professional-tech-services-employment-2025",
            "US professional/tech services employment (FRED CES6054000001, 2025)",
            "Total employees in professional and technical services (NAICS 54), thousands.",
            "https://fred.stlouisfed.org/series/CES6054000001",
            2025,
            "stock",
            "people",
            None,
            None,
            "L1",
        ),
        # L3: latent_demand — population + adoption
        (
            "POPTHM",
            "us-demographics",
            "fred-us-population-monthly-2025",
            "US total population, monthly (FRED POPTHM, 2025)",
            "Resident population estimate, thousands.",
            "https://fred.stlouisfed.org/series/POPTHM",
            2025,
            "stock",
            "people",
            None,
            None,
            "L3",
        ),
        (
            "LNS12000060",
            "us-demographics",
            "fred-employed-25-54-2025",
            "US employed persons age 25-54 (FRED LNS12000060, 2025)",
            "Prime-age employed persons, thousands — core productive workforce.",
            "https://fred.stlouisfed.org/series/LNS12000060",
            2025,
            "stock",
            "people",
            None,
            None,
            "L3",
        ),
        # L4: platform_throughput — financial flows
        (
            "BOGZ1FL073164003Q",
            "us-financial-flows",
            "fred-total-checkable-deposits-2024",
            "US total checkable deposits (FRED BOGZ1FL073164003Q, 2024)",
            "Total checkable deposits and currency at commercial banks, billions.",
            "https://fred.stlouisfed.org/series/BOGZ1FL073164003Q",
            2024,
            "stock",
            "currency",
            "USD",
            None,
            "L4",
        ),
        # L5: bundle_consolidation — IT spending signals
        (
            "GFDEBTN",
            "us-macroeconomy",
            "fred-federal-debt-total-2024",
            "US federal debt total public (FRED GFDEBTN, 2024)",
            "Federal debt total public debt, millions of dollars.",
            "https://fred.stlouisfed.org/series/GFDEBTN",
            2024,
            "stock",
            "currency",
            "USD",
            None,
            "cross",
        ),
        (
            "INDPRO",
            "us-industrial-production",
            "fred-industrial-production-2025",
            "US industrial production index (FRED INDPRO, 2025)",
            "Industrial production index (2017=100).",
            "https://fred.stlouisfed.org/series/INDPRO",
            2025,
            "intensive",
            "events",
            None,
            None,
            "cross",
        ),
        (
            "UNRATE",
            "us-labor-market",
            "fred-unemployment-rate-2025",
            "US unemployment rate (FRED UNRATE, 2025)",
            "Civilian unemployment rate, seasonally adjusted.",
            "https://fred.stlouisfed.org/series/UNRATE",
            2025,
            "intensive",
            "percent",
            None,
            None,
            "cross",
        ),
        (
            "DGS10",
            "us-interest-rates",
            "fred-10yr-treasury-yield-2025",
            "US 10-year treasury yield (FRED DGS10, 2025)",
            "Market yield on 10-year Treasury securities.",
            "https://fred.stlouisfed.org/series/DGS10",
            2025,
            "intensive",
            "percent",
            None,
            None,
            "cross",
        ),
        (
            "JTSJOL",
            "us-labor-market",
            "fred-job-openings-total-2025",
            "US total job openings (FRED JTSJOL, 2025)",
            "JOLTS total nonfarm job openings, seasonally adjusted, thousands.",
            "https://fred.stlouisfed.org/series/JTSJOL",
            2025,
            "stock",
            "people",
            None,
            None,
            "L1",
        ),
        (
            "A939RC0Q052SBEA",
            "us-consumer-spending",
            "fred-real-pce-per-capita-2024",
            "US real PCE per capita (FRED A939RC0Q052SBEA, 2024)",
            "Real personal consumption expenditures per capita, chained 2017 dollars.",
            "https://fred.stlouisfed.org/series/A939RC0Q052SBEA",
            2024,
            "flow",
            "currency",
            "USD",
            "per-person-per-year",
            "L3",
        ),
        (
            "DGORDER",
            "us-industrial-production",
            "fred-durable-goods-orders-2025",
            "US durable goods new orders (FRED DGORDER, 2025)",
            "Manufacturers' new orders for durable goods, millions of dollars.",
            "https://fred.stlouisfed.org/series/DGORDER",
            2025,
            "flow",
            "currency",
            "USD",
            "per-month",
            "L2",
        ),
        (
            "PERMIT",
            "us-construction",
            "fred-building-permits-2025",
            "US new privately-owned housing units authorized (FRED PERMIT, 2025)",
            "New building permits, thousands of units.",
            "https://fred.stlouisfed.org/series/PERMIT",
            2025,
            "flow",
            "events",
            None,
            "per-month",
            "L3",
        ),
        (
            "PSAVERT",
            "us-consumer-spending",
            "fred-personal-savings-rate-2025",
            "US personal savings rate (FRED PSAVERT, 2025)",
            "Personal savings as percentage of disposable income.",
            "https://fred.stlouisfed.org/series/PSAVERT",
            2025,
            "intensive",
            "percent",
            None,
            None,
            "L3",
        ),
    ]

    with FREDClient(api_key=settings.fred_api_key) as client:
        for sid, concept, slug, name, desc, url, year, uk, ud, uc, udn, lens in queries:
            try:
                info_resp = client.get_series(sid)
                obs_resp = client.get_observations(
                    sid, observation_start="2020-01-01", sort_order="desc", limit=100
                )
                if not info_resp.series_list or not obs_resp.observations:
                    _log(f"  FRED {sid}: no data", fail=True)
                    continue

                kwargs: dict = dict(
                    concept_slug=concept,
                    primitive_slug=slug,
                    name=name,
                    description=desc,
                    source_url=url,
                    year=year,
                    unit_kind=uk,
                    unit_dimension=ud,
                )
                if uc:
                    kwargs["unit_currency"] = uc
                if udn:
                    kwargs["unit_denominator"] = udn

                prim = observations_to_primitive_yaml(
                    info_resp.series_list[0], obs_resp.observations, **kwargs
                )
                src = observations_to_source_yaml(
                    info_resp.series_list[0], obs_resp.observations, source_url=url, year=year
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                _log(f"  [{lens}] FRED {sid} → {slug} = {prim['value']}")
            except Exception as e:
                _log(f"  FRED {sid} FAILED: {e}", fail=True)


# ═══════════════════════════════════════════════════════════════════
# Census CBP — industry establishment + employee counts
# ═══════════════════════════════════════════════════════════════════


def populate_census_industries() -> None:
    """Census: 15 NAICS industries × establishments + employees = 30 primitives."""
    from strata.connectors.census import (
        CensusClient,
        industry_to_primitive_yaml,
        industry_to_source_yaml,
    )
    from strata.config import settings

    industries = [
        # L1 cost_efficiency persona pools
        ("5112", "software-publishers", "L1"),
        ("5415", "computer-systems-design", "L1"),
        ("5416", "management-consulting", "L1"),
        ("5182", "data-processing-hosting", "L1"),
        ("5417", "scientific-rd-services", "L6"),
        # L2 revenue_generation segments
        ("5242", "insurance-agencies", "L2"),
        ("5221", "depository-credit-intermediation", "L4"),
        ("5222", "nondepository-credit-intermediation", "L4"),
        ("5239", "other-financial-investment", "L4"),
        # L3 latent_demand adoption signals
        ("4541", "electronic-shopping", "L3"),
        ("5191", "internet-publishing-web-search", "L3"),
        # L5 bundle_consolidation
        ("5411", "legal-services", "L5"),
        ("5412", "accounting-tax-preparation", "L5"),
        ("5413", "architectural-engineering", "L5"),
        ("5611", "office-administrative-services", "L5"),
    ]

    with CensusClient(api_key=settings.census_api_key) as client:
        for naics, label, lens in industries:
            try:
                resp = client.get_cbp(2022, naics=naics)
                if not resp.records:
                    _log(f"  Census {naics} ({label}): no records", fail=True)
                    continue
                rec = resp.records[0]

                for field, dim in [("establishments", "organizations"), ("employees", "people")]:
                    slug = f"census-cbp-{naics}-{field}-2022"
                    prim = industry_to_primitive_yaml(
                        rec,
                        concept_slug=f"us-{label}",
                        primitive_slug=slug,
                        name=f"US {rec.naics_label} {field} (Census CBP 2022)",
                        description=f"Census County Business Patterns {field} for NAICS {naics}.",
                        source_url="https://api.census.gov/data/2022/cbp",
                        value_field=field,
                        unit_dimension=dim,
                    )
                    src = industry_to_source_yaml(
                        rec, source_url="https://api.census.gov/data/2022/cbp"
                    )
                    _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                    _write_yaml(SOURCES_DIR, src["slug"], src)
                    val = rec.establishments if field == "establishments" else rec.employees
                    _log(f"  [{lens}] Census {naics}/{field} → {slug} = {val:,}")
            except Exception as e:
                _log(f"  Census {naics} FAILED: {e}", fail=True)


# ═══════════════════════════════════════════════════════════════════
# EDGAR — company revenue + R&D + financial metrics
# ═══════════════════════════════════════════════════════════════════


def populate_edgar_companies() -> None:
    """EDGAR: revenue + R&D for 15 companies + 3 cross-company frames."""
    from strata.connectors.edgar import (
        EDGARClient,
        concept_to_primitive_yaml,
        concept_to_source_yaml,
        frame_to_primitive_yaml,
    )

    # (ticker, label, concept_tag, concept_slug, lens)
    companies: list[tuple[str, str, str, str, str]] = [
        # L2: revenue_generation — segment revenue
        ("AAPL", "apple", "Revenues", "big-tech-financials", "L2"),
        ("MSFT", "microsoft", "Revenues", "big-tech-financials", "L2"),
        ("GOOGL", "alphabet", "Revenues", "big-tech-financials", "L2"),
        (
            "AMZN",
            "amazon",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "big-tech-financials",
            "L2",
        ),
        ("META", "meta-platforms", "Revenues", "big-tech-financials", "L2"),
        # L4: platform_throughput — payment companies
        ("V", "visa", "Revenues", "payments-platform", "L4"),
        ("MA", "mastercard", "Revenues", "payments-platform", "L4"),
        ("PYPL", "paypal", "Revenues", "payments-platform", "L4"),
        ("SQ", "block-sq", "Revenues", "payments-platform", "L4"),
        # L5: bundle_consolidation — SaaS platforms
        ("CRM", "salesforce", "Revenues", "saas-consolidation", "L5"),
        ("NOW", "servicenow", "Revenues", "saas-consolidation", "L5"),
        ("WDAY", "workday", "Revenues", "saas-consolidation", "L5"),
        # L6: productivity_uplift — AI/dev tools
        ("ADBE", "adobe", "Revenues", "productivity-tools", "L6"),
        ("PLTR", "palantir", "Revenues", "ai-analytics", "L6"),
        ("SNOW", "snowflake", "Revenues", "data-infrastructure", "L6"),
    ]

    with EDGARClient() as client:
        tickers_resp = client.get_company_tickers()
        ticker_map: dict[str, str] = {}
        for cik_int, tick, _name in tickers_resp.tickers:
            ticker_map[tick.upper()] = str(cik_int).zfill(10)

        for ticker, label, concept_tag, concept_slug, lens in companies:
            try:
                cik = ticker_map.get(ticker.upper())
                if cik is None:
                    _log(f"  EDGAR {ticker}: CIK not found", fail=True)
                    continue

                resp = client.get_company_concept(cik, "us-gaap", concept_tag)
                if resp.concept is None:
                    _log(f"  EDGAR {ticker}: no {concept_tag} concept", fail=True)
                    continue

                slug = f"edgar-{ticker.lower()}-revenue-2023"
                prim = concept_to_primitive_yaml(
                    resp.concept,
                    concept_slug=concept_slug,
                    primitive_slug=slug,
                    name=f"{resp.concept.entity_name} revenue (EDGAR 10-K, CY2023)",
                    description=f"SEC EDGAR XBRL {concept_tag} for {resp.concept.entity_name}.",
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
                _log(f"  [{lens}] EDGAR {ticker} → {slug} = ${prim['value'] / 1e9:,.1f}B")
            except Exception as e:
                _log(f"  EDGAR {ticker} FAILED: {e}", fail=True)

        # Cross-company frames
        frames = [
            (
                "Revenues",
                "USD",
                "CY2023",
                "edgar-frame-us-revenues-2023",
                "us-public-company-revenue",
                "Total US public company revenue",
                "sum",
                "L2",
            ),
            (
                "Revenues",
                "USD",
                "CY2023",
                "edgar-frame-reporting-companies-2023",
                "us-public-companies",
                "US companies reporting revenue",
                "count",
                "cross",
            ),
            (
                "ResearchAndDevelopmentExpense",
                "USD",
                "CY2023",
                "edgar-frame-us-rd-spend-2023",
                "us-rd-investment",
                "Total US public company R&D spending",
                "sum",
                "L6",
            ),
        ]

        for concept_tag, unit, period, slug, cs, name, agg, lens in frames:
            try:
                resp = client.get_frames("us-gaap", concept_tag, unit, period)
                if not resp.frame_entries:
                    _log(f"  EDGAR frame {concept_tag}/{period}: no entries", fail=True)
                    continue

                uk = "stock" if agg == "count" else "flow"
                ud = "organizations" if agg == "count" else "currency"
                prim = frame_to_primitive_yaml(
                    resp.frame_entries,
                    concept_slug=cs,
                    primitive_slug=slug,
                    name=f"{name} (EDGAR XBRL frames, {period})",
                    description=f"Aggregated {concept_tag} from SEC EDGAR XBRL frames for {period}.",
                    source_url=f"https://data.sec.gov/api/xbrl/frames/us-gaap/{concept_tag}/{unit}/{period}.json",
                    aggregation=agg,
                    unit_kind=uk,
                    unit_dimension=ud,
                    unit_denominator="per-year" if agg != "count" else None,
                    unit_currency="USD" if agg != "count" else None,
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                val = prim["value"]
                if agg == "count":
                    _log(f"  [{lens}] EDGAR frame {concept_tag} → {slug} = {int(val)} companies")
                else:
                    _log(f"  [{lens}] EDGAR frame {concept_tag} → {slug} = ${val / 1e12:,.1f}T")
            except Exception as e:
                _log(f"  EDGAR frame {concept_tag} FAILED: {e}", fail=True)


# ═══════════════════════════════════════════════════════════════════
# World Bank — global macro + adoption signals
# ═══════════════════════════════════════════════════════════════════


def populate_worldbank_global() -> None:
    """World Bank: US + global indicators across all lenses."""
    from strata.connectors.worldbank import (
        WorldBankClient,
        indicator_to_primitive_yaml,
        indicator_to_source_yaml,
    )

    # (indicator, country, concept_slug, slug, name, year, uk, ud, uc, udn, lens)
    queries = [
        # L3: latent_demand — population + adoption
        (
            "SP.POP.TOTL",
            "US",
            "us-demographics",
            "wb-us-population-2023",
            "US total population (World Bank, 2023)",
            2023,
            "stock",
            "people",
            None,
            None,
            "L3",
        ),
        (
            "SL.TLF.TOTL.IN",
            "US",
            "us-labor-market",
            "wb-us-labor-force-2023",
            "US total labor force (World Bank, 2023)",
            2023,
            "stock",
            "people",
            None,
            None,
            "L1",
        ),
        (
            "IT.NET.USER.ZS",
            "US",
            "us-digital-adoption",
            "wb-us-internet-users-pct-2023",
            "US internet users % (World Bank, 2023)",
            2023,
            "intensive",
            "percent",
            None,
            None,
            "L3",
        ),
        (
            "IT.CEL.SETS.P2",
            "US",
            "us-digital-adoption",
            "wb-us-mobile-subscriptions-2022",
            "US mobile cellular subscriptions per 100 people (World Bank, 2022)",
            2022,
            "intensive",
            "percent",
            None,
            None,
            "L3",
        ),
        (
            "SP.POP.TOTL",
            "WLD",
            "global-demographics",
            "wb-world-population-2023",
            "World total population (World Bank, 2023)",
            2023,
            "stock",
            "people",
            None,
            None,
            "L3",
        ),
        (
            "NY.GDP.MKTP.CD",
            "WLD",
            "global-gdp",
            "wb-world-gdp-2023",
            "World GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "IT.NET.USER.ZS",
            "WLD",
            "global-digital-adoption",
            "wb-world-internet-users-pct-2022",
            "World internet users % (World Bank, 2022)",
            2022,
            "intensive",
            "percent",
            None,
            None,
            "L3",
        ),
        # L2: revenue_generation — economic signals
        (
            "NY.GDP.MKTP.CD",
            "US",
            "us-macroeconomy",
            "wb-us-gdp-2023",
            "US GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "L2",
        ),
        (
            "NY.GDP.PCAP.CD",
            "US",
            "us-macroeconomy",
            "wb-us-gdp-per-capita-2023",
            "US GDP per capita (World Bank, 2023)",
            2023,
            "intensive",
            "currency",
            "USD",
            "per-person",
            "L2",
        ),
        (
            "NE.CON.PRVT.CD",
            "US",
            "us-consumer-spending",
            "wb-us-household-consumption-2023",
            "US household final consumption (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "L2",
        ),
        # L4: platform_throughput — trade + FDI
        (
            "BX.KLT.DINV.CD.WD",
            "US",
            "us-financial-flows",
            "wb-us-fdi-inflows-2023",
            "US FDI net inflows (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "L4",
        ),
        (
            "TG.VAL.TOTL.GD.ZS",
            "US",
            "us-trade",
            "wb-us-trade-pct-gdp-2023",
            "US merchandise trade % of GDP (World Bank, 2023)",
            2023,
            "intensive",
            "percent",
            None,
            None,
            "L4",
        ),
        # L1: cost_efficiency — labor costs
        (
            "SL.UEM.TOTL.ZS",
            "US",
            "us-labor-market",
            "wb-us-unemployment-rate-2023",
            "US unemployment rate ILO estimate (World Bank, 2023)",
            2023,
            "intensive",
            "percent",
            None,
            None,
            "L1",
        ),
        # Global market comparisons
        (
            "NY.GDP.MKTP.CD",
            "CN",
            "china-macroeconomy",
            "wb-china-gdp-2023",
            "China GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "NY.GDP.MKTP.CD",
            "GB",
            "uk-macroeconomy",
            "wb-uk-gdp-2023",
            "United Kingdom GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "NY.GDP.MKTP.CD",
            "DE",
            "germany-macroeconomy",
            "wb-germany-gdp-2023",
            "Germany GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "NY.GDP.MKTP.CD",
            "JP",
            "japan-macroeconomy",
            "wb-japan-gdp-2023",
            "Japan GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "NY.GDP.MKTP.CD",
            "IN",
            "india-macroeconomy",
            "wb-india-gdp-2023",
            "India GDP (World Bank, 2023)",
            2023,
            "flow",
            "currency",
            "USD",
            "per-year",
            "cross",
        ),
        (
            "FP.CPI.TOTL.ZG",
            "US",
            "us-inflation",
            "wb-us-inflation-rate-2023",
            "US inflation rate CPI (World Bank, 2023)",
            2023,
            "intensive",
            "percent",
            None,
            None,
            "cross",
        ),
        (
            "SL.TLF.TOTL.IN",
            "WLD",
            "global-labor-market",
            "wb-world-labor-force-2023",
            "World total labor force (World Bank, 2023)",
            2023,
            "stock",
            "people",
            None,
            None,
            "cross",
        ),
    ]

    with WorldBankClient() as client:
        for indicator, country, concept, slug, name, year, uk, ud, uc, udn, lens in queries:
            try:
                geo_codes = (country,) if country != "WLD" else ("GLOBAL",)
                geo_level = "country" if country != "WLD" else "global"
                resp = client.get_indicator(
                    indicator, country=country, date_range=f"{year - 2}:{year}"
                )
                if not resp.values:
                    _log(f"  WB {indicator}/{country}: no data", fail=True)
                    continue

                kwargs: dict = dict(
                    concept_slug=concept,
                    primitive_slug=slug,
                    name=name,
                    description=f"World Bank Open Data {indicator} for {country}.",
                    source_url=f"https://data.worldbank.org/indicator/{indicator}",
                    year=year,
                    unit_kind=uk,
                    unit_dimension=ud,
                    geo_codes=geo_codes,
                    geo_level=geo_level,
                )
                if uc:
                    kwargs["unit_currency"] = uc
                if udn:
                    kwargs["unit_denominator"] = udn

                prim = indicator_to_primitive_yaml(resp.values, **kwargs)
                src = indicator_to_source_yaml(
                    resp.values,
                    source_url=f"https://data.worldbank.org/indicator/{indicator}",
                    year=year,
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                val = prim["value"]
                if val and abs(val) > 1e9:
                    _log(f"  [{lens}] WB {indicator}/{country} → {slug} = ${val / 1e9:,.1f}B")
                elif val and abs(val) > 1e6:
                    _log(f"  [{lens}] WB {indicator}/{country} → {slug} = {val / 1e6:,.1f}M")
                else:
                    _log(f"  [{lens}] WB {indicator}/{country} → {slug} = {val}")
            except Exception as e:
                _log(f"  WB {indicator}/{country} FAILED: {e}", fail=True)


# ═══════════════════════════════════════════════════════════════════
# BLS — occupational employment + wages
# ═══════════════════════════════════════════════════════════════════


def populate_bls_occupations() -> None:
    """BLS OES: employment + wage data for key occupations."""
    from strata.connectors.bls import BLSClient, series_to_primitive_yaml, series_to_source_yaml
    from strata.config import settings

    with BLSClient(api_key=settings.bls_api_key) as client:
        # Batch 1: employment levels for key tech occupations (OES format)
        # Series format: OEUS + area + industry + occupation + datatype
        # 000000 = national, 000000 = all industries, XXXXXX = SOC code, 01 = employment
        employment_series = [
            (
                "OEUN000000000000015125200000003",
                "bls-oes-sw-devs-national-2024",
                "software-eng-productivity",
                "Software developers employment (SOC 15-1252)",
                "L1",
            ),
            (
                "OEUN000000000000015205100000003",
                "bls-oes-data-scientists-national-2024",
                "ai-analytics",
                "Data scientists employment (SOC 15-2051)",
                "L6",
            ),
            (
                "OEUN000000000000011302100000003",
                "bls-oes-computer-info-managers-national-2024",
                "saas-consolidation",
                "Computer/information systems managers (SOC 11-3021)",
                "L5",
            ),
            (
                "OEUN000000000000015124100000003",
                "bls-oes-network-architects-national-2024",
                "data-infrastructure",
                "Network architects employment (SOC 15-1241)",
                "L1",
            ),
            (
                "OEUN000000000000013116100000003",
                "bls-oes-marketing-managers-national-2024",
                "gtm-ops-tooling-na",
                "Marketing managers employment (SOC 13-1161)",
                "L1",
            ),
            (
                "OEUN000000000000013119900000003",
                "bls-oes-business-ops-specialists-national-2024",
                "workplace-suite-consolidation",
                "Business operations specialists (SOC 13-1199)",
                "L5",
            ),
        ]

        for sid, slug, concept, name, lens in employment_series:
            try:
                resp = client.get_multiple_series([sid], 2023, 2025)
                if not resp.series or not resp.series[0].data:
                    _log(f"  BLS {sid}: no data", fail=True)
                    continue
                series = resp.series[0]
                prim = series_to_primitive_yaml(
                    series,
                    concept_slug=concept,
                    primitive_slug=slug,
                    name=f"US {name}, national (BLS OES 2024)",
                    description=f"BLS OES employment estimate, national, all industries.",
                    source_url="https://www.bls.gov/oes/current/",
                    year=2024,
                )
                src = series_to_source_yaml(
                    series, source_url="https://www.bls.gov/oes/current/", year=2024
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                _log(f"  [{lens}] BLS {sid[:20]}... → {slug} = {prim['value']}")
            except Exception as e:
                _log(f"  BLS {sid[:20]}... FAILED: {e}", fail=True)

        # Batch 2: CES industry employment
        ces_series = [
            (
                "CES5051200001",
                "bls-ces-software-publishing-2025",
                "software-eng-productivity",
                "Software publishing employment (CES)",
                "L1",
            ),
            (
                "CES6056174201",
                "bls-ces-computer-systems-design-2025",
                "computer-systems-design",
                "Computer systems design employment (CES)",
                "L1",
            ),
            (
                "CES5051800001",
                "bls-ces-data-processing-2025",
                "data-infrastructure",
                "Data processing/hosting employment (CES)",
                "L1",
            ),
            (
                "CES6561000001",
                "bls-ces-healthcare-social-assistance-2025",
                "doc-gen-pc-insurance",
                "Healthcare/social assistance employment (CES)",
                "L2",
            ),
            (
                "CES5552000001",
                "bls-ces-finance-insurance-2025",
                "payments-platform",
                "Finance/insurance employment (CES)",
                "L4",
            ),
        ]

        for sid, slug, concept, name, lens in ces_series:
            try:
                resp = client.get_multiple_series([sid], 2023, 2025)
                if not resp.series or not resp.series[0].data:
                    _log(f"  BLS {sid}: no data", fail=True)
                    continue
                series = resp.series[0]
                prim = series_to_primitive_yaml(
                    series,
                    concept_slug=concept,
                    primitive_slug=slug,
                    name=f"US {name}, thousands (BLS CES 2025)",
                    description=f"BLS Current Employment Statistics, seasonally adjusted.",
                    source_url="https://www.bls.gov/ces/",
                    year=2025,
                )
                src = series_to_source_yaml(
                    series, source_url="https://www.bls.gov/ces/", year=2025
                )
                _write_yaml(PRIMITIVES_DIR, prim["slug"], prim)
                _write_yaml(SOURCES_DIR, src["slug"], src)
                _log(f"  [{lens}] BLS {sid} → {slug} = {prim['value']}")
            except Exception as e:
                _log(f"  BLS {sid} FAILED: {e}", fail=True)


def main() -> None:
    print("=" * 70)
    print("Strata Data Bank — Lens-Aligned Population (100+ queries)")
    print("=" * 70)

    for name, func in [
        ("FRED Macro + Industry", populate_fred_macro),
        ("Census CBP Industries", populate_census_industries),
        ("EDGAR Company Financials", populate_edgar_companies),
        ("World Bank Global Indicators", populate_worldbank_global),
        ("BLS Occupational Employment", populate_bls_occupations),
    ]:
        print(f"\n{'─' * 50}")
        print(f"  {name}")
        print(f"{'─' * 50}")
        try:
            func()
        except Exception as e:
            _log(f"  {name} CONNECTOR FAILED: {e}", fail=True)
            traceback.print_exc()

    print(f"\n{'=' * 70}")
    print(f"TOTAL: {len(RESULTS)} succeeded, {len(FAILURES)} failed")
    print(f"{'=' * 70}")

    if FAILURES:
        print(f"\n--- {len(FAILURES)} Failures ---")
        for f in FAILURES:
            print(f)
        sys.exit(1)


if __name__ == "__main__":
    main()
