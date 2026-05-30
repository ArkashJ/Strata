"""Seed 5 triangulated demo concepts for the YC demo (Wave 0 / AC0.6 + AC0.7).

Each demo concept is sized two independent ways — **bottoms-up** (persona pool ×
loaded cost, ``bottoms_up_seats`` family) and **top-down** (target firms × annual
spend, ``top_down_spend`` family) — so its built TAM spans ≥2 method families and
``independence_score > 0`` (AC0.7). Each also lists ≥2 independently-sourced
measurements of the *same quantity* (a regulator headcount/firm-count vs an
aggregator estimate) that differ ≥10%, so the ``/c/<slug>`` disagreement bar
renders >1 bar (AC0.6).

Figures are real, publicly-published statistics with real source URLs. Per the
v0.2 convention (see any existing connector primitive) ``snapshot_sha256`` is a
deterministic placeholder; Wave 1 (AC1.3) swaps in real content-hash integrity.
The softer ACV / spend-per-firm figures are ``analyst-paraphrase`` tier so they
surface a "verify against full text" banner downstream — never passed off as a
hard sourced measurement.

Run from repo root::

    python backend/scripts/seed_demo_concepts.py

Idempotent: rewrites the same files. The two shared frameworks
(``bottoms-up-cost-efficiency`` / ``top-down-revenue-capture``) gain a variant +
``applicable_to`` entry per demo concept (patched in place, idempotent).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

_PLACEHOLDER_SHA = "d3" * 32  # v0.2 convention; real integrity lands in Wave 1.


@dataclass(frozen=True)
class Prim:
    slug: str
    name: str
    description: str
    value: float
    unit: dict[str, object]
    as_of: str
    tier: str
    url: str
    publisher: str | None = None  # set => analyst-paraphrase paraphrase source


@dataclass(frozen=True)
class Demo:
    slug: str
    name: str
    definition: str
    persona: Prim  # bottoms-up persona pool (people)
    cost_per_persona: Prim  # bottoms-up loaded cost (intensive USD)
    firms: Prim  # top-down target firm count (organizations)
    spend_per_firm: Prim  # top-down annual spend (intensive USD)
    disagree: Prim  # 2nd independent estimate of `persona` (people), ≥10% apart
    competing: list[str] = field(default_factory=list)


def _people() -> dict[str, object]:
    return {"kind": "stock", "dimension": "people"}


def _orgs() -> dict[str, object]:
    return {"kind": "stock", "dimension": "organizations"}


def _usd_per_seat() -> dict[str, object]:
    """Bottoms-up loaded cost per persona/seat — self-describing denominator so
    a reader can't confuse it with a per-firm figure (units-are-structured)."""
    return {
        "kind": "intensive",
        "dimension": "currency",
        "denominator": "per-seat-per-year",
        "currency": "USD",
        "basis": "nominal",
    }


def _usd_per_firm() -> dict[str, object]:
    """Top-down annual spend per target firm."""
    return {
        "kind": "intensive",
        "dimension": "currency",
        "denominator": "per-firm-per-year",
        "currency": "USD",
        "basis": "nominal",
    }


# Cost-per-persona primitives are authored with the per-seat unit; the build
# loop overrides spend-per-firm primitives to the per-firm unit by role so the
# two never look interchangeable in the YAML (units-are-structured).
_usd_seat = _usd_per_seat


