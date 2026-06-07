"""MCP Resources — the protocol drill-down surface (Phase 1).

Registers ``resources/templates/list``, ``resources/list`` and ``resources/read``
on the server so a host (Claude Code's ``@``-picker, claude.ai) can browse and
read Strata records by URI. Every numeric tool result already carries
``resource_uri`` links into these; reading one returns the full sourced record as
a JSON document.

URI scheme (``strata://<kind>/<id>``):

* ``primitive/{slug}``  — one atomic primitive (value + unit + citation + integrity)
* ``concept/{slug}``    — a concept with its competing measurements
* ``framework/{slug}``  — a TAM framework (method family, lens, inputs)
* ``tam/{hash}``        — a frozen TAM scenario tree (from the registry cache)
* ``report/{slug}``     — the assembled market report for a concept
* ``snapshot/{sha}``    — serve-time integrity status of a pinned snapshot
* ``chart/{hash}/{kind}`` — a Vega-Lite / Mermaid spec built from a cached TAM

Dispatch reuses the existing pure builders (``_cite`` / ``_serialize_tam`` /
``assemble_report`` / charts) so a resource read never diverges from a tool call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from pydantic import AnyUrl

from ..registry import Registry, RegistryError
from . import charts
from .integrity import snapshot_integrity
from .tools import cite_primitive

_JSON = "application/json"

# Bounded curated set surfaced by resources/list (full browse is via templates +
# read). Keeps the list small enough for a host to render.
_LIST_CAP = 25


def _templates() -> list[types.ResourceTemplate]:
    def tmpl(uri: str, name: str, desc: str) -> types.ResourceTemplate:
        return types.ResourceTemplate(uriTemplate=uri, name=name, description=desc, mimeType=_JSON)

    return [
        tmpl("strata://primitive/{slug}", "primitive", "An atomic sourced primitive."),
        tmpl("strata://concept/{slug}", "concept", "A market concept + competing measurements."),
        tmpl("strata://framework/{slug}", "framework", "A TAM framework recipe."),
        tmpl("strata://tam/{hash}", "tam", "A frozen TAM scenario tree."),
        tmpl("strata://report/{slug}", "report", "The assembled market report for a concept."),
        tmpl("strata://snapshot/{sha}", "snapshot", "Integrity status of a pinned snapshot."),
        tmpl("strata://chart/{hash}/{kind}", "chart", "A chart spec built from a cached TAM."),
    ]


def _curated_list(reg: Registry) -> list[types.Resource]:
    out: list[types.Resource] = []
    for slug, c in list(reg.concepts.items())[:_LIST_CAP]:
        out.append(
            types.Resource(
                uri=AnyUrl(f"strata://concept/{slug}"),
                name=c.name,
                description=c.definition[:200] if c.definition else None,
                mimeType=_JSON,
            )
        )
    for fw in list(reg.iter_frameworks())[:_LIST_CAP]:
        out.append(
            types.Resource(
                uri=AnyUrl(f"strata://framework/{fw.slug}"),
                name=fw.name,
                mimeType=_JSON,
            )
        )
    return out


def _read(reg: Registry, uri: str) -> dict[str, Any]:
    """Resolve one ``strata://`` URI to a JSON-able document. Raises
    ``RegistryError`` / ``KeyError`` for an unknown id (the caller maps to text)."""
    body = uri.removeprefix("strata://")
    kind, _, rest = body.partition("/")
    if kind == "primitive":
        p = reg.get_atomic(rest)
        return cite_primitive(p) | {"description": p.description}
    if kind == "concept":
        c = reg.get_concept(rest)
        return {
            "slug": c.slug,
            "name": c.name,
            "definition": c.definition,
            "competing_concepts": list(c.competing_concepts),
            "measurements": [
                cite_primitive(reg.atomic[m]) for m in c.measurements if m in reg.atomic
            ],
        }
    if kind == "framework":
        fw = reg.frameworks[rest]
        return {
            "slug": fw.slug,
            "name": fw.name,
            "method_family": fw.method_family.value,
            "lens": fw.lens.value,
            "formula": fw.formula,
            "inputs": [{"name": i.name, "role": i.role.value} for i in fw.inputs],
        }
    if kind == "tam":
        tam = reg.tam_outputs[rest]
        return tam.model_dump(mode="json")
    if kind == "report":
        from ..report import assemble_report

        return assemble_report(reg, rest).model_dump(mode="json")
    if kind == "snapshot":
        return {"snapshot_sha256": rest, "integrity": snapshot_integrity(rest)}
    if kind == "chart":
        chart_hash, _, chart_kind = rest.partition("/")
        tam = reg.tam_outputs[chart_hash]
        spec = charts.build_chart(tam, chart_kind)
        if spec is None:
            raise KeyError(f"unknown chart kind {chart_kind!r}")
        return spec
    raise KeyError(f"unknown resource kind {kind!r}")


def register_resources(server: Server, get_registry: Callable[[], Registry]) -> None:
    """Wire the resources capability onto ``server`` (declares it implicitly)."""

    @server.list_resource_templates()
    async def _list_templates() -> list[types.ResourceTemplate]:  # pyright: ignore[reportUnusedFunction]
        return _templates()

    @server.list_resources()
    async def _list_resources() -> list[types.Resource]:  # pyright: ignore[reportUnusedFunction]
        return _curated_list(get_registry())

    @server.read_resource()
    async def _read_resource(  # pyright: ignore[reportUnusedFunction]
        uri: AnyUrl,
    ) -> list[ReadResourceContents]:
        reg = get_registry()
        try:
            doc = _read(reg, str(uri))
        except (RegistryError, KeyError) as exc:
            doc = {"error": {"code": "NOT_FOUND", "message": str(exc), "uri": str(uri)}}
        return [ReadResourceContents(content=json.dumps(doc, default=str), mime_type=_JSON)]


# Exposed for tests / direct resolution without a transport.
read_resource_doc = _read

__all__ = ["read_resource_doc", "register_resources"]
