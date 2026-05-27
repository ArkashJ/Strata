#!/usr/bin/env python3
"""Claude-driven TAM pipeline: classify portfolio companies, emit Strata YAML, evaluate via DAG.

Architecture (replaces the v1 ``tam_77_estimates.py`` hardcoded-multiplier
script, which is kept on disk as a historical reference until this pipeline
is fully audited):

    PER COMPANY
    -----------
    1. Build a prompt with the company description, 77-query angles,
       existing concepts/frameworks/primitives so Claude knows what's there.
    2. Call Claude (claude-opus-4-7) with the classify_company tool. Claude
       returns: lens, framework_slug (one of the 5 existing), geo profile,
       concept definition, and the 2-3 input primitives the framework needs.
    3. Best-effort enrich primitives flagged with a connector_hint by
       calling the live API (BLS series, Census NAICS, FRED indicator,
       World Bank indicator, openFDA endpoint, etc.) and overwriting
       Claude's estimate with the regulator-sourced value + real SHA256 of
       the response payload.
    4. Render and write concept YAML, primitive YAMLs (with deterministic
       SHA256s when no live source is fetched), and append a variant to the
       chosen framework YAML.
    5. Reload the registry and call ``size_concept(slug)`` to produce a real
       TAMOutput. Persist the output as JSON + markdown.

Outputs:
    backend/tam_77_results_v2.json   — per-company TAMOutput + reasoning
    docs/tam-77-corrected.md          — human-readable summary table

Usage::

    cd backend/
    uv run python scripts/tam_77_pipeline.py             # all remaining 21
    uv run python scripts/tam_77_pipeline.py --only Kyber,Endeavor
    uv run python scripts/tam_77_pipeline.py --dry-run   # no YAML writes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

import anthropic  # noqa: E402
import yaml  # noqa: E402
from anthropic.types import ToolUseBlock  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from exa_py import Exa  # noqa: E402

from strata.config import get_settings  # noqa: E402
from strata.connectors.bls import BLSClient  # noqa: E402
from strata.connectors.census import CensusClient  # noqa: E402
from strata.connectors.fred import FREDClient  # noqa: E402
from strata.connectors.openfda import OpenFDAClient  # noqa: E402
from strata.connectors.worldbank import WorldBankClient  # noqa: E402
from strata.evaluator.engine import size_concept  # noqa: E402
from strata.loader import load_data_dir  # noqa: E402
from strata.registry import Registry  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
CLAUDE_MODEL = os.environ.get("STRATA_TAM_CLAUDE_MODEL", "claude-opus-4-7")
DATA_DIR = REPO_ROOT / "data"


# ─── Company catalogue (the 24 portfolio companies) ──────────────────


@dataclass(frozen=True)
class Company:
    name: str
    slug: str
    sector: str
    short_desc: str
    spec_notes: str = ""


COMPANIES: list[Company] = [
    Company(
        "Kyber",
        "kyber-pc-doc-gen",
        "P&C insurance doc-gen",
        "AI document generation for US P&C insurance carriers (policy docs, declarations, endorsements, ACORD forms). State-regulated by 50 US DOIs.",
        "us_only_regulated. International P&C is a separate buyer set with different forms and regulators.",
    ),
    Company(
        "Gather",
        "gather-customer-research",
        "AI customer research / VoC",
        "AI customer-research agent for marketing teams. Replaces qualitative research, surveys, expert networks. Global SaaS.",
        "global_saas. No regulatory gates.",
    ),
    Company(
        "Echelon",
        "echelon-servicenow-agents",
        "ServiceNow development agents",
        "AI agents that build/maintain ServiceNow applications. Sold to ServiceNow customers (F500 + global enterprises). Platform-bound.",
        "global_saas via ServiceNow. Platform-bound to ServiceNow customer base.",
    ),
    Company(
        "Endeavor",
        "endeavor-mfg-back-office",
        "Mfg/distribution back-office AI",
        "AI workflow agents for manufacturing + distribution back-office (quote-to-cash, order management, ERP automation). Global industrial.",
        "global_industrial. Realistic SAM is <20% of the total mfg back-office labor pool ($75B ceiling — apply addressability + capture).",
    ),
    Company(
        "Skyramp",
        "skyramp-qa-automation",
        "QA / test automation",
        "AI test-generation and QA automation for software engineering teams. Global SaaS sold to eng orgs worldwide.",
        "global_saas. Persona = BLS QA / software-dev headcount; cost = QA tool spend per dev.",
    ),
    Company(
        "Supermemory",
        "supermemory-ai-memory-infra",
        "AI memory infra",
        "Memory layer infra for AI applications (long-term context, retrieval). Sold as API to AI app devs globally. Infra-stack layer.",
        "infra_layer. Size by sum of application markets enabled (agent platforms, copilots, chatbots) x memory share of AI infra spend.",
    ),
    Company(
        "Numeral",
        "numeral-tax-compliance",
        "Sales-tax / VAT compliance",
        "Sales-tax and VAT compliance automation for ecommerce + SaaS. US sales tax + EU VAT + APAC GST.",
        "global_saas with jurisdictional compliance rules; share-shift from Avalara/Vertex incumbent market.",
    ),
    Company(
        "SignalLabs",
        "signallabs-healthcare-decision-ai",
        "Healthcare decision AI",
        "AI decision-intelligence layer for US health payers + provider systems. HIPAA-bound.",
        "us_only_regulated. International healthcare AI is a separate stack.",
    ),
    Company(
        "Zero RFI",
        "zerorfi-construction-rfi",
        "ConTech RFI / owner's-rep",
        "AI for construction RFI / change-order management and owner's-rep workflow. US commercial construction.",
        "us_only_regulated by procurement. Owner's-rep AI slice << $72B total construction services.",
    ),
    Company(
        "Contrario AI",
        "contrario-ai-recruiting",
        "AI recruiting agents",
        "AI agents for talent-acquisition teams (sourcing, screening, outreach). Global SaaS sold to TA teams worldwide.",
        "global_saas. Comp set: Mercor, Paraform. Displacement of staffing-agency revenue.",
    ),
    Company(
        "Miravoice",
        "miravoice-phone-surveys",
        "AI phone surveys / CATI",
        "AI voice surveys replacing CATI (computer-aided telephone interviewing). Global market-research industry.",
        "global_saas. Displacement of CATI labor + survey call-centers.",
    ),
    Company(
        "PlayerZero",
        "playerzero-code-quality",
        "AI code quality / observability",
        "AI code-quality and debug-assist tools for engineering teams. Global SaaS.",
        "global_saas. Share of observability / APM spend (Datadog comp set).",
    ),
    Company(
        "Kaizen Labs",
        "kaizen-labs-govtech",
        "US state/local GovTech",
        "AI-native resident-services and payments platform for US state + local governments.",
        "us_only_regulated by procurement scope. Cooperative purchasing + state IT procurement rules.",
    ),
    Company(
        "Sieve",
        "sieve-multimodal-infra",
        "Multimodal AI infra",
        "Video and audio AI APIs for developers. Multimodal pipeline infra (processing, transformation, generation).",
        "infra_layer. Size by app markets enabled (video gen, video editing, content moderation, video search).",
    ),
    Company(
        "ST Labs",
        "st-labs-ai-itsm",
        "AI-native ITSM",
        "AI-native ITSM platform competing with ServiceNow/Atlassian/Freshworks for IT teams. Global SaaS.",
        "global_saas. Share-shift from ITSM incumbents (Atlassian, Freshworks).",
    ),
    Company(
        "Wraithwatch",
        "wraithwatch-cyber-defense",
        "Agentic cyber defense",
        "Autonomous AI agents for cyber defense (SOC, incident response, pentest). Sold to F500 and government globally.",
        "global_saas. Share of SecOps spend; SOC analyst + pentester labor displacement.",
    ),
    Company(
        "Moda",
        "moda-ai-design",
        "AI brand-design agents",
        "AI brand-design agents for marketing and content teams. Global SaaS sold to marketers worldwide.",
        "global_saas. Displacement of design tools + agency spend.",
    ),
    Company(
        "Minerva",
        "minerva-ai-accounting-firm",
        "AI-native accounting firm (US CPA)",
        "AI-native accounting *firm* for US SMBs. Requires US CPA licensure for sign-off; firm structure regulated state-by-state.",
        "us_only_regulated. Realistic SAM is single-digit % of $43B total SMB accounting services ceiling.",
    ),
    Company(
        "Effective AI",
        "effective-ai-insurance-knowledge",
        "Insurance actuarial / underwriting AI",
        "AI agents for insurance actuarial and underwriting knowledge work. Jurisdiction-bound (US state DOIs).",
        "us_only_regulated. Actuarial work is state-DOI-bound; cross-border ratemaking does not transfer.",
    ),
    Company(
        "Melius",
        "melius-creative-canvas",
        "AI creative canvas / image+video gen",
        "AI image / video generation canvas for marketers and creators. Global SaaS.",
        "global_saas. Displacement of stock-photo + creative-agency spend.",
    ),
    Company(
        "Accrual",
        "accrual-ai-tax-software",
        "AI tax software for US CPA firms",
        "AI-native tax-preparation and accounting software for US CPA firms. US federal/state tax code only.",
        "us_only_regulated. Share-shift from Intuit / Thomson Reuters / Wolters Kluwer.",
    ),
]


# Slugs of the 3 hand-crafted worked examples already in the data bank.
HAND_CRAFTED = {"yotta-india-cloud", "voice-ai-infra-global", "piramidal-eeg-multi-geo"}


# ─── Claude tool schema ──────────────────────────────────────────────


CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_company",
    "description": (
        "Classify a portfolio company onto Strata's existing primitive/framework "
        "DAG. Pick exactly one of the 5 existing framework slugs. Emit 2 input "
        "primitives (one per framework input). Each primitive must declare its "
        "own value, unit, geo, source tier + URL. Apply addressability + capture "
        "% multipliers by embedding them into the primitive values rather than "
        "the framework formula (Q15: frameworks have no scalar defaults)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "concept_name": {"type": "string"},
            "concept_definition": {
                "type": "string",
                "description": "2-4 sentence narrow-scope market definition. Mention regulatory regime, geographic scope.",
            },
            "analysis_lens": {
                "type": "string",
                "enum": [
                    "cost_efficiency",
                    "revenue_generation",
                    "platform_throughput",
                    "bundle_consolidation",
                    "productivity_uplift",
                ],
            },
            "framework_slug": {
                "type": "string",
                "enum": [
                    "bottoms-up-cost-efficiency",
                    "top-down-revenue-capture",
                    "productivity-uplift-value-split",
                    "consolidation-sum-then-discount",
                    "throughput-take-rate",
                ],
            },
            "geo_profile": {
                "type": "string",
                "enum": [
                    "us_only_regulated",
                    "india_only",
                    "global_saas",
                    "infra_layer",
                    "multi_jurisdiction_regulated",
                    "global_industrial",
                ],
                "description": (
                    "Affects geo on the input primitives. us_only_regulated -> "
                    "level=country codes=[US] with intl TAM structurally 0. "
                    "india_only -> codes=[IN]. global_saas -> level=global "
                    "codes=[WLD]. infra_layer -> codes=[WLD]. "
                    "multi_jurisdiction_regulated -> codes=[WLD] with the per-geo "
                    "decomposition explained in the paraphrase_text. "
                    "global_industrial -> codes=[WLD]."
                ),
            },
            "input_primitives": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "description": (
                    "Exactly 2 primitives, one per framework input. role_name "
                    "must match the framework input names exactly: "
                    "bottoms-up-cost-efficiency -> [persona_pool, cost_per_persona]; "
                    "top-down-revenue-capture -> [target_segment_count, spend_per_target]; "
                    "productivity-uplift-value-split -> [persona_count, value_split_to_vendor]; "
                    "consolidation-sum-then-discount -> [tools_displaced, consolidation_rate]; "
                    "throughput-take-rate -> [gmv_or_volume, take_rate]."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "role_name": {"type": "string"},
                        "slug": {
                            "type": "string",
                            "description": "kebab-case-with-year-suffix, e.g. 'us-pc-carriers-naic-2024'.",
                        },
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "value": {"type": "number"},
                        "unit_kind": {
                            "type": "string",
                            "enum": ["stock", "flow", "intensive", "dimensionless"],
                        },
                        "unit_dimension": {
                            "type": "string",
                            "enum": [
                                "people",
                                "currency",
                                "transactions",
                                "events",
                                "percent",
                                "tokens",
                                "impressions",
                                "organizations",
                                "seats",
                            ],
                        },
                        "unit_currency": {"type": "string"},
                        "unit_denominator": {"type": "string"},
                        "geo_level": {
                            "type": "string",
                            "enum": ["country", "subnational", "supranational", "global"],
                        },
                        "geo_codes": {"type": "array", "items": {"type": "string"}},
                        "geo_perspective": {
                            "type": "string",
                            "enum": ["supply", "demand", "mixed", "unknown"],
                        },
                        "source_tier": {
                            "type": "string",
                            "enum": [
                                "regulator",
                                "aggregator",
                                "analyst",
                                "analyst-paraphrase",
                                "community-modeled",
                            ],
                        },
                        "source_url": {"type": "string"},
                        "source_slug": {"type": "string"},
                        "original_publisher": {
                            "type": "string",
                            "description": "Required when source_tier=analyst-paraphrase.",
                        },
                        "paraphrase_text": {
                            "type": "string",
                            "maxLength": 280,
                            "description": "Required when source_tier=analyst-paraphrase. Max 280 chars (Q40 fair-use).",
                        },
                        "connector_hint": {
                            "type": "object",
                            "description": (
                                "Optional: if this value is sourceable from a Strata connector, "
                                "fill this and the script will overwrite ``value`` with the "
                                "live API response."
                            ),
                            "properties": {
                                "connector": {
                                    "type": "string",
                                    "enum": ["BLS", "FRED", "Census", "WorldBank", "openFDA"],
                                },
                                "method": {"type": "string"},
                                "series_or_code": {"type": "string"},
                            },
                            "required": ["connector"],
                        },
                        "uncertainty_low": {"type": "number"},
                        "uncertainty_high": {"type": "number"},
                        "uncertainty_basis": {"type": "string"},
                    },
                    "required": [
                        "role_name",
                        "slug",
                        "name",
                        "description",
                        "value",
                        "unit_kind",
                        "unit_dimension",
                        "geo_level",
                        "geo_codes",
                        "geo_perspective",
                        "source_tier",
                        "source_url",
                        "source_slug",
                    ],
                },
            },
            "addressability_justification": {
                "type": "string",
                "description": "Explain how the addressability + (if applicable) capture % are baked into the primitive values rather than being separate multipliers.",
            },
            "reasoning_chain": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5-8 short steps: geo decision -> framework choice -> primitive sourcing -> addressability handling -> sanity check vs spec target.",
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
            "spec_target_band_usd_b": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
                "description": "[low, high] in $B. The expected TAM band per the methodology spec; the evaluator's result should land here.",
            },
        },
        "required": [
            "concept_name",
            "concept_definition",
            "analysis_lens",
            "framework_slug",
            "geo_profile",
            "input_primitives",
            "addressability_justification",
            "reasoning_chain",
            "warnings",
            "spec_target_band_usd_b",
        ],
    },
}


SYSTEM_PROMPT = """You are Strata's TAM classification engine. For one portfolio company,
classify it onto Strata's primitive/framework DAG and emit the data records.

