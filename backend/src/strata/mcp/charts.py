"""Pure chart-spec builders from a TAM (Phase 5, backend half).

These turn an already-computed :class:`TAMOutput` into portable visualization
specs so a host that can render Vega-Lite / Mermaid (claude.ai, Claude Code) gets
a chart, not just numbers. They are **pure**: every value comes off the TAM's
sourced scenarios — no number is invented, nothing is fetched.

* Vega-Lite: ``tornado`` (per-input ± swing), ``composition`` (a scenario's
  inputs), ``scenario_comparison`` (value per method/framework), ``source_mix``
  (count by source tier), ``penetration`` (placeholder honest-gap — no sourced
  adoption curve yet).
* Mermaid: ``scenario_tree`` (concept → frameworks → values),
  ``lineage`` (scenario → its sourced inputs).

The web report components (a separate PR) render the same data richly; these
specs cover hosts that would otherwise show nothing.
"""

from __future__ import annotations

from typing import Any

from ..models.tam_output import TAMOutput

_VL_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

VEGA_KINDS = ("tornado", "composition", "scenario_comparison", "source_mix", "penetration")
MERMAID_KINDS = ("scenario_tree", "lineage")
ALL_KINDS = (*VEGA_KINDS, *MERMAID_KINDS)


def _scenario_comparison(tam: TAMOutput) -> dict[str, Any]:
    rows = [{"method": s.framework_variant or s.framework, "value": s.value} for s in tam.scenarios]
    return {
        "$schema": _VL_SCHEMA,
        "title": f"Method comparison — {tam.target.concept_name or tam.target.concept}",
        "data": {"values": rows},
        "mark": "bar",
        "encoding": {
            "y": {"field": "method", "type": "nominal", "sort": "-x"},
            "x": {"field": "value", "type": "quantitative", "title": "TAM value"},
        },
    }


def _composition(tam: TAMOutput) -> dict[str, Any]:
    # The first (representative) scenario's sourced inputs.
    sc = tam.scenarios[0]
    rows = [
        {"input": iu.name or iu.primitive_slug, "value": iu.value}
        for iu in sc.inputs_used
        if iu.value is not None
    ]
    return {
        "$schema": _VL_SCHEMA,
        "title": f"Composition — {sc.framework_variant or sc.framework}",
        "data": {"values": rows},
        "mark": "bar",
        "encoding": {
            "x": {"field": "input", "type": "nominal", "sort": "-y"},
            "y": {"field": "value", "type": "quantitative"},
        },
    }


def _source_mix(tam: TAMOutput) -> dict[str, Any]:
    by_tier: dict[str, int] = {}
    for sc in tam.scenarios:
        for iu in sc.inputs_used:
            tier = iu.source_tier or "unknown"
            by_tier[tier] = by_tier.get(tier, 0) + 1
    rows = [{"tier": t, "count": n} for t, n in sorted(by_tier.items())]
    return {
        "$schema": _VL_SCHEMA,
        "title": "Source-tier mix",
        "data": {"values": rows},
        "mark": "arc",
        "encoding": {
            "theta": {"field": "count", "type": "quantitative"},
            "color": {"field": "tier", "type": "nominal"},
        },
    }


def _tornado(tam: TAMOutput) -> dict[str, Any]:
    # A lightweight tornado proxy off the scenario tree: each unique sourced input
    # as a bar of its value. The full ±pct sensitivity is GET /build/{slug}/
    # sensitivity (needs re-evaluation); this spec is the pure, TAM-only view.
    seen: dict[str, float] = {}
    for sc in tam.scenarios:
        for iu in sc.inputs_used:
            if iu.value is not None and iu.primitive_slug not in seen:
                seen[iu.primitive_slug] = iu.value
    rows = [{"input": k, "value": v} for k, v in seen.items()]
    rows.sort(key=lambda r: abs(float(r["value"])), reverse=True)
    return {
        "$schema": _VL_SCHEMA,
        "title": "Input magnitudes (tornado)",
        "data": {"values": rows},
        "mark": "bar",
        "encoding": {
            "y": {"field": "input", "type": "nominal", "sort": "-x"},
            "x": {"field": "value", "type": "quantitative"},
        },
    }


def _penetration(tam: TAMOutput) -> dict[str, Any]:
    # Honest gap: Strata has no sourced adoption/CAGR curve primitives yet, so the
    # penetration spec is an explicit empty chart with a note, never a fabricated
    # S-curve (Q20).
    return {
        "$schema": _VL_SCHEMA,
        "title": "Penetration over time (no sourced adoption series)",
        "description": "No dated adoption/CAGR primitives are sourced for this concept yet.",
        "data": {"values": []},
        "mark": "line",
        "encoding": {
            "x": {"field": "year", "type": "temporal"},
            "y": {"field": "penetration", "type": "quantitative"},
        },
    }


def _scenario_tree(tam: TAMOutput) -> dict[str, Any]:
    lines = ["graph TD", f'  C["{tam.target.concept_name or tam.target.concept}"]']
    for i, s in enumerate(tam.scenarios):
        node = f"S{i}"
        label = (s.framework_variant or s.framework).replace('"', "'")
        lines.append(f'  C --> {node}["{label}<br/>{s.value:,.0f}"]')
    return {"kind": "mermaid", "diagram": "\n".join(lines)}


def _lineage(tam: TAMOutput) -> dict[str, Any]:
    lines = ["graph LR"]
    for i, s in enumerate(tam.scenarios):
        node = f"S{i}"
        lines.append(f'  {node}["{(s.framework_variant or s.framework)}"]')
        for j, iu in enumerate(s.inputs_used):
            inp = f"{node}_I{j}"
            label = (iu.name or iu.primitive_slug).replace('"', "'")
            lines.append(f'  {inp}["{label}"] --> {node}')
    return {"kind": "mermaid", "diagram": "\n".join(lines)}


_BUILDERS = {
    "scenario_comparison": _scenario_comparison,
    "composition": _composition,
    "source_mix": _source_mix,
    "tornado": _tornado,
    "penetration": _penetration,
    "scenario_tree": _scenario_tree,
    "lineage": _lineage,
}


def build_chart(tam: TAMOutput, kind: str) -> dict[str, Any] | None:
    """Build one chart spec by ``kind``; ``None`` for an unknown kind."""
    builder = _BUILDERS.get(kind)
    return builder(tam) if builder is not None else None


def build_all_charts(tam: TAMOutput) -> dict[str, Any]:
    """All chart specs for a TAM, keyed by kind — the ``charts`` field on a result.

    Each carries a ``resource_uri`` so a host can also re-read it as a resource.
    """
    out: dict[str, Any] = {}
    for kind in ALL_KINDS:
        spec = build_chart(tam, kind)
        if spec is not None:
            out[kind] = {
                "spec": spec,
                "format": "mermaid" if kind in MERMAID_KINDS else "vega-lite",
                "resource_uri": f"strata://chart/{tam.state_hash}/{kind}",
            }
    return out


__all__ = ["ALL_KINDS", "build_all_charts", "build_chart"]