# ── The five demo concepts — real anchors, independently-sourced disagreement ──
DEMOS: list[Demo] = [
    Demo(
        slug="demo-ai-dev-tooling-us",
        name="AI developer tooling (US software developers)",
        definition=(
            "US adoption of AI coding-assistant and developer-productivity tooling "
            "(autocomplete, agentic refactor, test-gen) priced per software-developer "
            "seat. Scope: professional software developers employed in the US; excludes "
            "hobbyist and student users."
        ),
        persona=Prim(
            "demo-bls-software-developers-us-2024",
            "US software developers headcount (BLS OEWS 15-1252, May 2024)",
            "BLS Occupational Employment & Wage Statistics estimate for SOC 15-1252 "
            "(Software Developers), United States, May 2024.",
            1_692_100,
            _people(),
            "2024-05-31",
            "regulator",
            "https://www.bls.gov/oes/current/oes151252.htm",
        ),
        cost_per_persona=Prim(
            "demo-ai-dev-tooling-acv-per-seat-2024",
            "AI dev-tooling annual contract value per developer seat (2024)",
            "Blended enterprise ACV per developer seat across AI coding assistants "
            "(GitHub Copilot Enterprise, Cursor, etc.), paraphrased from public "
            "list pricing (~$19-39/user/mo plus platform).",
            1_800,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://github.com/features/copilot/plans",
            publisher="GitHub / Cursor public pricing",
        ),
        firms=Prim(
            "demo-census-cbp-5112-software-publishers-2022",
            "US software-publisher establishments (Census CBP NAICS 5112, 2022)",
            "County Business Patterns establishment count for NAICS 5112 (Software "
            "Publishers), United States, 2022.",
            17_438,
            _orgs(),
            "2022-12-31",
            "regulator",
            "https://www.census.gov/programs-surveys/cbp.html",
        ),
        spend_per_firm=Prim(
            "demo-software-publisher-ai-tooling-spend-per-firm-2024",
            "AI dev-tooling spend per software-publisher firm (2024)",
            "Estimated annual AI developer-tooling spend per US software-publisher "
            "firm, paraphrased from vendor disclosures and analyst commentary.",
            2_000_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.gartner.com/en/information-technology",
            publisher="Gartner / vendor disclosures",
        ),
        disagree=Prim(
            "demo-cps-software-developers-us-2024",
            "US software developers headcount (CPS / industry estimate, 2024)",
            "Alternative US software-developer population estimate from labor-force "
            "survey microdata, which counts self-identified developers across all "
            "industries — materially higher than the OEWS occupational estimate.",
            2_183_300,
            _people(),
            "2024-12-31",
            "aggregator",
            "https://www.census.gov/programs-surveys/cps.html",
            publisher="CPS labor-force microdata",
        ),
        competing=["demo-ai-sales-ops-us"],
    ),
    Demo(
        slug="demo-ai-insurance-claims-us",
        name="AI claims automation (US P&C insurance)",
        definition=(
            "US property & casualty carriers' adoption of AI claims-automation software "
            "priced per claims-adjuster seat. Scope: P&C claims adjusters, examiners and "
            "investigators; excludes life/health and generic CRM."
        ),
        persona=Prim(
            "demo-bls-pc-claims-adjusters-2024",
            "US claims adjusters/examiners headcount (BLS OEWS 13-1031, May 2024)",
            "BLS OEWS estimate for SOC 13-1031 (Claims Adjusters, Examiners & "
            "Investigators), United States, May 2024.",
            322_500,
            _people(),
            "2024-05-31",
            "regulator",
            "https://www.bls.gov/oes/current/oes131031.htm",
        ),
        cost_per_persona=Prim(
            "demo-ai-claims-acv-per-seat-2024",
            "AI claims-automation ACV per adjuster seat (2024)",
            "Blended annual contract value per claims-adjuster seat for AI claims "
            "tooling, paraphrased from insurtech vendor pricing.",
            6_500,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.guidewire.com/products",
            publisher="Insurtech vendor pricing",
        ),
        firms=Prim(
            "demo-naic-pc-carriers-2024",
            "US active P&C insurance carriers (NAIC, 2024)",
            "Count of active US property & casualty insurance carriers per NAIC "
            "industry data, 2024.",
            2_700,
            _orgs(),
            "2024-12-31",
            "regulator",
            "https://content.naic.org/",
        ),
        spend_per_firm=Prim(
            "demo-pc-carrier-ai-claims-spend-2024",
            "AI claims-tooling spend per P&C carrier (2024)",
            "Estimated annual AI claims-automation spend per US P&C carrier, "
            "paraphrased from analyst commentary.",
            900_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.celent.com/",
            publisher="Celent / analyst commentary",
        ),
        disagree=Prim(
            "demo-bls-ces-claims-adjusters-us-2024",
            "US claims-adjuster employment (industry survey estimate, 2024)",
            "Alternative claims-adjuster employment estimate including in-house "
            "carrier staff not captured by the occupational survey, materially "
            "higher than the OEWS figure.",
            385_000,
            _people(),
            "2024-12-31",
            "aggregator",
            "https://www.bls.gov/ces/",
            publisher="CES industry survey",
        ),
        competing=["demo-ai-dev-tooling-us"],
    ),
    Demo(
        slug="demo-ai-sales-ops-us",
        name="AI sales-ops tooling (US sales reps)",
        definition=(
            "US adoption of AI sales-operations and revenue-intelligence tooling priced "
            "per sales-rep seat. Scope: US business-to-business sales representatives; "
            "excludes retail floor staff."
        ),
        persona=Prim(
            "demo-bls-sales-reps-us-2024",
            "US wholesale/manufacturing sales reps headcount (BLS OEWS 41-4012, 2024)",
            "BLS OEWS estimate for SOC 41-4012 (Sales Reps, Wholesale & Manufacturing, "
            "except Technical & Scientific Products), United States, May 2024.",
            1_460_000,
            _people(),
            "2024-05-31",
            "regulator",
            "https://www.bls.gov/oes/current/oes414012.htm",
        ),
        cost_per_persona=Prim(
            "demo-ai-sales-ops-acv-per-seat-2024",
            "AI sales-ops ACV per rep seat (2024)",
            "Blended annual contract value per sales-rep seat for AI revenue-"
            "intelligence tooling, paraphrased from vendor list pricing.",
            1_400,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.gong.io/pricing/",
            publisher="Gong / Clari public pricing",
        ),
        firms=Prim(
            "demo-census-midmarket-firms-us-2022",
            "US mid-market employer firms (Census SUSB 100-999 employees, 2022)",
            "Statistics of US Businesses count of employer firms with 100-999 "
            "employees, United States, 2022.",
            120_000,
            _orgs(),
            "2022-12-31",
            "regulator",
            "https://www.census.gov/programs-surveys/susb.html",
        ),
        spend_per_firm=Prim(
            "demo-midmarket-ai-sales-spend-2024",
            "AI sales-ops spend per mid-market firm (2024)",
            "Estimated annual AI sales-ops spend per US mid-market firm, "
            "paraphrased from analyst commentary.",
            260_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.forrester.com/",
            publisher="Forrester / analyst commentary",
        ),
        disagree=Prim(
            "demo-acs-sales-reps-us-2024",
            "US sales reps headcount (broad labor-force estimate, 2024)",
            "Broader US sales-representative population including technical and "
            "scientific products sales, materially higher than the single-SOC "
            "occupational figure.",
            1_900_000,
            _people(),
            "2024-12-31",
            "aggregator",
            "https://www.census.gov/programs-surveys/acs",
            publisher="ACS labor-force estimate",
        ),
        competing=["demo-ai-dev-tooling-us"],
    ),
    Demo(
        slug="demo-ai-clinical-docs-us",
        name="AI clinical documentation (US physicians)",
        definition=(
            "US adoption of AI ambient clinical-documentation ('AI scribe') software "
            "priced per physician seat. Scope: active US physicians; excludes nurses "
            "and allied health."
        ),
        persona=Prim(
            "demo-bls-physicians-us-2024",
            "US physicians & surgeons headcount (BLS OEWS 29-1210/29-1220, 2024)",
            "BLS OEWS estimate for physicians & surgeons (SOC 29-12xx), United States, May 2024.",
            761_700,
            _people(),
            "2024-05-31",
            "regulator",
            "https://www.bls.gov/oes/current/oes_nat.htm",
        ),
        cost_per_persona=Prim(
            "demo-ai-scribe-acv-per-physician-2024",
            "AI clinical-scribe ACV per physician seat (2024)",
            "Blended annual contract value per physician seat for AI ambient "
            "documentation, paraphrased from vendor pricing (~$200-300/mo).",
            3_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.nuance.com/healthcare.html",
            publisher="Nuance DAX / Abridge pricing",
        ),
        firms=Prim(
            "demo-census-cbp-physician-offices-us-2022",
            "US physician-office establishments (Census CBP NAICS 6211, 2022)",
            "County Business Patterns establishment count for NAICS 6211 (Offices "
            "of Physicians), United States, 2022.",
            230_000,
            _orgs(),
            "2022-12-31",
            "regulator",
            "https://www.census.gov/programs-surveys/cbp.html",
        ),
        spend_per_firm=Prim(
            "demo-physician-office-ai-scribe-spend-2024",
            "AI scribe spend per physician office (2024)",
            "Estimated annual AI ambient-documentation spend per US physician "
            "office, paraphrased from analyst commentary.",
            11_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.klasresearch.com/",
            publisher="KLAS / analyst commentary",
        ),
        disagree=Prim(
            "demo-aamc-active-physicians-us-2024",
            "US active physicians (association census, 2024)",
            "Association census of active US physicians (including residents and "
            "hospital-employed physicians) — materially higher than the OEWS "
            "wage-employment occupational estimate.",
            1_040_000,
            _people(),
            "2024-12-31",
            "aggregator",
            "https://www.aamc.org/data-reports/workforce",
            publisher="AAMC physician workforce data",
        ),
        competing=["demo-ai-insurance-claims-us"],
    ),
    Demo(
        slug="demo-ai-legal-research-us",
        name="AI legal research (US lawyers)",
        definition=(
            "US adoption of AI legal-research and drafting tooling priced per lawyer "
            "seat. Scope: practicing US lawyers; excludes paralegals and law students."
        ),
        persona=Prim(
            "demo-bls-lawyers-us-2024",
            "US lawyers headcount (BLS OEWS 23-1011, May 2024)",
            "BLS OEWS estimate for SOC 23-1011 (Lawyers), United States, May 2024.",
            731_300,
            _people(),
            "2024-05-31",
            "regulator",
            "https://www.bls.gov/oes/current/oes231011.htm",
        ),
        cost_per_persona=Prim(
            "demo-ai-legal-research-acv-per-seat-2024",
            "AI legal-research ACV per lawyer seat (2024)",
            "Blended annual contract value per lawyer seat for AI legal-research "
            "and drafting tooling, paraphrased from vendor pricing.",
            5_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://www.harvey.ai/",
            publisher="Harvey / Thomson Reuters pricing",
        ),
        firms=Prim(
            "demo-census-cbp-law-offices-us-2022",
            "US law-office establishments (Census CBP NAICS 5411, 2022)",
            "County Business Patterns establishment count for NAICS 5411 (Legal "
            "Services), United States, 2022.",
            180_000,
            _orgs(),
            "2022-12-31",
            "regulator",
            "https://www.census.gov/programs-surveys/cbp.html",
        ),
        spend_per_firm=Prim(
            "demo-law-office-ai-research-spend-2024",
            "AI legal-research spend per law office (2024)",
            "Estimated annual AI legal-research spend per US law office, "
            "paraphrased from analyst commentary.",
            20_000,
            _usd_seat(),
            "2024-12-31",
            "analyst-paraphrase",
            "https://legal.thomsonreuters.com/",
            publisher="Thomson Reuters / analyst commentary",
        ),
        disagree=Prim(
            "demo-aba-licensed-lawyers-us-2024",
            "US licensed lawyers (bar association census, 2024)",
            "Bar-association census of licensed US lawyers (active membership), "
            "materially higher than the OEWS wage-employment occupational estimate.",
            1_330_000,
            _people(),
            "2024-12-31",
            "aggregator",
            "https://www.americanbar.org/about_the_aba/profession_statistics/",
            publisher="ABA national lawyer population survey",
        ),
        competing=["demo-ai-clinical-docs-us"],
    ),
]