THE 5 EXISTING FRAMEWORKS (do not invent new ones):

| slug | lens | inputs (role_name, unit) | when to use |
|---|---|---|---|
| bottoms-up-cost-efficiency | cost_efficiency | persona_pool (stock_people), cost_per_persona (intensive_currency_USD) | persona-replacement sizing (Harvey/Glean style) |
| top-down-revenue-capture | revenue_generation | target_segment_count (stock_organizations), spend_per_target (intensive_currency_USD) | enterprise spend capture (Brex/Rippling style) |
| productivity-uplift-value-split | productivity_uplift | persona_count (stock_people), value_split_to_vendor (intensive_currency_USD) | per-persona productivity uplift (Copilot style) |
| consolidation-sum-then-discount | bundle_consolidation | tools_displaced (flow_currency_USD), consolidation_rate (dimensionless_percent) | replacing an incumbent spend pool with a share-shift (Microsoft 365 style) |
| throughput-take-rate | platform_throughput | gmv_or_volume (flow_currency_USD), take_rate (dimensionless_percent) | infra layer or platform taking a share of throughput (Stripe / voice-infra style) |

HARD RULES:
1. Q15 — frameworks have no scalar defaults. Every input is a primitive slug. So
   addressability % and capture % MUST be embedded into the primitive values you emit,
   not added as separate framework multipliers. Example: for Endeavor's persona_pool
   primitive, instead of "2M mfg back-office workers" + a 0.25 addressability multiplier,
   emit "addressable AI-eligible mfg back-office personas = 500K" with the calculation
   shown in the description and source paraphrase.
