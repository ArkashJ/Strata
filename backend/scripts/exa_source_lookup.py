"""
exa_source_lookup.py — find real source data for Strata seed primitives via Exa deep search.

Run from backend/:
    uv run python scripts/exa_source_lookup.py

Outputs a structured report per primitive and a JSON summary of corrections needed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from exa_py import Exa

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Research queries — one per primitive slug
# ---------------------------------------------------------------------------
QUERIES: list[dict] = [
    # --- P&C Insurance vertical ---
    {
        "primitive_slug": "bls-pc-claims-adjusters-headcount",
        "query": "BLS OES 13-1031 claims adjusters examiners investigators employment 2024 total US headcount",
        "expected_value": 322_500,
        "unit_hint": "headcount (persons)",
        "source_domains": ["bls.gov"],
    },
    {
        "primitive_slug": "naic-active-pc-carriers-2024",
        "query": "NAIC active property casualty insurance carriers US 2024 total count licensed companies",
        "expected_value": 2_541,
        "unit_hint": "count (companies)",
        "source_domains": ["naic.org"],
    },
    {
        "primitive_slug": "pc-claims-adjuster-cost-per-seat",
        "query": "claims adjuster software SaaS cost per seat annual pricing 2024 insurance technology",
        "expected_value": 480,
        "unit_hint": "USD/seat/year",
        "source_domains": [],
    },
    {
        "primitive_slug": "pc-saas-spend-per-carrier-2024",
        "query": "property casualty insurance carrier annual IT software spend per company 2024 technology budget",
        "expected_value": 185_000,
        "unit_hint": "USD/carrier/year",
        "source_domains": [],
    },
    {
        "primitive_slug": "pc-premium-volume-digital-us-2024",
        "query": "US property casualty insurance total written premium volume 2024 annual dollars",
        "expected_value": 500_000_000_000,
        "unit_hint": "USD total",
        "source_domains": ["naic.org", "iii.org"],
    },
    {
        "primitive_slug": "payment-processing-take-rate-2024",
        "query": "insurance premium payment processing take rate fee percentage 2024 digital payments",
        "expected_value": 0.002,
        "unit_hint": "fraction (e.g. 0.002 = 0.2%)",
        "source_domains": [],
    },
    # --- GTM Ops / Sales vertical ---
    {
        "primitive_slug": "bls-sales-reps-headcount-2024",
        "query": "BLS OES 41-3091 sales representatives wholesale manufacturing employment 2024 total US headcount",
        "expected_value": 4_600_000,
        "unit_hint": "headcount (persons)",
        "source_domains": ["bls.gov"],
    },
    {
        "primitive_slug": "gtm-ops-tool-cost-per-rep-2024",
        "query": "GTM sales operations software tool cost per sales rep annual 2024 CRM sequencer pricing",
        "expected_value": 1_440,
        "unit_hint": "USD/rep/year",
        "source_domains": [],
    },
    # --- Midmarket SaaS vertical ---
    {
        "primitive_slug": "census-midmarket-companies-na-2024",
        "query": "US Census Bureau business statistics companies 100 to 999 employees 2024 total count North America",
        "expected_value": 200_000,
        "unit_hint": "count (companies)",
        "source_domains": ["census.gov"],
    },
    {
        "primitive_slug": "avg-saas-spend-midmarket-2024",
        "query": "average SaaS software spend midmarket company 100-999 employees 2024 annual IT budget",
        "expected_value": 420_000,
        "unit_hint": "USD/company/year",
        "source_domains": [],
    },
    # --- Software engineering productivity vertical ---
    {
        "primitive_slug": "bls-software-developers-us-2024",
        "query": "BLS OES 15-1252 software developers quality assurance analysts testers employment 2024 total US",
        "expected_value": 4_400_000,
        "unit_hint": "headcount (persons)",
        "source_domains": ["bls.gov"],
    },
    {
        "primitive_slug": "dev-tool-arpu-2024",
        "query": "developer tool software ARPU average revenue per user annual 2024 devtools SaaS pricing",
        "expected_value": 1_800,
        "unit_hint": "USD/developer/year",
        "source_domains": [],
    },
    # --- Workplace suite consolidation vertical ---
    {
        "primitive_slug": "enterprise-workplace-point-solution-spend-2024",
        "query": "enterprise workplace software total point solution spend 2024 HR productivity collaboration tools market size",
        "expected_value": 85_000_000_000,
        "unit_hint": "USD total",
        "source_domains": [],
    },
    {
        "primitive_slug": "consolidation-capture-rate-2024",
        "query": "enterprise software consolidation rate percentage companies consolidating point solutions suite 2024",
        "expected_value": 0.15,
        "unit_hint": "fraction (e.g. 0.15 = 15%)",
        "source_domains": [],
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOLERANCE = 0.15  # 15% tolerance before flagging as "differs"


def fmt_val(v: float | int) -> str:
    """Human-readable number formatting."""
    if isinstance(v, float) and v < 1:
        return f"{v:.4f} ({v * 100:.2f}%)"
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B ({v:,.0f})"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M ({v:,.0f})"
    if v >= 1_000:
        return f"{v:,.0f}"
    return str(v)


def extract_numbers_from_highlights(highlights: list[str]) -> list[float]:
    """Very light heuristic: pull bare integers/floats out of highlight text."""
    import re

    numbers: list[float] = []
    for h in highlights:
        # Strip commas from numbers like 295,630
        cleaned = h.replace(",", "")
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", cleaned):
            numbers.append(float(match.group(1)))
    return numbers


def verdict(expected: float | int, highlights: list[str]) -> str:
    nums = extract_numbers_from_highlights(highlights)
    if not nums:
        return "VERDICT: No numeric data extracted — manual review required."
    # Find the number closest to expected
    closest = min(nums, key=lambda n: abs(n - expected) / max(expected, 1))
    pct_diff = abs(closest - expected) / max(abs(expected), 1)
    if pct_diff <= TOLERANCE:
        return f"VERDICT: Value consistent — closest match {fmt_val(closest)} vs expected {fmt_val(expected)} ({pct_diff * 100:.1f}% diff). NO CHANGE needed."
    else:
        return f"VERDICT: Value differs — found {fmt_val(closest)} vs expected {fmt_val(expected)} ({pct_diff * 100:.1f}% diff). UPDATE RECOMMENDED."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        raise RuntimeError("EXA_API_KEY not set — check .env at repo root")

    exa = Exa(api_key=api_key)

    corrections: list[dict] = []

    print("=" * 70)
    print("Strata Primitive Source Lookup — Exa Deep Search")
    print(f"Checking {len(QUERIES)} primitives")
    print("=" * 70)
    print()

    for i, q in enumerate(QUERIES, 1):
        slug = q["primitive_slug"]
        query_text = q["query"]
        expected = q["expected_value"]
        domains = q.get("source_domains", [])

        print(f"[{i}/{len(QUERIES)}] Searching: {slug}")

        try:
            kwargs: dict = {
                "type": "deep",
                "num_results": 5,
                "contents": {"highlights": True},
            }
            if domains:
                kwargs["include_domains"] = domains

            results = exa.search(query_text, **kwargs)

            print(f"\n{'=' * 70}")
            print(f"=== {slug} ===")
            print(f"Expected: {fmt_val(expected)}  [{q['unit_hint']}]")
            print(f"Query: {query_text[:80]}...")
            print("Sources found:")

            all_highlights: list[str] = []

            if not results.results:
                print("  (no results returned)")
            else:
                for j, r in enumerate(results.results, 1):
                    domain = r.url.split("/")[2] if r.url else "unknown"
                    title = (r.title or "")[:80]
                    print(f"\n  {j}. [{domain}] {title}")
                    print(f"     URL: {r.url}")
                    hi = getattr(r, "highlights", None) or []
                    if hi:
                        for h in hi[:3]:  # top 3 highlights per result
                            short = h[:200].replace("\n", " ")
                            print(f'     Highlight: "{short}"')
                            all_highlights.append(h)
                    else:
                        print("     (no highlights)")

            v = verdict(expected, all_highlights)
            print(f"\n{v}")
            print()

            # Record corrections
            needs_update = "UPDATE RECOMMENDED" in v or "manual review" in v
            corrections.append(
                {
                    "slug": slug,
                    "expected_value": expected,
                    "unit_hint": q["unit_hint"],
                    "verdict": v,
                    "needs_update": needs_update,
                    "top_urls": [r.url for r in (results.results or [])[:3]],
                }
            )

        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            corrections.append(
                {
                    "slug": slug,
                    "expected_value": expected,
                    "unit_hint": q["unit_hint"],
                    "verdict": f"ERROR: {exc}",
                    "needs_update": None,
                    "top_urls": [],
                }
            )

        # Rate-limit courtesy pause (skip after last item)
        if i < len(QUERIES):
            time.sleep(1)

    # ---------------------------------------------------------------------------
    # JSON summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("JSON SUMMARY — corrections needed")
    print("=" * 70)

    flagged = [c for c in corrections if c["needs_update"]]
    summary = {
        "total_checked": len(corrections),
        "needs_update": len(flagged),
        "clean": len([c for c in corrections if c["needs_update"] is False]),
        "errors": len([c for c in corrections if c["needs_update"] is None]),
        "flagged": flagged,
        "all": corrections,
    }

    print(json.dumps(summary, indent=2))

    # Write to file next to the script
    out_path = Path(__file__).parent / "exa_lookup_results.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
