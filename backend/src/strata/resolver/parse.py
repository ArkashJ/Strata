"""Claude-driven query parsing — lifted from api/routes/resolve.py.

Extracts ``lens``, ``concept_name``, ``definition``, and a list of
``primitives_needed`` (each with a role / description / Exa-optimised
search query / expected unit).

Pure unit; no I/O beyond the LLM layer. The HTTP layer wraps
it in ``asyncio.to_thread`` (it does blocking I/O).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import llm as _llm


class ParsedPrimitive(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    description: str
    search_query: str
    expected_unit: dict[str, Any] = Field(default_factory=dict[str, Any])
    expected_currency: str | None = None


class ParsedQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lens: str
    concept_name: str
    definition: str
    primitives_needed: list[ParsedPrimitive] = Field(default_factory=list[ParsedPrimitive])


def _strip_code_fence(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text.strip())


def parse_query(query: str, *, model: str = "claude-sonnet-4-6") -> ParsedQuery:
    """Single LLM call to parse a free-form market query into ParsedQuery.

    Errors from the LLM layer bubble up; the caller decides how to surface
    them (HTTP path emits an SSE error event, CLI returns exit code 3).
    """
    prompt = f"""Parse this market-sizing query into structured parameters.

Query: "{query}"

Return JSON with:
- lens: one of cost_efficiency, revenue_generation, latent_demand, platform_throughput, bundle_consolidation, productivity_uplift
- concept_name: human-readable market name (e.g. "AI-assisted code review tooling")
- definition: 2-3 sentence market definition
- primitives_needed: array of exactly 2 objects, each with:
  - role: a snake_case role name (e.g. "persona_count", "cost_per_persona")
  - description: what to search for (e.g. "number of US software developers")
  - search_query: an Exa-optimized search query to find this data
  - expected_unit: object with kind (stock/flow/intensive/dimensionless) and dimension (people/currency/organizations/percent)
  - expected_currency: "USD" if dimension is currency, null otherwise

Return ONLY valid JSON, no markdown."""

    text = _llm.complete(prompt, model=model, max_tokens=1024)
    text = _strip_code_fence(text)
    raw: dict[str, Any] = json.loads(text)
    return ParsedQuery.model_validate(raw)