2. Geo profile drives the geo block. us_only_regulated -> level=country codes=["US"] and
   intl TAM is structurally 0. india_only -> codes=["IN"]. global_saas / infra_layer /
   multi_jurisdiction_regulated -> level=global codes=["WLD"] (and explain the multi-geo
   decomposition in the paraphrase_text for multi_jurisdiction_regulated).
3. Source tier rules:
   - regulator: BLS, Census, FRED, openFDA, CMS (US gov), Eurostat (EU regulator).
     Use only if the primitive value really came from one of those APIs. Include
     ``connector_hint`` so the script can fetch the live value.
   - aggregator: World Bank, OECD, UN Comtrade.
   - analyst: published, citable industry report not behind paywall.
   - analyst-paraphrase: paywalled Gartner / IDC / Frost. REQUIRES original_publisher
     + paraphrase_text (<=280 chars) + paraphrase_reviewer (the script fills in "arkash").
   - community-modeled: % multipliers, take rates, share-of-stack estimates that have no
     direct citable source — your reasoning is the source. Carry uncertainty range.
4. Don't repeat the 12 errors:
   - Endeavor / Zero RFI / Minerva: realistic SAM, not labor-pool ceilings (apply addressability).
   - US-only-regulated companies: $0 intl TAM (geo_codes=["US"] only).
   - Infra layers: gmv_or_volume = application stack revenue (not nascent API ARR);
     take_rate = infra share of stack.
   - Share-shift companies (Numeral, Accrual, ST Labs): use consolidation-sum-then-discount
     with tools_displaced = incumbent revenue pool and consolidation_rate = realistic capture %.
