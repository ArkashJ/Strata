#!/usr/bin/env python3
"""Push Strata API keys from the repo-root .env to the Railway prod backend.

Robust against awkward .env values (spaces, parens, quotes) — it parses with
python-dotenv and shells out to `railway` with list args (no shell splitting).
Only non-empty values are pushed. Connector keys go up STRATA_-prefixed
(prod config uses pydantic env_prefix="STRATA_"); EXA/ANTHROPIC stay bare.

Run it yourself (the assistant is gated from prod secret writes):
    cd backend && uv run python ../scripts/push_railway_keys.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
SERVICE = "strata-api"

# Railway var name -> .env source name(s) to try, in order.
BARE = ["EXA_API_KEY", "ANTHROPIC_API_KEY"]
# These get the STRATA_ prefix on Railway; value taken from STRATA_<X> or bare <X>.
PREFIXED = [
    "BLS_API_KEY",
    "FRED_API_KEY",
    "CENSUS_API_KEY",
    "EIA_API_KEY",
    "USDA_NASS_API_KEY",
    "OPENFDA_API_KEY",
    "COMTRADE_API_KEY",
    "KALSHI_API_KEY",
    "SEC_API_KEY",
    "SEC_USER_AGENT",
    "ALPHA_VANTAGE_API_KEY",
    "NASDAQ_DATA_LINK_API_KEY",
    "DUNE_API_KEY",
    "POLYMARKET_API_KEY",
    "METACULUS_API_TOKEN",
    "MANIFOLD_API_KEY",
    "CRUNCHBASE_API_KEY",
    "OPENCORPORATES_API_KEY",
    "TAVILY_API_KEY",
    "SERPER_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "PERPLEXITY_API_KEY",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USER_AGENT",
    "GITHUB_TOKEN",
    "STACK_EXCHANGE_KEY",
    "TWITTER_BEARER_TOKEN",
    "PRODUCTHUNT_CLIENT_ID",
    "PRODUCTHUNT_CLIENT_SECRET",
    "PRODUCTHUNT_DEV_TOKEN",
    "COINGECKO_API_KEY",
    "ETHERSCAN_API_KEY",
]


def main() -> int:
    if not ROOT_ENV.exists():
        print(f"!! {ROOT_ENV} not found", file=sys.stderr)
        return 1
    env = {k: (v or "").strip() for k, v in dotenv_values(ROOT_ENV).items()}

    sets: list[str] = []
    set_names: list[str] = []
    skipped: list[str] = []

    for name in BARE:
        val = env.get(name, "")
        if val:
            sets.append(f"{name}={val}")
            set_names.append(name)
        else:
            skipped.append(name)

    for x in PREFIXED:
        val = env.get(f"STRATA_{x}", "") or env.get(x, "")
        target = f"STRATA_{x}"
        if val:
            sets.append(f"{target}={val}")
            set_names.append(target)
        else:
            skipped.append(target)

    if not sets:
        print("!! nothing to push (all values empty)", file=sys.stderr)
        return 1

    cmd = ["railway", "variables", "--service", SERVICE]
    for kv in sets:
        cmd += ["--set", kv]

    print(f"Pushing {len(set_names)} vars to Railway service '{SERVICE}':")
    for n in set_names:
        print(f"  set    {n}")
    for n in skipped:
        print(f"  skip   {n} (empty in .env)")
    print()

    result = subprocess.run(cmd)  # noqa: S603 — values never printed
    if result.returncode == 0:
        print(f"\nOK — {len(set_names)} variables set; Railway will redeploy.")
    else:
        print(f"\n!! railway exited {result.returncode}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
