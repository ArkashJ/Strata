"""Lineage DAG route — server-side replacement for the frontend's local walk.

``GET /lineage/{concept_slug}`` returns the provenance graph for a concept as a
``{nodes, edges}`` payload whose keys match ``web/.../LineageGraph.tsx``'s client
builder exactly, so the frontend can swap its in-component walk for a fetch.

Traversal (read-only over the registry):

    concept ──▶ framework (applicable_to / variant)
                  └─▶ framework input ─bound─▶ primitive
                                                 ├─ composite ─▶ its inputs (primitives)
                                                 └─ atomic ─▶ derives_from (primitives)

A visited set guards cycles (a self/mutually-referential ``derives_from`` or
composite ``inputs`` terminates instead of recursing forever) and a depth cap
bounds the walk. No auth — the curated graph is public.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from strata.api.deps import get_registry
from strata.api.responses import error
from strata.models import AtomicPrimitive, CompositePrimitive
from strata.registry import Registry, RegistryError

router = APIRouter(prefix="/lineage", tags=["lineage"])

_REG = Depends(get_registry)

# Bounds the primitive-derivation walk so a deep (or maliciously crafted) chain
# can never blow the stack; the cycle-guard already prevents infinite loops, this
# just caps a legitimately deep DAG. 8 comfortably exceeds the real bank depth
# (concept → framework → composite → atomic → derives_from is 4).
MAX_DEPTH = 8


class GraphNode(BaseModel):
    """Mirrors the ``GraphNode`` interface in LineageGraph.tsx. ``method_family``,
    ``role``, ``value``, ``lens`` are all optional there; we emit ``lens`` on
    framework nodes and ``role`` on primitive nodes that fill a framework input."""

    id: str
    label: str
    kind: str  # "concept" | "framework" | "primitive"
    method_family: str | None = None
    role: str | None = None
    value: float | None = None
    lens: str | None = None


class GraphEdge(BaseModel):
    """Mirrors the ``GraphEdge`` interface: id/from/to + free-text ``signals``.

    ``from`` is reserved in Python, so the field is declared as ``from_`` with a
    serialization alias of ``from`` to match the client keys byte-for-byte."""

    id: str
    # ``from`` is a Python keyword; the field stays ``from_`` for construction
    # (pyright-friendly) but SERIALIZES as ``from`` so the JSON keys match the
    # client builder exactly. ``serialization_alias`` only — no input alias — so
    # callers always pass ``from_=`` and never the keyword.
    from_: str = Field(serialization_alias="from")
    to: str
    signals: list[str]


class LineageResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def _truncate(raw: str, n: int) -> str:
    """Match the client's label truncation so server- and client-built graphs are
    visually identical."""
    s = (raw or "").strip()
    if len(s) <= n:
        return s
    return f"{s[: n - 1]}…"


class _Builder:
    """Accumulates nodes/edges with de-duplication and a visited cycle-guard."""

    def __init__(self, reg: Registry) -> None:
        self._reg = reg
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        # Primitive-derivation cycle guard: a primitive whose subtree is being (or
        # has been) walked is in here, so a back-edge into it adds the edge but
        # does not recurse again.
        self._walked: set[str] = set()

    def add_node(self, node: GraphNode) -> None:
        # First writer wins: a primitive may be reached as a framework input
        # (carrying a role) AND as a composite member; keep the richer first form.
        self._nodes.setdefault(node.id, node)

    def add_edge(self, edge: GraphEdge) -> None:
        self._edges.setdefault(edge.id, edge)

    def result(self) -> LineageResponse:
        return LineageResponse(nodes=list(self._nodes.values()), edges=list(self._edges.values()))

    def walk_primitive(self, slug: str, parent_id: str, depth: int) -> None:
        """Add a primitive node + the parent→primitive edge, then recurse into its
        composite inputs / atomic ``derives_from`` (cycle- and depth-guarded)."""
        pid = f"p-{slug}"
        prim = self.lookup_primitive(slug)
        if prim is not None:
            self.add_node(GraphNode(id=pid, label=_truncate(prim.name, 24), kind="primitive"))
        else:
            # An unresolved slug (dangling reference) still gets a node so the edge
            # is meaningful; label falls back to the raw slug.
            self.add_node(GraphNode(id=pid, label=_truncate(slug, 24), kind="primitive"))

        self.add_edge(
            GraphEdge(id=f"{parent_id}__{pid}", from_=parent_id, to=pid, signals=["derives from"])
        )

        if prim is None or pid in self._walked or depth >= MAX_DEPTH:
            return
        self.expand_children(prim, pid, depth)

    def expand_children(
        self,
        prim: AtomicPrimitive | CompositePrimitive,
        pid: str,
        depth: int,
    ) -> None:
        """Recurse into a primitive's lineage: composite → its set-op members,
        atomic → its ``derives_from`` chain. Marks ``pid`` walked first so a
        back-edge into it terminates instead of re-expanding (cycle-guard)."""
        if pid in self._walked or depth >= MAX_DEPTH:
            return
        self._walked.add(pid)
        children = prim.inputs if isinstance(prim, CompositePrimitive) else prim.derives_from
        for child in children:
            self.walk_primitive(child, pid, depth + 1)

    def lookup_primitive(self, slug: str) -> AtomicPrimitive | CompositePrimitive | None:
        try:
            return self._reg.primitive(slug)
        except RegistryError:
            return None


def build_lineage(reg: Registry, concept_slug: str) -> LineageResponse:
    """Construct the lineage DAG for ``concept_slug``. Raises ``RegistryError`` if
    the concept is unknown (the route maps that to 404)."""
    concept = reg.get_concept(concept_slug)
    b = _Builder(reg)

    b.add_node(GraphNode(id="concept", label=_truncate(concept.name, 28), kind="concept"))

    # Frameworks that size this concept: either declared in ``applicable_to`` or
    # carrying a concept-scoped variant (mirrors build.py's resolution).
    for fw in reg.iter_frameworks():
        variant = fw.variant_for(concept_slug)
        if concept_slug not in fw.applicable_to and variant is None:
            continue

        fid = f"f-{fw.slug}"
        b.add_node(
            GraphNode(
                id=fid,
                label=_truncate(fw.name, 26),
                kind="framework",
                method_family=fw.method_family.value,
                lens=fw.lens.value,
            )
        )
        b.add_edge(
            GraphEdge(
                id=f"concept__{fid}",
                from_="concept",
                to=fid,
                signals=[f"lens: {fw.lens.value.replace('_', ' ')}"],
            )
        )

        bindings = variant.default_inputs if variant is not None else {}
        for inp in fw.inputs:
            bound = bindings.get(inp.name)
            if bound is None:
                # No primitive bound to this role for this concept — nothing to add.
                continue
            pid = f"p-{bound}"
            prim = b.lookup_primitive(bound)
            b.add_node(
                GraphNode(
                    id=pid,
                    label=_truncate(prim.name if prim is not None else bound, 24),
                    kind="primitive",
                    role=inp.role.value,
                )
            )
            b.add_edge(
                GraphEdge(
                    id=f"{fid}__{pid}",
                    from_=fid,
                    to=pid,
                    signals=[f"role: {inp.role.value.replace('_', ' ')}"],
                )
            )
            # Recurse into the bound primitive's own lineage (composite members /
            # atomic derives_from), guarded against cycles + depth.
            if prim is not None:
                b.expand_children(prim, pid, depth=0)

    return b.result()


@router.get(
    "/{concept_slug}",
    response_model=LineageResponse,
    summary="Provenance DAG for a concept (nodes + edges)",
    description=(
        "Walk concept → framework → bound primitive → composite inputs / "
        "derives_from, returning a {nodes, edges} graph matching the frontend's "
        "LineageGraph builder. Cycle- and depth-guarded; read-only."
    ),
    responses=error(404, "Concept not found."),
)
async def get_lineage(
    concept_slug: str,
    reg: Registry = _REG,
) -> LineageResponse:
    try:
        return build_lineage(reg, concept_slug)
    except RegistryError as exc:
        raise HTTPException(404, f"concept {concept_slug!r} not found") from exc