5. spec_target_band_usd_b should be your honest estimate of where the TAM should land
   per the corrected methodology spec. The evaluator will run framework x primitives and
   produce a number; if it's outside your band you'll know your primitives are off.
"""


# ─── Connector enrichment (best-effort) ──────────────────────────────


def enrich_with_connector(prim: dict[str, Any], log: logging.Logger) -> dict[str, Any]:
    """If Claude flagged a primitive with a connector_hint, fetch the live value
    and overwrite. Returns the updated primitive dict. Failures fall back to
    Claude's estimate with a warning."""
    hint = prim.get("connector_hint")
    if not hint:
        return prim
    connector = hint.get("connector")
    series = hint.get("series_or_code", "")
    try:
        settings = get_settings()
        live_value: float | None = None
        raw_payload: str | None = None
        if connector == "BLS":
            with BLSClient(api_key=settings.bls_api_key) as bls:
                r = bls.get_series(series)
                if r.series and r.series[0].data:
                    live_value = float(r.series[0].data[0].value)
                    raw_payload = json.dumps(
                        [d.__dict__ for d in r.series[0].data[:3]], default=str
                    )
        elif connector == "FRED":
            with FREDClient(api_key=settings.fred_api_key or "") as fred:
                r = fred.get_observations(series)
                if r.observations:
                    live_value = float(r.observations[-1].value)
                    raw_payload = json.dumps([o.__dict__ for o in r.observations[-3:]], default=str)
        elif connector == "Census":
            with CensusClient(api_key=settings.census_api_key) as census:
                r = census.get_industry(series, year=2022)
                if r.industries:
                    live_value = float(r.industries[0].establishments)
                    raw_payload = json.dumps(r.industries[0].__dict__, default=str)
        elif connector == "WorldBank":
            with WorldBankClient() as wb:
                country = hint.get("country", "US")
                r = wb.get_indicator(series, country=country, date_range="2022:2023")
                vals = [d.value for d in r.data if d.value is not None and d.indicator == series]
                if vals:
                    live_value = float(max(vals))
                    raw_payload = json.dumps([{"value": v, "indicator": series} for v in vals[:3]])
        elif connector == "openFDA":
            with OpenFDAClient(api_key=settings.openfda_api_key) as fda:
                if "device" in series:
                    r = fda.get_device_510k(start_date="20230101", end_date="20231231", limit=1)
                    live_value = float(r.total)
                    raw_payload = f'{{"total": {r.total}}}'
        if live_value is not None and raw_payload is not None:
            prim["value"] = live_value
            prim["source_tier"] = (
                "regulator" if connector in {"BLS", "FRED", "Census", "openFDA"} else "aggregator"
            )
            prim["snapshot_sha256_override"] = hashlib.sha256(raw_payload.encode()).hexdigest()
            log.info(
                "    enriched %s via %s/%s -> %.0f", prim["slug"], connector, series, live_value
            )
        else:
            log.warning(
                "    %s connector %s returned no value; keeping Claude estimate",
                prim["slug"],
                connector,
            )
    except Exception as exc:
        log.warning(
            "    %s connector %s/%s failed: %s; keeping Claude estimate",
            prim["slug"],
            connector,
            series,
            exc,
        )
    return prim


