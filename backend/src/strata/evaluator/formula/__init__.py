"""Closed, whitelisted formula language for ``Framework.formula`` (Phase 2).

The five-node AST, its lexer/parser, the closed interpreter (no ``eval``/
``exec``), and the load-time unit algebra live here. Both the evaluator
(eval-time value walk) and the validator (load-time unit + identifier check)
import from this package.

Grammar (EBNF, see docs/plans/02): a pure arithmetic expression over bound
``FrameworkInput`` names with ``+ - *``, the calls
``min|max|clamp|logistic|curve``, and the structural constants ``0``/``1``
(legal only in the ``(1 - x)`` discount idiom and as ``clamp``/``logistic``
bounds). No free numeric literals — that is the Q15 guard against smuggling a
scalar magnitude through the formula.
"""

from __future__ import annotations

from .ast_nodes import BinOp, Call, Identifier, Node, StructuralConst
from .errors import FormulaError, FormulaEvalError, FormulaSyntaxError, FormulaUnitError
from .interp import eval_node
from .parser import parse
from .units import ReducedUnit, infer_unit


def identifiers(node: Node) -> set[str]:
    """Every ``Identifier`` name referenced anywhere in the tree."""
    if isinstance(node, Identifier):
        return {node.name}
    if isinstance(node, BinOp):
        return identifiers(node.left) | identifiers(node.right)
    if isinstance(node, Call):
        out: set[str] = set()
        for arg in node.args:
            out |= identifiers(arg)
        return out
    return set()


__all__ = [
    "BinOp",
    "Call",
    "FormulaError",
    "FormulaEvalError",
    "FormulaSyntaxError",
    "FormulaUnitError",
    "Identifier",
    "Node",
    "ReducedUnit",
    "StructuralConst",
    "eval_node",
    "identifiers",
    "infer_unit",
    "parse",
]
