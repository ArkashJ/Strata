"""Dynamic TAM query resolution via LLM + Exa search.

POST /resolve accepts a natural language market query and streams
back SSE events as it parses, searches, and evaluates.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import cast

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv
from exa_py import Exa
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["resolve"])

# Load .env from repo root for EXA_API_KEY
load_dotenv(Path(__file__).parent.parent.parent.parent.parent.parent / ".env")

FRAMEWORK_TEMPLATES: dict[str, dict[str, str]] = {
    "cost_efficiency": {"name": "Bottoms-up cost efficiency", "formula": "persona_pool x cost_per_persona"},
    "revenue_generation": {"name": "Top-down revenue capture", "formula": "target_segment x spend_per_target"},
    "latent_demand": {"name": "Adoption curve latent demand", "formula": "addressable_population x adoption_value"},
    "platform_throughput": {"name": "Throughput take-rate", "formula": "volume x take_rate"},
    "bundle_consolidation": {"name": "Consolidation sum-then-discount", "formula": "total_spend x consolidation_rate"},
    "productivity_uplift": {"name": "Productivity uplift value-split", "formula": "persona_count x value_per_persona"},
}


class ResolveRequest(BaseModel):
    query: str


def _sse(event: str, data: dict[str, object] | str) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def _format_usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _select_framework(lens: str) -> dict[str, str]:
    return FRAMEWORK_TEMPLATES.get(lens, FRAMEWORK_TEMPLATES["cost_efficiency"])


def _parse_query_with_claude(query: str) -> dict[str, object]:
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY from env

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Parse this market-sizing query into structured parameters.

Query: "{query}"

Return JSON with:
- lens: one of cost_efficiency, revenue_generation, latent_demand, platform_throughput, bundle_consolidation, productivity_uplift
- concept_name: human-readable market name (e.g. "AI-assisted code review tooling")
- definition: 2-3 sentence market definition
- primitives_needed: array of exactly 2 objects, each with:
  - role: a snake_case role name (e.g. "persona_count", "cost_per_persona")
  - description: what to search for (e.g. "number of US software developers")
  - search_query: an Exa-optimized search query to find this data (e.g. "BLS OES software developers employment 2024 total US headcount")
  - expected_unit: object with kind (stock/flow/intensive/dimensionless) and dimension (people/currency/organizations/percent)
  - expected_currency: "USD" if dimension is currency, null otherwise

Return ONLY valid JSON, no markdown.""",
            }
        ],
    )

    block = response.content[0]
    assert isinstance(block, TextBlock), f"unexpected content block type: {type(block)}"
    text: str = block.text
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)  # type: ignore[no-any-return]


def _search_primitive_with_exa(prim_spec: dict[str, object]) -> dict[str, object] | None:
    exa = Exa(api_key=os.environ.get("EXA_API_KEY"))

    try:
        results = exa.search(
            str(prim_spec["search_query"]),
            type="auto",
            num_results=5,
            contents={"highlights": True},
        )

        if not results.results:
            return None

        # Use Claude to extract the number from highlights
        highlights_text = ""
        top_url = results.results[0].url
        for r in results.results[:3]:
            if r.highlights:
                for h in r.highlights:
                    highlights_text += f"[{r.title}] {h}\n"

        if not highlights_text:
            return None

        # Ask Claude to extract the number
        client = anthropic.Anthropic()
        extract = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": f"""From these search results, extract the single most relevant numeric value for: {prim_spec['description']}

Search results:
{highlights_text}

Return ONLY JSON: {{"value": <number>, "name": "<source description>", "source_url": "<best URL>", "source_tier": "<regulator|analyst|aggregator|community>"}}

The value should be a raw number (e.g. 2183300 not "2.18M"). If the data is about money, give the annual USD amount. If it's a percentage/rate, give the decimal (e.g. 0.15 for 15%).
Return ONLY valid JSON.""",
                }
            ],
        )

        extract_block = extract.content[0]
        assert isinstance(extract_block, TextBlock), f"unexpected content block type: {type(extract_block)}"
        exa_text: str = extract_block.text
        exa_text = re.sub(r"^```(?:json)?\s*", "", exa_text.strip())
        exa_text = re.sub(r"\s*```$", "", exa_text.strip())
        extracted: dict[str, object] = json.loads(exa_text)

        return {
            "role": prim_spec["role"],
            "name": extracted.get("name", prim_spec["description"]),
            "value": float(extracted["value"]),  # type: ignore[arg-type]
            "unit": prim_spec.get("expected_unit", {"kind": "stock", "dimension": "people"}),
            "source_url": extracted.get("source_url", top_url),
            "source_tier": extracted.get("source_tier", "community"),
        }

    except Exception:
        return None


@router.post("/resolve")
async def resolve_query(body: ResolveRequest) -> StreamingResponse:
    async def generate():  # type: ignore[return]
        try:
            # Step 1: Parse query with Claude
            yield _sse("step", {"type": "parsing", "message": f'Parsing: "{body.query}"...'})

            parsed = _parse_query_with_claude(body.query)
            yield _sse(
                "step",
                {
                    "type": "parsed",
                    "lens": parsed["lens"],
                    "concept_name": parsed["concept_name"],
                    "definition": parsed["definition"],
                    "primitives_needed": parsed["primitives_needed"],
                },
            )

            # Step 2: Search for each primitive with Exa
            found_primitives: list[dict[str, object]] = []
            primitives_needed = parsed.get("primitives_needed", [])
            if not isinstance(primitives_needed, list):
                primitives_needed = []

            for prim_spec_raw in primitives_needed:
                if not isinstance(prim_spec_raw, dict):
                    continue
                prim_spec = cast(dict[str, object], prim_spec_raw)
                yield _sse(
                    "step",
                    {
                        "type": "searching",
                        "role": prim_spec["role"],
                        "message": f"Searching for {prim_spec['description']}...",
                    },
                )

                result = _search_primitive_with_exa(prim_spec)
                if result:
                    found_primitives.append(result)
                    yield _sse(
                        "step",
                        {
                            "type": "primitive_found",
                            "role": result["role"],
                            "name": result["name"],
                            "value": result["value"],
                            "unit": result["unit"],
                            "source_url": result["source_url"],
                            "source_tier": result.get("source_tier", "community"),
                        },
                    )

            if len(found_primitives) < 2:
                yield _sse("error", {"message": "Could not find enough market data for this query."})
                yield _sse("done", {})
                return

            # Step 3: Select framework
            lens = str(parsed["lens"])
            framework_info = _select_framework(lens)
            yield _sse(
                "step",
                {
                    "type": "framework_selected",
                    "name": framework_info["name"],
                    "lens": lens,
                    "formula": framework_info["formula"],
                },
            )

            # Step 4: Evaluate TAM
            yield _sse("step", {"type": "evaluating", "message": "Computing TAM scenarios..."})

            tam_value = 1.0
            for p in found_primitives:
                tam_value *= float(p["value"])  # type: ignore[arg-type]

            yield _sse(
                "result",
                {
                    "concept_name": parsed["concept_name"],
                    "definition": parsed["definition"],
                    "tam_value": tam_value,
                    "formatted_tam": _format_usd(tam_value),
                    "lens": lens,
                    "framework_name": framework_info["name"],
                    "independence_score": 0.0,
                    "primitives_used": found_primitives,
                },
            )

            yield _sse("done", {})

        except Exception as e:
            yield _sse("error", {"message": str(e)})
            yield _sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