# ─── YAML rendering ──────────────────────────────────────────────────


def deterministic_sha256(prim: dict[str, Any]) -> str:
    if "snapshot_sha256_override" in prim:
        return cast(str, prim["snapshot_sha256_override"])
    key = f"{prim['slug']}|{prim['source_slug']}|{prim.get('source_url', '')}|{date.today().isoformat()}"
    return hashlib.sha256(key.encode()).hexdigest()


def render_primitive_yaml(prim: dict[str, Any], concept_slug: str) -> str:
    sha = deterministic_sha256(prim)
    unit: dict[str, Any] = {
        "kind": prim["unit_kind"],
        "dimension": prim["unit_dimension"],
    }
    if prim.get("unit_currency"):
        unit["currency"] = prim["unit_currency"]
    if prim.get("unit_denominator"):
        unit["denominator"] = prim["unit_denominator"]
    record: dict[str, Any] = {
        "kind": "atomic_primitive",
        "slug": prim["slug"],
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": prim["name"],
        "description": prim["description"],
        "value": prim["value"],
        "unit": unit,
        "as_of": "2024-12-31",
        "geo": {"level": prim["geo_level"], "codes": prim["geo_codes"]},
        "geo_perspective": prim["geo_perspective"],
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
    }
    if prim["source_tier"] == "community-modeled":
        record["expiry"] = "2027-05-26"
    if prim.get("uncertainty_low") is not None and prim.get("uncertainty_high") is not None:
        record["uncertainty"] = {
            "range": [prim["uncertainty_low"], prim["uncertainty_high"]],
            "basis": prim.get("uncertainty_basis", "Claude-modeled range."),
        }
    src: dict[str, Any] = {
        "slug": prim["source_slug"],
        "tier": prim["source_tier"],
        "url": prim["source_url"],
        "accessed": "2026-05-26",
        "snapshot_sha256": sha,
    }
    if prim["source_tier"] == "analyst-paraphrase":
        src["original_publisher"] = prim.get("original_publisher", "Industry composite")
        src["paraphrase_reviewer"] = "arkash"
        src["paraphrase_text"] = prim.get("paraphrase_text", prim["description"][:280])
    record["source"] = src
    return yaml.safe_dump(record, sort_keys=False, default_flow_style=False, allow_unicode=True)


def render_concept_yaml(
    slug: str, name: str, definition: str, lens: str, prim_slugs: list[str]
) -> str:
    record = {
        "kind": "concept",
        "slug": slug,
        "schema_version": 1,
        "name": name,
        "definition": definition,
        "analysis_lens": {"primary": lens},
        "modifiers": {},
        "measurements": prim_slugs,
        "competing_concepts": [],
        "requires_clearance": [],
    }
    return yaml.safe_dump(record, sort_keys=False, default_flow_style=False, allow_unicode=True)


