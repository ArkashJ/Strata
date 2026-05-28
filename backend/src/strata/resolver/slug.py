"""Slug resolution — audit fix A+B.

A single Claude call that maps a free-form query to known registry slugs
OR declares the query novel. The output ``ResolvedQuery`` is *carried*
through the rest of the pipeline so we never re-parse the same query
twice in one invocation.

Prompt is dominated by the registry index (concepts + primitives). Sent
with ``cache_control: ephemeral`` on the index block so back-to-back
queries within ~5 min hit Anthropic's prompt cache.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Any

from anthropic.types import TextBlock
from pydantic import BaseModel, ConfigDict, Field

from .parse import get_anthropic_client


class ResolverIntent(StrEnum):
    CONCEPT = "concept"
    PRIMITIVE = "primitive"
    NOVEL = "novel"


class ConceptSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    name: str
    one_line_description: str


class PrimitiveSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    name: str
    one_line_description: str


class ResolvedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: ResolverIntent
    concept_slug: str | None = None
    primitive_slugs: list[str] = Field(default_factory=list[str])
    framework_hint: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


def _strip_code_fence(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text.strip())


def _build_registry_block(
    concepts: list[ConceptSummary],
    primitives: list[PrimitiveSummary],
) -> str:
    concept_lines = [
        f"  {{slug: {c.slug!r}, name: {c.name!r}, desc: {c.one_line_description!r}}}"
        for c in concepts
    ]
    primitive_lines = [
        f"  {{slug: {p.slug!r}, name: {p.name!r}, desc: {p.one_line_description!r}}}"
        for p in primitives
    ]
    return (
        "REGISTRY INDEX\n\nConcepts:\n["
        + ",\n".join(concept_lines)
        + "\n]\n\nPrimitives:\n["
        + ",\n".join(primitive_lines)
        + "\n]"
    )


def resolve_slug(
    query: str,
    *,
    known_concepts: list[ConceptSummary],
    known_primitives: list[PrimitiveSummary],
    model: str = "claude-sonnet-4-6",
) -> ResolvedQuery:
    """Single Claude one-shot mapping a free-form query to ResolvedQuery."""

    client = get_anthropic_client()
    registry_block = _build_registry_block(known_concepts, known_primitives)

    instruction = (
        f"User query: {query!r}\n\n"
        "Decide which path the resolver should take. Return JSON with:\n"
        "- intent: 'concept' (one registry concept matches), 'primitive' "
        "(one or more registry primitives match), or 'novel' (neither)\n"
        "- concept_slug: string or null\n"
        "- primitive_slugs: list of strings (may be empty)\n"
        "- framework_hint: one of "
        "cost_efficiency, revenue_generation, latent_demand, "
        "platform_throughput, bundle_consolidation, productivity_uplift, or null\n"
        "- confidence: float in [0,1]\n\n"
        "Return ONLY JSON, no markdown."
    )

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": registry_block,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": instruction}],
    )

    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise ValueError("Expected text response from Claude")
    raw: dict[str, Any] = json.loads(_strip_code_fence(block.text))
    return ResolvedQuery.model_validate(raw)
