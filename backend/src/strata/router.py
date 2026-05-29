"""Manifest + LLM router (spec §6).

Single Claude call that takes a free-form query plus the union of all
connector capability specs and returns a routing decision (or None).

The manifest block is serialized into the system prompt and the call is
routed through ``resolver.llm.complete`` (backend switch + ANTHROPIC_API_KEY
env scrub). NOTE: the SDK-only ``cache_control: ephemeral`` optimisation
(spec §6.1, audit fix E) that amortised the ~21K-token manifest across
back-to-back ``goal`` invocations is NOT applied on this path — correctness
(works off the Claude Code subscription, no funded key) over the prompt
cache; restoring cache_control via ``llm.complete`` is a follow-up.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .connectors import all_capabilities
from .connectors._capability import CapabilitySpec
from .resolver import llm as _llm

_log = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    """One connector method the router has decided to call."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    method: str
    args: dict[str, str | int | float | bool] = Field(
        default_factory=dict[str, str | int | float | bool]
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


_MIN_CONFIDENCE = 0.5


def _strip_code_fence(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text.strip())


def _serialize_manifest(specs: list[CapabilitySpec]) -> str:
    """Render manifest as compact JSON. Demoted entries get a flag the LLM
    can read in the prompt instructions.
    """
    payload = [spec.model_dump() for spec in specs]
    return json.dumps(payload, indent=None, separators=(",", ":"))


def choose(
    query: str,
    manifests: list[CapabilitySpec] | None = None,
    *,
    model: str = "claude-sonnet-4-6",
    min_confidence: float = _MIN_CONFIDENCE,
    allow_fragile: bool = False,
    allow_paid: bool = False,
) -> RoutingDecision | None:
    """Choose one connector method for the query, or None.

    The manifest is sent as a cached system block; the user message is just
    the query + the strict JSON-out instruction. Returns ``None`` when
    confidence is below ``min_confidence`` or the LLM declines.
    """

    specs = manifests if manifests is not None else all_capabilities()
    if not specs:
        return None

    # Filter out demoted specs *before* serialising the manifest unless the
    # caller explicitly opted into them.
    candidates = [
        s
        for s in specs
        if (allow_fragile or not s.is_fragile) and (allow_paid or not s.requires_paid_tier)
    ]
    if not candidates:
        return None

    manifest_block = _serialize_manifest(candidates)

    user_msg = (
        f"User query: {query!r}\n\n"
        "Choose the single most appropriate connector method from the manifest, "
        'or return {"connector": null} if none fit.\n'
        'Output strict JSON: {"connector": <str|null>, "method": <str>, '
        '"args": <obj>, "confidence": <float 0..1>, "rationale": <str>}.\n'
        "Pick exactly one. Do not invent methods that are not in the manifest. "
        "Args must satisfy the spec's args contract.\n"
        "Return ONLY JSON, no markdown."
    )

    # Route through the shared LLM layer so connector routing works off the same
    # backend (subscription CLI by default; SDK on STRATA_LLM_BACKEND=anthropic)
    # and ANTHROPIC_API_KEY env scrub as the rest of the resolver. NOTE: this
    # drops the SDK-only cache_control on the ~21K-token manifest block —
    # correctness (works without a funded key) over the prompt-cache
    # optimisation; restoring cache_control via llm.complete is a follow-up.
    raw_text = _llm.complete(
        user_msg, system="CAPABILITY MANIFEST:\n" + manifest_block, model=model, max_tokens=512
    )
    try:
        raw: dict[str, Any] = json.loads(_strip_code_fence(raw_text))
    except json.JSONDecodeError:
        _log.warning("router returned non-JSON: %r", raw_text[:200])
        return None

    if not raw.get("connector"):
        return None
    try:
        decision = RoutingDecision.model_validate(raw)
    except Exception:
        _log.warning("router output failed validation: %r", raw)
        return None
    if decision.confidence < min_confidence:
        return None
    return decision