def append_framework_variant(
    framework_slug: str, concept_slug: str, default_inputs: dict[str, str], log: logging.Logger
) -> None:
    fw_path = next(
        (
            p
            for p in DATA_DIR.glob("frameworks/*.yaml")
            if framework_slug.replace("-", "_") in p.name
        ),
        None,
    )
    if fw_path is None:
        raise FileNotFoundError(f"framework YAML for {framework_slug} not found")
    text = fw_path.read_text()
    if f"scope: {concept_slug}" in text:
        log.info("    variant for %s already present in %s", concept_slug, fw_path.name)
        return
    if f"  - {concept_slug}\n" not in text:
        text = re.sub(
            r"(applicable_to:\n(?:  - [^\n]+\n)+)",
            lambda m: m.group(1) + f"  - {concept_slug}\n",
            text,
            count=1,
        )
    variant_block = f"  - scope: {concept_slug}\n    default_inputs:\n"
    for role, slug in default_inputs.items():
        variant_block += f"      {role}: {slug}\n"
    # Append variant before the trailing fields (expansion_stage_parameter)
    text = re.sub(
        r"(\nvariants:\n(?:  - scope:[^\n]+\n(?:    [^\n]+\n)+)+)",
        lambda m: m.group(1) + variant_block,
        text,
        count=1,
    )
    fw_path.write_text(text)
    log.info("    appended variant scope=%s to %s", concept_slug, fw_path.name)


# ─── Claude call ─────────────────────────────────────────────────────


@dataclass
class ClassificationResult:
    company: Company
    classification: dict[str, Any]
    primitives_after_enrichment: list[dict[str, Any]]
    tam_output_state_hash: str | None = None
    tam_value_usd: float | None = None
    tam_lens: str | None = None
    tam_framework: str | None = None
    errors: list[str] = field(default_factory=list)


def _fetch_exa_context(company: Company, exa: Exa | None, log: logging.Logger) -> str:
    """Search Exa for industry context (market sizes, comps, funding). Returns a
    text block that gets injected into Claude's classification prompt."""
    if exa is None:
        return ""
    queries = [
        f"{company.name} {company.sector} market size TAM 2024",
        f"{company.sector} industry revenue competitors funding",
    ]
    snippets: list[str] = []
    for q in queries:
        try:
            results = exa.search(q, type="auto", num_results=3, contents={"highlights": True})
            for r in results.results[:2]:
                highlights = "; ".join(r.highlights or [])[:400]
                if highlights:
                    snippets.append(f"[{r.title or ''}] {highlights}")
        except Exception as exc:
            log.warning("  exa search failed for %s: %s", q[:60], exc)
    if not snippets:
        return ""
    return "EXA INDUSTRY CONTEXT:\n" + "\n".join(snippets[:4])


def classify_with_claude(
    company: Company,
    client: anthropic.Anthropic,
    log: logging.Logger,
    *,
    exa_context: str = "",
) -> dict[str, Any]:
    exa_block = f"\n\n{exa_context}" if exa_context else ""
    user_prompt = f"""COMPANY: {company.name}
SECTOR: {company.sector}
DESCRIPTION: {company.short_desc}
METHODOLOGY NOTES FROM SPEC: {company.spec_notes}
{exa_block}

Slug for concept: {company.slug}

Pick the right framework and emit 2 input primitives. Embed any addressability /
capture multipliers INSIDE the primitive values (e.g. "AI-addressable persona pool"
rather than total pool, with the math shown in description + paraphrase). Use
connector_hint when a primitive can be sourced from BLS / Census / FRED / openFDA /
World Bank. Provide spec_target_band_usd_b so I can verify the evaluator's output."""
    log.info("  claude classifying %s (model=%s)", company.name, CLAUDE_MODEL)
    start = time.time()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_company"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    log.info("  claude %s done in %.1fs", company.name, time.time() - start)
    for block in resp.content:
        if isinstance(block, ToolUseBlock) and block.name == "classify_company":
            return cast(dict[str, Any], block.input)
    raise RuntimeError(f"Claude did not return classify_company tool_use for {company.name}")


# ─── Pipeline driver ─────────────────────────────────────────────────


def process_company(
    company: Company,
    anthropic_client: anthropic.Anthropic,
    exa_client: Exa | None,
    dry_run: bool,
    log: logging.Logger,
) -> ClassificationResult:
    exa_context = _fetch_exa_context(company, exa_client, log)
    classification = classify_with_claude(company, anthropic_client, log, exa_context=exa_context)
    primitives = list(classification.get("input_primitives", []))
    if len(primitives) != 2:
        return ClassificationResult(
            company=company,
            classification=classification,
            primitives_after_enrichment=primitives,
            errors=[f"expected 2 primitives, got {len(primitives)}"],
        )
    enriched = [enrich_with_connector(dict(p), log) for p in primitives]

    if dry_run:
        log.info("  [dry-run] would write concept + 2 primitives + framework variant")
        return ClassificationResult(
            company=company,
            classification=classification,
            primitives_after_enrichment=enriched,
        )

    # Write concept + primitives
    concept_yaml = render_concept_yaml(
        slug=company.slug,
        name=classification["concept_name"],
        definition=classification["concept_definition"],
        lens=classification["analysis_lens"],
        prim_slugs=[p["slug"] for p in enriched],
    )
    (DATA_DIR / "concepts" / f"{company.slug}.yaml").write_text(concept_yaml)
    for prim in enriched:
        (DATA_DIR / "primitives" / f"{prim['slug']}.yaml").write_text(
            render_primitive_yaml(prim, company.slug)
        )
    append_framework_variant(
        framework_slug=classification["framework_slug"],
        concept_slug=company.slug,
        default_inputs={p["role_name"]: p["slug"] for p in enriched},
        log=log,
    )

    # Reload registry, run evaluator
    try:
        records = load_data_dir(DATA_DIR)
        registry = Registry.from_loaded(records)
        tam = size_concept(registry, company.slug)
        if tam.scenarios:
            s = tam.scenarios[0]
            return ClassificationResult(
                company=company,
                classification=classification,
                primitives_after_enrichment=enriched,
                tam_output_state_hash=tam.state_hash,
                tam_value_usd=s.value,
                tam_lens=s.lens.value,
                tam_framework=s.framework,
            )
        return ClassificationResult(
            company=company,
            classification=classification,
            primitives_after_enrichment=enriched,
            errors=["evaluator returned 0 scenarios"],
        )
    except Exception as exc:
        log.error("  evaluator failed for %s: %s", company.name, exc)
        return ClassificationResult(
            company=company,
            classification=classification,
            primitives_after_enrichment=enriched,
            errors=[f"evaluator error: {exc}"],
        )


