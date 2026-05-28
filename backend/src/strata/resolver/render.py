"""Renderers — turn PipelineEvent / ResolverResult into compact, stream, or JSON output."""

from __future__ import annotations

import json
from enum import StrEnum

from .events import PipelineEvent, PipelineEventKind, ResolverResult


class RenderMode(StrEnum):
    COMPACT = "compact"
    STREAM = "stream"
    JSON = "json"


def render_event(event: PipelineEvent, *, mode: RenderMode) -> str:
    """One line per event in stream mode; empty string for compact (events
    only surface in the terminal result)."""
    if mode is RenderMode.COMPACT:
        return ""
    if mode is RenderMode.JSON:
        return json.dumps({"kind": event.kind.value, "step": event.step, "payload": event.payload})

    step = event.step
    if event.kind is PipelineEventKind.PARSING:
        query = event.payload.get("query", "")
        return f"→ Parsing: {query!r}"
    if event.kind is PipelineEventKind.SLUG_RESOLVED:
        intent = event.payload.get("intent", "?")
        hint = event.payload.get("framework_hint")
        suffix = f", framework_hint={hint}" if hint else ""
        return f"→ Slug resolver: intent={intent}{suffix}"
    if event.kind is PipelineEventKind.CONCEPT_HIT:
        slug = event.payload.get("concept_slug")
        return f"→ Step 1: concept hit → {slug}"
    if event.kind is PipelineEventKind.PRIMITIVE_HIT:
        slug = event.payload.get("slug")
        val = event.payload.get("value")
        return f"→ Step 2: primitive hit → {slug} = {val}"
    if event.kind is PipelineEventKind.ROUTER_DECISION:
        connector = event.payload.get("connector")
        method = event.payload.get("method")
        conf = event.payload.get("confidence")
        return f"→ Step 3: router → {connector}.{method} (conf={conf})"
    if event.kind is PipelineEventKind.CONNECTOR_CALL:
        return f"→ Step 3: calling {event.payload.get('connector')}.{event.payload.get('method')}"
    if event.kind is PipelineEventKind.WROTE_PRIMITIVE:
        return f"→ wrote {event.payload.get('path')}"
    if event.kind is PipelineEventKind.BUDGET_EXCEEDED:
        return f"→ expansion budget exceeded ({event.payload.get('budget')})"
    if event.kind is PipelineEventKind.SEARCHING:
        role = event.payload.get("role") or event.payload.get("primitive_name")
        return f"→ Step 4: searching {role}"
    if event.kind is PipelineEventKind.FRAMEWORK_SELECTED:
        return f"→ Step 4: framework={event.payload.get('framework')}"
    if event.kind is PipelineEventKind.EVALUATING:
        return "→ evaluating..."
    if event.kind is PipelineEventKind.RESULT:
        return "→ done"
    if event.kind is PipelineEventKind.ERROR:
        return f"→ error[{step}]: {event.message or event.payload.get('error')}"
    return ""


def render_result(result: ResolverResult, *, mode: RenderMode) -> str:
    if mode is RenderMode.JSON:
        return json.dumps(result.model_dump(), indent=2, default=str)

    lines: list[str] = []
    if mode is RenderMode.STREAM:
        for ev in result.events:
            line = render_event(ev, mode=RenderMode.STREAM)
            if line:
                lines.append(line)
        lines.append("")

    if result.status.value == "failed":
        lines.append(f"FAILED: {result.error or 'no result'}")
        return "\n".join(lines)

    if result.tam_value is not None:
        lines.append(f"  TAM   point: {result.formatted_tam or result.tam_value}")
    if result.concept_name:
        lines.append(f"  Concept:      {result.concept_name}")
    if result.framework_name:
        lines.append(f"  Framework:    {result.framework_name}")
    if result.primitives_used:
        lines.append("  Inputs:")
        for p in result.primitives_used:
            slug = p.get("slug") or p.get("role") or "—"
            value = p.get("value")
            name = p.get("name", "")
            lines.append(f"    • {slug:32s}  {value}  {name}")
    if result.wrote_primitives:
        lines.append("")
        lines.append(
            f"  Wrote {len(result.wrote_primitives)} auto-primitive(s) to ~/.strata/auto-primitives/."
        )
    if result.banner:
        lines.append("")
        lines.append(f"  ⚑ {result.banner}")
    return "\n".join(lines)
