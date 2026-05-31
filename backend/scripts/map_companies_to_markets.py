"""Map every company in the portfolio CSV to the curated sized market it competes
in, and inherit that market's *sourced* TAM. No per-company figures are invented
— a company's number is the market TAM of the concept it maps to (Q20-safe).

Coverage strategy (in priority order):
  1. Industry-vertical → concept(s) map (hand-curated against the 37 concepts).
  2. Fuzzy name/definition match (registry `match_concept`) as a tie-breaker.
  3. Honest "uncovered" when no curated market exists for that vertical yet.

Outputs a CSV: name, website, vertical, market_concept, market_tam_usd, lens,
coverage. Prints a per-vertical coverage summary.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from strata.evaluator.engine import EvaluatorError, size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

# Vertical (as tagged in the portfolio CSV) → ordered candidate concept slugs.
# Curated against concept definitions; first slug is the primary market.
VERTICAL_TO_CONCEPTS: dict[str, list[str]] = {
    "Health Tech": [
        "signallabs-healthcare-decision-ai",
        "demo-ai-clinical-docs-us",
        "piramidal-eeg-multi-geo",
    ],
    "Finance & Accounting": [
        "midmarket-saas-spend-na",
        "accrual-ai-tax-software",
        "minerva-ai-accounting-firm",
        "numeral-tax-compliance",
        "demo-ai-insurance-claims-us",
    ],
    "Security": ["wraithwatch-cyber-defense", "st-labs-ai-itsm"],
    "Dev": [
        "ai-coding-assistants-us",
        "software-eng-productivity",
        "demo-ai-dev-tooling-us",
        "playerzero-code-quality",
        "skyramp-qa-automation",
    ],
    "Data": [
        "supermemory-ai-memory-infra",
        "sieve-multimodal-infra",
        "yotta-india-cloud",
        "voice-ai-infra-global",
    ],
    "HR": ["contrario-ai-recruiting"],
    "Analytics": ["gather-customer-research", "miravoice-phone-surveys"],
    "Marketing": ["gtm-ops-tooling-na", "melius-creative-canvas", "moda-ai-design"],
    "Sales": ["demo-ai-sales-ops-us", "gtm-ops-tooling-na"],
    "Prop Tech": ["zerorfi-construction-rfi"],
    "Manufacturing Tech": ["endeavor-mfg-back-office"],
    "Legal": ["ai-legal-assistants-us", "demo-ai-legal-research-us"],
    "Workflow Automation": [
        "echelon-servicenow-agents",
        "workplace-suite-consolidation",
        "st-labs-ai-itsm",
    ],
    "Customer Support": ["voice-ai-infra-global", "miravoice-phone-surveys"],
    "Collaboration": ["workplace-suite-consolidation"],
    "Image & Video": ["sieve-multimodal-infra", "melius-creative-canvas", "moda-ai-design"],
    "Services": ["kaizen-labs-govtech"],
    "Vertical SaaS": ["midmarket-saas-spend-na"],
    "Agents": ["echelon-servicenow-agents"],
    "Voice": ["voice-ai-infra-global"],
}

# Normalize portfolio vertical tags before lookup. Multi-tags ("Dev; Analytics")
# take the first tag; aliases fold onto the canonical vertical.
ALIASES: dict[str, str] = {
    "Healthcare": "Health Tech",
    "Biotech": "Health Tech",
    "D2C": "DTC",
}


def _normalize_vertical(raw: str) -> str:
    first = raw.split(";")[0].strip()
    return ALIASES.get(first, first)


def _concept_tam(reg: Registry, slug: str) -> tuple[float | None, str | None]:
    try:
        out = size_concept(reg, slug)
    except EvaluatorError:
        return None, None
    if not out.scenarios:
        return None, None
    base = out.scenarios[0]
    return base.value, base.lens


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../Cos list.csv")
    out_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../portfolios/cos-list-market-map.csv")
    )
    reg = Registry.from_loaded(load_data_dir(Path("../data")))

    tam_cache: dict[str, tuple[float | None, str | None]] = {}
    for slug in reg.concepts:
        tam_cache[slug] = _concept_tam(reg, slug)

    rows: list[dict[str, str]] = []
    vert_counts: dict[str, dict[str, int]] = {}
    with csv_path.open(encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for parts in reader:
            if not parts or not parts[0].strip():
                continue
            name = parts[0].strip()
            website = parts[1].strip() if len(parts) > 1 else ""
            vertical = parts[2].strip() if len(parts) > 2 else ""

            concept = None
            candidates = VERTICAL_TO_CONCEPTS.get(_normalize_vertical(vertical), [])
            for cand in candidates:
                if cand in reg.concepts:
                    concept = cand
                    break

            coverage = "vertical-map" if concept else "uncovered"
            tam, lens = tam_cache.get(concept, (None, None)) if concept else (None, None)

            rows.append(
                {
                    "name": name,
                    "website": website,
                    "vertical": vertical,
                    "market_concept": concept or "",
                    "market_tam_usd": f"{tam:.0f}" if tam else "",
                    "lens": lens or "",
                    "coverage": coverage,
                }
            )
            bucket = vert_counts.setdefault(
                vertical or "(untagged)", {"covered": 0, "uncovered": 0}
            )
            bucket["covered" if concept else "uncovered"] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    covered = sum(1 for r in rows if r["coverage"] == "vertical-map")
    print(
        f"# {total} companies → {covered} mapped to a sourced market "
        f"({100 * covered // total}%), {total - covered} uncovered\n"
    )
    print(f"{'vertical':28s} {'covered':>8s} {'uncovered':>10s}")
    for v, c in sorted(
        vert_counts.items(), key=lambda kv: -(kv[1]["covered"] + kv[1]["uncovered"])
    ):
        print(f"{v:28s} {c['covered']:>8d} {c['uncovered']:>10d}")
    print(f"\n# wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
