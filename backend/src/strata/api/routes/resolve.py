"""Dynamic TAM query resolution via LLM + Exa search.

POST /resolve accepts a natural language market query and streams
back SSE events as it parses, searches, and evaluates.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import cast

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv
from exa_py import Exa
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["resolve"])

# Load .env — walks up directory tree automatically
load_dotenv()

FRAMEWORK_TEMPLATES: dict[str, dict[str, str]] = {
    "cost_efficiency": {"name": "Bottoms-up cost efficiency", "formula": "persona_pool x cost_per_persona"},
    "revenue_generation": {"name": "Top-down revenue capture", "formula": "target_segment x spend_per_target"},
    "latent_demand": {"name": "Adoption curve latent demand", "formula": "addressable_population x adoption_value"},
    "platform_throughput": {"name": "Throughput take-rate", "formula": "volume x take_rate"},
    "bundle_consolidation": {"name": "Consolidation sum-then-discount", "formula": "total_spend x consolidation_rate"},
    "productivity_uplift": {"name": "Productivity uplift value-split", "formula": "persona_count x value_per_persona"},
}

# Module-level lazy singletons — avoid re-creating clients on every call
_anthropic_client: anthropic.Anthropic | None = None
_exa_client: Exa | None = None


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_exa() -> Exa:
    global _exa_client
    if _exa_client is None:
        _exa_client = Exa(api_key=os.environ.get("EXA_API_KEY"))
    return _exa_client


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
    client = _get_anthropic()

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
    if not isinstance(block, TextBlock):
        raise ValueError("Expected text response from Claude")
    text: str = block.text
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)  # type: ignore[no-any-return]


def _search_primitive_with_exa(prim_spec: dict[str, object]) -> dict[str, object] | None:
    exa = _get_exa()

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
        client = _get_anthropic()
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
        if not isinstance(extract_block, TextBlock):
            raise ValueError("Expected text response from Claude")
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

    except json.JSONDecodeError:
        logging.getLogger(__name__).warning(
            "Failed to parse extraction result for %s", prim_spec.get("role", "unknown")
        )
        return None
    except Exception:
        logging.getLogger(__name__).warning(
            "Exa search failed for %s", prim_spec.get("role", "unknown"), exc_info=True
        )
        return None


@router.post("/resolve")
async def resolve_query(body: ResolveRequest) -> StreamingResponse:
    async def generate():  # type: ignore[return]
        try:
            # Step 1: Parse query with Claude
            yield _sse("step", {"type": "parsing", "message": f'Parsing: "{body.query}"...'})

            parsed = await asyncio.to_thread(_parse_query_with_claude, body.query)

            try:
                # Validate parsed is a dict (json.loads already ran inside the sync fn,
                # but we guard against it returning something unexpected)
                if not isinstance(parsed, dict):
                    raise ValueError("Unexpected response shape from Claude")
            except Exception:
                yield _sse("error", {"message": "Failed to parse AI response. Please try again."})
                yield _sse("done", {})
                return

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

                result = await asyncio.to_thread(_search_primitive_with_exa, prim_spec)
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

        except Exception:
            logging.getLogger(__name__).exception("resolve failed")
            yield _sse("error", {"message": "An internal error occurred. Please try again."})
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