def fmt_b(v: float | None) -> str:
    if v is None or v <= 0:
        return "n/a"
    if v >= 1e12:
        return f"${v / 1e12:.1f}T"
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def write_outputs(
    results: list[ClassificationResult], hand_crafted_tams: list[dict[str, Any]]
) -> None:
    json_payload = [
        {
            "company": r.company.name,
            "concept_slug": r.company.slug,
            "sector": r.company.sector,
            "tam_state_hash": r.tam_output_state_hash,
            "tam_value_usd": r.tam_value_usd,
            "tam_lens": r.tam_lens,
            "tam_framework": r.tam_framework,
            "geo_profile": r.classification.get("geo_profile"),
            "spec_target_band_usd_b": r.classification.get("spec_target_band_usd_b"),
            "addressability_justification": r.classification.get("addressability_justification"),
            "reasoning_chain": r.classification.get("reasoning_chain"),
            "warnings": r.classification.get("warnings"),
            "errors": r.errors,
            "primitives": [
                {k: v for k, v in p.items() if k != "snapshot_sha256_override"}
                for p in r.primitives_after_enrichment
            ],
        }
        for r in results
    ] + hand_crafted_tams
    (REPO_ROOT / "backend" / "tam_77_results_v2.json").write_text(
        json.dumps(json_payload, indent=2, default=str)
    )

    lines = [
        "# Strata TAM v2 — 24 Portfolio Companies, Corrected Methodology",
        "",
        "Generated via Claude classification (`"
        + CLAUDE_MODEL
        + "`) + Strata's primitive/framework/evaluator DAG. "
        "Replaces `docs/tam-77-results.md`. Per-company artifacts live as YAML in `data/concepts/`, "
        "`data/primitives/`, and as variants in `data/frameworks/`. Each TAM is reproducible via "
        "`uv run strata size <concept_slug> -d ../data`.",
        "",
        "## Summary",
        "",
        "| # | Company | Sector | Geo | Lens | Framework | TAM | Spec target |",
        "|---|---------|--------|-----|------|-----------|-----|-------------|",
    ]
    for i, item in enumerate(json_payload, 1):
        band = item.get("spec_target_band_usd_b")
        band_str = f"${band[0]}-{band[1]}B" if band else "—"
        lines.append(
            f"| {i} | {item['company']} | {item['sector']} | "
            f"`{item.get('geo_profile', '—')}` | `{item.get('tam_lens', '—')}` | "
            f"`{item.get('tam_framework', '—')}` | **{fmt_b(item.get('tam_value_usd'))}** | {band_str} |"
        )
    lines += [
        "",
        "## Per-Company Reasoning",
        "",
    ]
    for item in json_payload:
        lines.append(f"### {item['company']} — {item.get('sector', '')}")
        lines.append("")
        if item.get("errors"):
            lines.append("**Errors:** " + "; ".join(item["errors"]))
            lines.append("")
        lines.append(
            f"- **TAM:** {fmt_b(item.get('tam_value_usd'))} "
            f"(state hash `{item.get('tam_state_hash') or 'n/a'}`)"
        )
        lines.append(f"- **Geo profile:** `{item.get('geo_profile', '—')}`")
        lines.append(
            f"- **Framework:** `{item.get('tam_framework', '—')}` (lens `{item.get('tam_lens', '—')}`)"
        )
        if item.get("addressability_justification"):
            lines.append(f"- **Addressability:** {item['addressability_justification']}")
        if item.get("reasoning_chain"):
            lines.append("- **Reasoning chain:**")
            for step in item["reasoning_chain"]:
                lines.append(f"  - {step}")
        if item.get("warnings"):
            lines.append("- **Warnings:** " + "; ".join(item["warnings"]))
        lines.append("")
    (REPO_ROOT / "docs" / "tam-77-corrected.md").write_text("\n".join(lines) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated company names; default = all 21 remaining.",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Classify but don't write YAML or run evaluator."
    )
    p.add_argument(
        "--include-handcrafted",
        action="store_true",
        help="Include the 3 already-shipped worked examples in outputs.",
    )
    p.add_argument(
        "--portfolio",
        type=str,
        default="",
        help="Path to a portfolio YAML (see portfolios/tam-77-sample.yaml). When set, the script uses that catalog instead of the in-script COMPANIES list, making the pipeline portfolio-agnostic.",
    )
    return p.parse_args(argv)


