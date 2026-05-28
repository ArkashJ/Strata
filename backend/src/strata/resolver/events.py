"""Pipeline event + result types shared by HTTP-SSE and CLI surfaces.

The HTTP route serializes these as SSE events (per the §9.1 frozen
contract); the CLI renders them as one-line steps or as a final compact
or JSON block. The internal shape is identical.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineEventKind(StrEnum):
    """Wire-level SSE event names — frozen per spec §9.1 audit fix H.

    DO NOT rename these. The /resolve regression test asserts the exact set;
    any rename here breaks SSE clients.
    """

    PARSING = "parsing"
    SEARCHING = "searching"
    FRAMEWORK_SELECTED = "framework_selected"
    EVALUATING = "evaluating"
    RESULT = "result"
    ERROR = "error"

    # Internal events used by the CLI renderer (not in the §9.1 wire contract;
    # `/resolve` does not emit these to network clients).
    SLUG_RESOLVED = "slug_resolved"
    CONCEPT_HIT = "concept_hit"
    PRIMITIVE_HIT = "primitive_hit"
    ROUTER_DECISION = "router_decision"
    CONNECTOR_CALL = "connector_call"
    WROTE_PRIMITIVE = "wrote_primitive"
    BUDGET_EXCEEDED = "budget_exceeded"


class PipelineStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class PipelineEvent(BaseModel):
    """One step in the pipeline trace."""

    model_config = ConfigDict(extra="forbid")

    kind: PipelineEventKind
    step: Literal["pre", "1", "2", "3", "4"]
    payload: dict[str, Any] = Field(default_factory=dict[str, Any])
    message: str | None = None


class ResolverResult(BaseModel):
    """The terminal value the renderer turns into compact / stream / JSON output."""

    model_config = ConfigDict(extra="forbid")

    status: PipelineStatus
    via: Literal["concept", "primitive", "connector", "fallback", "none"]
    tam_value: float | None = None
    formatted_tam: str | None = None
    concept_name: str | None = None
    definition: str | None = None
    lens: str | None = None
    framework_name: str | None = None
    independence_score: float = 0.0
    primitives_used: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    wrote_primitives: list[str] = Field(default_factory=list[str])
    events: list[PipelineEvent] = Field(default_factory=list[PipelineEvent])
    banner: str | None = None
    error: str | None = None