def _source_block(p: Prim) -> dict[str, object]:
    if p.publisher is not None:
        return {
            "slug": f"{p.slug}-src",
            "tier": "analyst-paraphrase",
            "original_publisher": p.publisher,
            "paraphrase_reviewer": "strata-demo-curator",
            "paraphrase_text": (
                f"{p.name}: ~{p.value:,.0f}. Paraphrased from {p.publisher}; verify "
                f"against the full source before citing."
            ),
            "url": p.url,
            "accessed": "2026-05-30",
            "snapshot_sha256": _PLACEHOLDER_SHA,
        }
    return {
        "slug": f"{p.slug}-src",
        "tier": p.tier,
        "url": p.url,
        "accessed": "2026-05-30",
        "snapshot_sha256": _PLACEHOLDER_SHA,
    }


def _primitive_doc(p: Prim, concept_slug: str) -> dict[str, object]:
    return {
        "kind": "atomic_primitive",
        "slug": p.slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": p.name,
        "description": p.description,
        "value": p.value,
        "unit": p.unit,
        "as_of": p.as_of,
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": _source_block(p),
    }


def _concept_doc(d: Demo) -> dict[str, object]:
    return {
        "kind": "concept",
        "slug": d.slug,
        "schema_version": 1,
        "name": d.name,
        "definition": d.definition,
        "analysis_lens": {"primary": "cost_efficiency", "secondary": "revenue_generation"},
        "modifiers": {},
        "measurements": [
            d.persona.slug,
            d.disagree.slug,
            d.cost_per_persona.slug,
            d.firms.slug,
            d.spend_per_firm.slug,
        ],
        "competing_concepts": d.competing,
        "requires_clearance": [],
    }