def hand_crafted_tam_entries(log: logging.Logger) -> list[dict[str, Any]]:
    """Run the evaluator on the 3 hand-crafted concepts and return their entries."""
    try:
        records = load_data_dir(DATA_DIR)
        registry = Registry.from_loaded(records)
    except Exception as exc:
        log.error("could not load registry for handcrafted entries: %s", exc)
        return []
    out: list[dict[str, Any]] = []
    for slug in HAND_CRAFTED:
        try:
            tam = size_concept(registry, slug)
        except Exception as exc:
            log.warning("handcrafted %s: %s", slug, exc)
            continue
        if not tam.scenarios:
            continue
        s = tam.scenarios[0]
        out.append(
            {
                "company": {
                    "yotta-india-cloud": "Yotta",
                    "voice-ai-infra-global": "MetaVoice",
                    "piramidal-eeg-multi-geo": "Piramidal",
                }.get(slug, slug),
                "concept_slug": slug,
                "sector": {
                    "yotta-india-cloud": "India sovereign cloud",
                    "voice-ai-infra-global": "Voice AI infra",
                    "piramidal-eeg-multi-geo": "Clinical EEG foundation model",
                }.get(slug, ""),
                "tam_state_hash": tam.state_hash,
                "tam_value_usd": s.value,
                "tam_lens": s.lens.value,
                "tam_framework": s.framework,
                "geo_profile": {
                    "yotta-india-cloud": "india_only",
                    "voice-ai-infra-global": "infra_layer",
                    "piramidal-eeg-multi-geo": "multi_jurisdiction_regulated",
                }.get(slug),
                "spec_target_band_usd_b": {
                    "yotta-india-cloud": [3, 5],
                    "voice-ai-infra-global": [13, 16],
                    "piramidal-eeg-multi-geo": [2, 5],
                }.get(slug),
                "addressability_justification": "Hand-crafted worked example per methodology spec.",
                "reasoning_chain": [],
                "warnings": [],
                "errors": [],
                "primitives": [],
            }
        )
    return out


def load_portfolio(path: Path) -> list[Company]:
    raw = yaml.safe_load(path.read_text())
    return [
        Company(
            name=str(c["name"]),
            slug=str(c["slug"]),
            sector=str(c.get("sector", "")),
            short_desc=str(c.get("short_desc", "")),
            spec_notes=str(c.get("spec_notes", "")),
        )
        for c in raw.get("companies", [])
    ]


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr
    )
    log = logging.getLogger("tam77.pipeline")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        return 1
    if args.portfolio:
        catalog = load_portfolio(Path(args.portfolio))
        log.info("Loaded %d companies from portfolio %s", len(catalog), args.portfolio)
    else:
        catalog = COMPANIES
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets = [c for c in catalog if not only or c.name in only]
    log.info("Processing %d companies", len(targets))

    anthropic_client = anthropic.Anthropic()
    exa_client: Exa | None = (
        Exa(api_key=os.environ["EXA_API_KEY"]) if os.environ.get("EXA_API_KEY") else None
    )
    if exa_client is None:
        log.warning("EXA_API_KEY not set — industry context search disabled")

    results: list[ClassificationResult] = []
    for company in targets:
        try:
            results.append(
                process_company(company, anthropic_client, exa_client, args.dry_run, log)
            )
        except Exception as exc:
            log.error("process_company %s crashed: %s", company.name, exc)
            results.append(
                ClassificationResult(
                    company=company,
                    classification={},
                    primitives_after_enrichment=[],
                    errors=[str(exc)],
                )
            )

    hand = hand_crafted_tam_entries(log) if args.include_handcrafted else []
    if not args.dry_run:
        write_outputs(results, hand)
        print("\nWrote backend/tam_77_results_v2.json + docs/tam-77-corrected.md")
    succeeded = [r for r in results if r.tam_value_usd is not None]
    print(
        f"Classified: {len(results)}; with TAM: {len(succeeded)}; errors: {sum(1 for r in results if r.errors)}"
    )
    for r in results:
        band = r.classification.get("spec_target_band_usd_b") or [0, 0]
        in_band = (
            band[0] * 1e9 <= (r.tam_value_usd or 0) <= band[1] * 1e9 if r.tam_value_usd else False
        )
        flag = "✓" if in_band else ("·" if r.tam_value_usd else "✗")
        print(
            f"  {flag} {r.company.name:18s} {fmt_b(r.tam_value_usd):>8s}  (spec: ${band[0]}-{band[1]}B)  {'; '.join(r.errors) if r.errors else ''}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
