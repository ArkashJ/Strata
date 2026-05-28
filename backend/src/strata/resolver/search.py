"""Exa search + Claude extract — lifted from api/routes/resolve.py.

Given a ParsedPrimitive, fetches Exa results, asks Claude to extract the
single most relevant number, and returns a PrimitiveHit (or None).

Errors are swallowed and converted to None per the spec's existing
behavior — the caller decides how to handle "not enough primitives found".
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from anthropic.types import TextBlock
from exa_py import Exa
from pydantic import BaseModel, ConfigDict

from .parse import ParsedPrimitive, get_anthropic_client

_exa_client: Exa | None = None
_log = logging.getLogger(__name__)


def _get_exa() -> Exa:
    global _exa_client
    if _exa_client is None:
        _exa_client = Exa(api_key=os.environ.get("EXA_API_KEY"))
    return _exa_client


class PrimitiveHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    name: str
    value: float
    unit: dict[str, Any]
    source_url: str
    source_tier: str = "community"


def _strip_code_fence(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text.strip())


def search_primitive(
    prim: ParsedPrimitive, *, model: str = "claude-sonnet-4-20250514"
) -> PrimitiveHit | None:
    """Exa search → Claude extract → PrimitiveHit | None."""
    exa = _get_exa()
    try:
        results = exa.search(
            prim.search_query,
            type="auto",
            num_results=5,
            contents={"highlights": True},
        )
        if not results.results:
            return None

        top_url = results.results[0].url
        highlights_text = ""
        for r in results.results[:3]:
            if r.highlights:
                for h in r.highlights:
                    highlights_text += f"[{r.title}] {h}\n"
        if not highlights_text:
            return None

        client = get_anthropic_client()
        extract = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": f"""From these search results, extract the single most relevant numeric value for: {prim.description}

Search results:
{highlights_text}

Return ONLY JSON: {{"value": <number>, "name": "<source description>", "source_url": "<best URL>", "source_tier": "<regulator|analyst|aggregator|community>"}}

The value should be a raw number (e.g. 2183300 not "2.18M"). If money, give annual USD. If percentage, give decimal.""",
                }
            ],
        )
        block = extract.content[0]
        if not isinstance(block, TextBlock):
            raise ValueError("Expected text response from Claude")
        raw: dict[str, Any] = json.loads(_strip_code_fence(block.text))

        return PrimitiveHit(
            role=prim.role,
            name=str(raw.get("name", prim.description)),
            value=float(raw["value"]),
            unit=prim.expected_unit
            if prim.expected_unit
            else {"kind": "stock", "dimension": "people"},
            source_url=str(raw.get("source_url", top_url)),
            source_tier=str(raw.get("source_tier", "community")),
        )
    except json.JSONDecodeError:
        _log.warning("Failed to parse extraction result for %s", prim.role)
        return None
    except Exception:
        _log.warning("Exa search failed for %s", prim.role, exc_info=True)
        return None
