"""Closed interpreter: walk the AST over a ``{name: value}`` env → float.

No dynamic execution anywhere — no interpreter eval, no exec, no compile, no
getattr, no dunder-import, no I/O. The walk
handles only the four node kinds and the five whitelisted function names;
identifiers resolve only against the bound ``env`` dict of primitive values.
Every intermediate is finite-guarded, mirroring the engine's existing
``math.isfinite`` gate."""

from __future__ import annotations

import math

from .ast_nodes import BinOp, Identifier, Node, StructuralConst
from .errors import FormulaEvalError


def _finite(x: float, what: str) -> float:
    if not math.isfinite(x):
        raise FormulaEvalError(f"non-finite intermediate from {what}: {x!r}")
    return x


def eval_node(node: Node, env: dict[str, float]) -> float:
    if isinstance(node, Identifier):
        try:
            return env[node.name]
        except KeyError:
            raise FormulaEvalError(f"unbound identifier {node.name!r}") from None
    if isinstance(node, StructuralConst):
        return float(node.value)
    if isinstance(node, BinOp):
        a = eval_node(node.left, env)
        b = eval_node(node.right, env)
        if node.op == "+":
            return _finite(a + b, "'+'")
        if node.op == "-":
            return _finite(a - b, "'-'")
        return _finite(a * b, "'*'")
    # node is Call (the closed AST has exactly four kinds; the parser guarantees it).
    vals = [eval_node(arg, env) for arg in node.args]
    if node.func == "min":
        return _finite(min(vals), "min")
    if node.func == "max":
        return _finite(max(vals), "max")
    if node.func == "clamp":
        x, lo, hi = vals
        return _finite(max(lo, min(x, hi)), "clamp")
    if node.func == "logistic":
        x, mid, steep = vals
        return _finite(1.0 / (1.0 + math.exp(-steep * (x - mid))), "logistic")
    # curve: bounded saturating adoption 1 - e^(-k*x) ∈ (0, 1)
    x, k = vals
    return _finite(1.0 - math.exp(-k * x), "curve")