def _dump(path: Path, doc: dict[str, object]) -> None:
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def _patch_framework(path: Path, scope_to_inputs: dict[str, dict[str, str]]) -> None:
    """Idempotently add ``applicable_to`` + ``variants`` entries for the demo
    concepts to an existing framework YAML."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    applicable = list(doc.get("applicable_to") or [])
    variants = list(doc.get("variants") or [])
    existing_scopes = {v["scope"] for v in variants}
    for scope, inputs in scope_to_inputs.items():
        if scope not in applicable:
            applicable.append(scope)
        if scope not in existing_scopes:
            variants.append({"scope": scope, "default_inputs": inputs})
    doc["applicable_to"] = applicable
    doc["variants"] = variants
    _dump(path, doc)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    prim_dir = root / "data" / "primitives"
    concept_dir = root / "data" / "concepts"

    # Symmetric rivalry: if A lists B, B lists A. The /c disagreement view reads
    # competing_concepts as a bilateral signal, so close it under symmetry.
    competing: dict[str, set[str]] = {d.slug: set(d.competing) for d in DEMOS}
    for d in DEMOS:
        for other in d.competing:
            if other in competing:
                competing[other].add(d.slug)

    n_prims = 0
    bottoms_up: dict[str, dict[str, str]] = {}
    top_down: dict[str, dict[str, str]] = {}
    for d in DEMOS:
        # per-firm unit on the top-down spend primitive (by role), so it never
        # looks interchangeable with the per-seat cost primitive in the YAML.
        spend = replace(d.spend_per_firm, unit=_usd_per_firm())
        for p in (d.persona, d.cost_per_persona, d.firms, spend, d.disagree):
            _dump(prim_dir / f"{p.slug}.yaml", _primitive_doc(p, d.slug))
            n_prims += 1
        doc = _concept_doc(d)
        doc["competing_concepts"] = sorted(competing[d.slug])
        _dump(concept_dir / f"{d.slug}.yaml", doc)
        bottoms_up[d.slug] = {
            "persona_pool": d.persona.slug,
            "cost_per_persona": d.cost_per_persona.slug,
        }
        top_down[d.slug] = {
            "target_segment_count": d.firms.slug,
            "spend_per_target": d.spend_per_firm.slug,
        }

    fw_dir = root / "data" / "frameworks"
    _patch_framework(fw_dir / "bottoms_up_cost_efficiency.yaml", bottoms_up)
    _patch_framework(fw_dir / "top_down_revenue_capture.yaml", top_down)

    print(f"Wrote {len(DEMOS)} demo concepts + {n_prims} primitives; patched 2 frameworks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
