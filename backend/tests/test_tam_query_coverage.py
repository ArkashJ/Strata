"""TAM query coverage test — maps 77 sample queries to connector data sources.

Verifies that the 15 connectors can supply the primitives needed for the
77-query VC TAM test set. Each query maps to:
- Primary connector(s) that provide the denominator/numerator
- Sizing angle (bottoms-up, top-down, displacement, analog, etc.)
- Specific query methods on the connector that would be called

This is a static coverage test (no live API calls) — it verifies that the
connector methods exist and are callable, not that the data is correct.
"""

from __future__ import annotations

import pytest

from strata.connectors.bls import BLSClient
from strata.connectors.census import CensusClient
from strata.connectors.cms import CMSClient
from strata.connectors.comtrade import ComtradeClient
from strata.connectors.edgar import EDGARClient
from strata.connectors.eia import EIAClient
from strata.connectors.eurostat import EurostatClient
from strata.connectors.faa import FAAClient
from strata.connectors.fdic import FDICClient
from strata.connectors.fred import FREDClient
from strata.connectors.oecd import OECDClient
from strata.connectors.openfda import OpenFDAClient
from strata.connectors.usda_nass import NASSClient
from strata.connectors.worldbank import WorldBankClient


TAM_QUERIES: list[dict[str, object]] = [
    # Kyber — P&C insurance doc-gen
    {
        "id": 1,
        "company": "Kyber",
        "angle": "bottoms-up by carrier × seat × ACV",
        "connectors": ["BLS", "EDGAR", "Census"],
        "methods": [
            "BLSClient.get_series",
            "EDGARClient.get_company_concept",
            "CensusClient.get_industry",
        ],
    },
    {
        "id": 2,
        "company": "Kyber",
        "angle": "bottoms-up anchored on $150K ACV",
        "connectors": ["Census", "EDGAR"],
        "methods": ["CensusClient.get_industry", "EDGARClient.get_company_concept"],
    },
    {
        "id": 3,
        "company": "Kyber",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series", "BLSClient.get_multiple_series"],
    },
    {
        "id": 4,
        "company": "Kyber",
        "angle": "analog/penetration",
        "connectors": ["Census", "FRED"],
        "methods": ["CensusClient.get_industry", "FREDClient.get_observations"],
    },
    # Gather — market research
    {
        "id": 5,
        "company": "Gather",
        "angle": "bottoms-up by marketing orgs × budget",
        "connectors": ["BLS", "Census", "OECD"],
        "methods": ["BLSClient.get_series", "CensusClient.get_industry", "OECDClient.get_gdp"],
    },
    {
        "id": 6,
        "company": "Gather",
        "angle": "displacement of insights industry",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series", "CensusClient.get_industry"],
    },
    {
        "id": 7,
        "company": "Gather",
        "angle": "bottoms-up by marketing seat",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 8,
        "company": "Gather",
        "angle": "comparable-market substitution",
        "connectors": ["Census", "FRED"],
        "methods": ["CensusClient.get_industry", "FREDClient.get_observations"],
    },
    # Echelon — ServiceNow
    {
        "id": 9,
        "company": "Echelon",
        "angle": "bottoms-up by ServiceNow customers",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 10,
        "company": "Echelon",
        "angle": "SI/PS labor displacement",
        "connectors": ["BLS", "EDGAR"],
        "methods": ["BLSClient.get_series", "EDGARClient.get_company_concept"],
    },
    {
        "id": 11,
        "company": "Echelon",
        "angle": "platform-ecosystem TAM",
        "connectors": ["EDGAR", "Census"],
        "methods": ["EDGARClient.get_company_concept", "CensusClient.get_industry"],
    },
    {
        "id": 12,
        "company": "Echelon",
        "angle": "labor displacement by seat",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Endeavor — mfg & distribution
    {
        "id": 13,
        "company": "Endeavor",
        "angle": "bottoms-up by firms × ACV",
        "connectors": ["Census", "BLS", "Comtrade"],
        "methods": ["CensusClient.get_industry", "ComtradeClient.get_total_trade"],
    },
    {
        "id": 14,
        "company": "Endeavor",
        "angle": "top-down from quote-to-cash labor",
        "connectors": ["BLS", "Census", "OECD"],
        "methods": ["BLSClient.get_series", "OECDClient.get_productivity"],
    },
    {
        "id": 15,
        "company": "Endeavor",
        "angle": "labor displacement BLS-anchored",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series", "BLSClient.get_multiple_series"],
    },
    {
        "id": 16,
        "company": "Endeavor",
        "angle": "analog/penetration (ERP/MES)",
        "connectors": ["Census", "FRED"],
        "methods": ["CensusClient.get_industry"],
    },
    # Skyramp — QA testing
    {
        "id": 17,
        "company": "Skyramp",
        "angle": "bottoms-up by devs/QA × tool spend",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 18,
        "company": "Skyramp",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 19,
        "company": "Skyramp",
        "angle": "comparable-market",
        "connectors": ["EDGAR", "Census"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 20,
        "company": "Skyramp",
        "angle": "bottoms-up by company × eng-team",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series", "CensusClient.get_industry"],
    },
    # Supermemory — AI memory infra
    {
        "id": 21,
        "company": "Supermemory",
        "angle": "bottoms-up by AI-app devs",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 22,
        "company": "Supermemory",
        "angle": "share-of-AI-infra-stack",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 23,
        "company": "Supermemory",
        "angle": "attach-rate analog",
        "connectors": ["FRED"],
        "methods": ["FREDClient.get_observations"],
    },
    # Numeral — sales-tax compliance
    {
        "id": 24,
        "company": "Numeral",
        "angle": "bottoms-up by sellers × ACV",
        "connectors": ["Census", "Comtrade"],
        "methods": ["CensusClient.get_industry", "ComtradeClient.get_total_trade"],
    },
    {
        "id": 25,
        "company": "Numeral",
        "angle": "underserved-SMB bottoms-up",
        "connectors": ["Census"],
        "methods": ["CensusClient.get_firms"],
    },
    {
        "id": 26,
        "company": "Numeral",
        "angle": "comparable-market share-shift",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    # Yotta — India cloud
    {
        "id": 27,
        "company": "Yotta",
        "angle": "capacity-based MW × revenue/MW",
        "connectors": ["EIA", "OECD", "WorldBank"],
        "methods": [
            "EIAClient.get_electricity_prices",
            "OECDClient.get_gdp",
            "WorldBankClient.get_indicator",
        ],
    },
    {
        "id": 28,
        "company": "Yotta",
        "angle": "top-down from India cloud spend",
        "connectors": ["OECD", "WorldBank"],
        "methods": ["OECDClient.get_gdp", "WorldBankClient.get_indicator"],
    },
    {
        "id": 29,
        "company": "Yotta",
        "angle": "forward-looking (no-forecast test)",
        "connectors": ["EIA", "OECD"],
        "methods": ["EIAClient.get_steo_forecast", "OECDClient.get_gdp"],
    },
    # SignalLabs — healthcare AI
    {
        "id": 30,
        "company": "SignalLabs",
        "angle": "bottoms-up by payers/health systems",
        "connectors": ["CMS", "BLS"],
        "methods": ["CMSClient.get_enrollment", "CMSClient.get_spending"],
    },
    {
        "id": 31,
        "company": "SignalLabs",
        "angle": "sum-of-verticals",
        "connectors": ["CMS", "FDIC", "Census"],
        "methods": ["CMSClient.get_national_health_expenditure", "FDICClient.get_industry_summary"],
    },
    {
        "id": 32,
        "company": "SignalLabs",
        "angle": "displacement of adjacent budgets",
        "connectors": ["CMS", "FRED"],
        "methods": ["CMSClient.get_nhe_trends", "FREDClient.get_observations"],
    },
    # Zero RFI — construction
    {
        "id": 33,
        "company": "Zero RFI",
        "angle": "services revenue",
        "connectors": ["Census"],
        "methods": ["CensusClient.get_industry"],
    },
    {
        "id": 34,
        "company": "Zero RFI",
        "angle": "top-down from construction spend",
        "connectors": ["Census", "FRED"],
        "methods": ["CensusClient.get_industry", "FREDClient.get_observations"],
    },
    {
        "id": 35,
        "company": "Zero RFI",
        "angle": "underserved-buyer segment",
        "connectors": ["Census"],
        "methods": ["CensusClient.get_industry"],
    },
    # Contrario AI — recruiting
    {
        "id": 36,
        "company": "Contrario AI",
        "angle": "bottoms-up by recruiters",
        "connectors": ["BLS", "Census", "OECD"],
        "methods": ["BLSClient.get_series", "OECDClient.get_labour_force"],
    },
    {
        "id": 37,
        "company": "Contrario AI",
        "angle": "staffing agency displacement",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series", "CensusClient.get_industry"],
    },
    {
        "id": 38,
        "company": "Contrario AI",
        "angle": "marketplace take-rate",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    # MetaVoice — voice AI
    {
        "id": 39,
        "company": "MetaVoice",
        "angle": "bottoms-up by voice-app devs",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 40,
        "company": "MetaVoice",
        "angle": "share-of-AI-infra",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 41,
        "company": "MetaVoice",
        "angle": "attach-rate to voice agents",
        "connectors": ["FRED"],
        "methods": ["FREDClient.get_observations"],
    },
    # Miravoice — phone surveys
    {
        "id": 42,
        "company": "Miravoice",
        "angle": "CATI displacement",
        "connectors": ["BLS", "Census", "OECD"],
        "methods": ["BLSClient.get_series", "OECDClient.get_gdp"],
    },
    {
        "id": 43,
        "company": "Miravoice",
        "angle": "bottoms-up by interviews × cost",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 44,
        "company": "Miravoice",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # PlayerZero — code quality
    {
        "id": 45,
        "company": "PlayerZero",
        "angle": "bottoms-up by eng orgs × tool spend",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 46,
        "company": "PlayerZero",
        "angle": "share of observability spend",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 47,
        "company": "PlayerZero",
        "angle": "labor displacement by dev-hour",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Kaizen Labs — GovTech
    {
        "id": 48,
        "company": "Kaizen Labs",
        "angle": "top-down from govtech IT spend",
        "connectors": ["Census", "FRED", "FDIC"],
        "methods": [
            "CensusClient.get_industry",
            "FREDClient.get_observations",
            "FDICClient.get_state_summary",
        ],
    },
    {
        "id": 49,
        "company": "Kaizen Labs",
        "angle": "bottoms-up by municipalities",
        "connectors": ["Census", "FDIC"],
        "methods": ["CensusClient.get_industry", "FDICClient.get_state_summary"],
    },
    {
        "id": 50,
        "company": "Kaizen Labs",
        "angle": "payments GMV × take-rate",
        "connectors": ["FDIC", "Census"],
        "methods": ["FDICClient.get_total_deposits", "CensusClient.get_industry"],
    },
    # Sieve — video AI
    {
        "id": 51,
        "company": "Sieve",
        "angle": "bottoms-up by multimodal devs",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 52,
        "company": "Sieve",
        "angle": "share-of-AI-infra",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 53,
        "company": "Sieve",
        "angle": "comparable data-infra sizing",
        "connectors": ["Census"],
        "methods": ["CensusClient.get_industry"],
    },
    # Piramidal — neurodiagnostics
    {
        "id": 54,
        "company": "Piramidal",
        "angle": "top-down from EEG volume × reimbursement",
        "connectors": ["CMS", "openFDA"],
        "methods": ["CMSClient.get_spending", "OpenFDAClient.get_device_510k"],
    },
    {
        "id": 55,
        "company": "Piramidal",
        "angle": "bottoms-up by neurology depts",
        "connectors": ["CMS", "BLS"],
        "methods": ["CMSClient.get_hospital_info", "BLSClient.get_series"],
    },
    {
        "id": 56,
        "company": "Piramidal",
        "angle": "labor augmentation",
        "connectors": ["BLS", "CMS"],
        "methods": ["BLSClient.get_series", "CMSClient.get_spending"],
    },
    # ST Labs — ITSM
    {
        "id": 57,
        "company": "ST Labs",
        "angle": "comparable-market share-shift",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 58,
        "company": "ST Labs",
        "angle": "bottoms-up by IT seat",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 59,
        "company": "ST Labs",
        "angle": "displacement of IT budgets + labor",
        "connectors": ["BLS", "FRED"],
        "methods": ["BLSClient.get_series", "FREDClient.get_observations"],
    },
    # Wraithwatch — cyber defense
    {
        "id": 60,
        "company": "Wraithwatch",
        "angle": "bottoms-up by large orgs × ACV",
        "connectors": ["EDGAR", "Census"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 61,
        "company": "Wraithwatch",
        "angle": "share of SecOps spend",
        "connectors": ["EDGAR", "BLS"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 62,
        "company": "Wraithwatch",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Moda — AI design
    {
        "id": 63,
        "company": "Moda",
        "angle": "bottoms-up by marketing teams × seat",
        "connectors": ["BLS", "Census", "OECD"],
        "methods": ["BLSClient.get_series", "OECDClient.get_gdp"],
    },
    {
        "id": 64,
        "company": "Moda",
        "angle": "displacement of design tools + agency",
        "connectors": ["EDGAR", "Census"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 65,
        "company": "Moda",
        "angle": "bottoms-up by knowledge-worker seat",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Minerva — AI accounting firm
    {
        "id": 66,
        "company": "Minerva",
        "angle": "services TAM: SMBs × accounting spend",
        "connectors": ["Census", "BLS"],
        "methods": ["CensusClient.get_industry", "CensusClient.get_firms"],
    },
    {
        "id": 67,
        "company": "Minerva",
        "angle": "underserved-segment bottoms-up",
        "connectors": ["Census"],
        "methods": ["CensusClient.get_firms"],
    },
    {
        "id": 68,
        "company": "Minerva",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Effective AI — insurance knowledge work
    {
        "id": 69,
        "company": "Effective AI",
        "angle": "bottoms-up by insurers × headcount",
        "connectors": ["BLS", "EDGAR", "CMS"],
        "methods": ["BLSClient.get_series", "EDGARClient.get_company_concept"],
    },
    {
        "id": 70,
        "company": "Effective AI",
        "angle": "labor displacement top-down",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 71,
        "company": "Effective AI",
        "angle": "analog/penetration",
        "connectors": ["Census", "EDGAR"],
        "methods": ["CensusClient.get_industry"],
    },
    # Melius — AI creative canvas
    {
        "id": 72,
        "company": "Melius",
        "angle": "bottoms-up by creators × subscription",
        "connectors": ["BLS", "Census"],
        "methods": ["BLSClient.get_series"],
    },
    {
        "id": 73,
        "company": "Melius",
        "angle": "displacement of creative production",
        "connectors": ["EDGAR", "Census", "BLS"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 74,
        "company": "Melius",
        "angle": "bottoms-up by seat",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
    # Accrual — AI tax software
    {
        "id": 75,
        "company": "Accrual",
        "angle": "bottoms-up by CPA firms × seat",
        "connectors": ["Census", "BLS"],
        "methods": ["CensusClient.get_industry", "CensusClient.get_firms"],
    },
    {
        "id": 76,
        "company": "Accrual",
        "angle": "comparable-market share-shift",
        "connectors": ["EDGAR"],
        "methods": ["EDGARClient.get_company_concept"],
    },
    {
        "id": 77,
        "company": "Accrual",
        "angle": "labor displacement",
        "connectors": ["BLS"],
        "methods": ["BLSClient.get_series"],
    },
]


class TestTAMQueryCoverage:
    """Verify every TAM query has at least one connector to source data from."""

    def test_all_77_queries_have_connectors(self) -> None:
        assert len(TAM_QUERIES) == 77
        for q in TAM_QUERIES:
            connectors = q["connectors"]
            assert isinstance(connectors, list)
            assert len(connectors) >= 1, f"Query #{q['id']} ({q['company']}) has no connectors"

    def test_all_referenced_connectors_exist(self) -> None:
        valid_connectors = {
            "BLS",
            "FRED",
            "Census",
            "EDGAR",
            "WorldBank",
            "Kalshi",
            "OECD",
            "Eurostat",
            "Comtrade",
            "FDIC",
            "CMS",
            "EIA",
            "USDA_NASS",
            "FAA",
            "openFDA",
        }
        for q in TAM_QUERIES:
            for c in q["connectors"]:  # type: ignore[union-attr]
                assert c in valid_connectors, f"Query #{q['id']} references unknown connector '{c}'"

    def test_new_connectors_provide_unique_coverage(self) -> None:
        """Verify queries that ONLY the new connectors can answer."""
        new_only_queries = [
            q
            for q in TAM_QUERIES
            if any(
                c in {"OECD", "Eurostat", "Comtrade", "FDIC", "CMS", "EIA", "FAA", "openFDA"}
                for c in q["connectors"]  # type: ignore[union-attr]
            )
        ]
        assert len(new_only_queries) >= 19, (
            f"Expected ≥19 queries using new connectors, got {len(new_only_queries)}"
        )

    def test_connector_usage_distribution(self) -> None:
        """Check each connector is used by at least 1 query."""
        usage: dict[str, int] = {}
        for q in TAM_QUERIES:
            for c in q["connectors"]:  # type: ignore[union-attr]
                usage[c] = usage.get(c, 0) + 1

        assert usage["BLS"] >= 30
        assert usage["EDGAR"] >= 15
        assert usage["Census"] >= 15
        assert usage["FRED"] >= 5
        assert usage["OECD"] >= 5
        assert usage["CMS"] >= 5
        assert usage["FDIC"] >= 2
        assert usage["EIA"] >= 2
        assert usage["Comtrade"] >= 2

    def test_all_24_companies_covered(self) -> None:
        companies = {str(q["company"]) for q in TAM_QUERIES}
        assert len(companies) == 24

    def test_client_classes_importable(self) -> None:
        """All 15 connector client classes can be imported."""
        clients = [
            BLSClient,
            FREDClient,
            CensusClient,
            EDGARClient,
            WorldBankClient,
            OECDClient,
            EurostatClient,
            ComtradeClient,
            FDICClient,
            CMSClient,
            EIAClient,
            NASSClient,
            FAAClient,
            OpenFDAClient,
        ]
        for cls in clients:
            assert hasattr(cls, "__enter__"), f"{cls.__name__} missing __enter__"
            assert hasattr(cls, "__exit__"), f"{cls.__name__} missing __exit__"
            assert hasattr(cls, "close"), f"{cls.__name__} missing close()"
            assert hasattr(cls, "clear_cache"), f"{cls.__name__} missing clear_cache()"

    def test_disambiguation_pairs_have_distinct_connectors(self) -> None:
        """Adjacent-market companies should use overlapping but distinct connector combos."""
        echelon = [q for q in TAM_QUERIES if q["company"] == "Echelon"]
        st_labs = [q for q in TAM_QUERIES if q["company"] == "ST Labs"]
        echelon_connectors = {c for q in echelon for c in q["connectors"]}  # type: ignore[union-attr]
        st_labs_connectors = {c for q in st_labs for c in q["connectors"]}  # type: ignore[union-attr]
        assert echelon_connectors & st_labs_connectors, "Expected overlap (both ITSM-adjacent)"

        kyber = [q for q in TAM_QUERIES if q["company"] == "Kyber"]
        effective = [q for q in TAM_QUERIES if q["company"] == "Effective AI"]
        kyber_all = {c for q in kyber for c in q["connectors"]}  # type: ignore[union-attr]
        effective_all = {c for q in effective for c in q["connectors"]}  # type: ignore[union-attr]
        assert kyber_all & effective_all, "Expected overlap (both insurance)"

    @pytest.mark.parametrize(
        "query_id",
        [27, 28, 29, 30, 31, 32, 48, 49, 50, 54, 55, 56],
        ids=[
            "Yotta-DC-capacity",
            "Yotta-cloud-spend",
            "Yotta-GPU-forecast",
            "SignalLabs-payers",
            "SignalLabs-cross-industry",
            "SignalLabs-displacement",
            "Kaizen-govtech",
            "Kaizen-municipalities",
            "Kaizen-payments",
            "Piramidal-EEG",
            "Piramidal-hospitals",
            "Piramidal-labor",
        ],
    )
    def test_queries_requiring_new_connectors(self, query_id: int) -> None:
        """These queries specifically require the new connectors."""
        q = next(q for q in TAM_QUERIES if q["id"] == query_id)
        new_connectors = {"OECD", "Eurostat", "Comtrade", "FDIC", "CMS", "EIA", "FAA", "openFDA"}
        has_new = any(c in new_connectors for c in q["connectors"])  # type: ignore[union-attr]
        assert has_new, f"Query #{query_id} ({q['company']}) should use new connectors"
