"""The four — and only four — AST node kinds. Frozen, slotted, immutable.

There is deliberately NO general numeric-literal node: ``StructuralConst`` is
constrained to ``{0, 1}`` and is the only literal, which is the structural guard
against a scalar magnitude leaking into the math (Q15)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BinaryOp = Literal["+", "-", "*"]
FuncName = Literal["min", "max", "clamp", "logistic", "curve"]


@dataclass(frozen=True, slots=True)
class Identifier:
    """A leaf that binds to a ``FrameworkInput.name``."""

    name: str


@dataclass(frozen=True, slots=True)
class StructuralConst:
    """The structural constant ``0`` or ``1`` — dimensionless, never a quantity."""

    value: Literal[0, 1]


@dataclass(frozen=True, slots=True)
class BinOp:
    op: BinaryOp
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Call:
    func: FuncName
    args: tuple[Node, ...]


Node = Identifier | StructuralConst | BinOp | Call

# Arg-count contract per function — enforced by the parser.
FUNC_ARITY: dict[FuncName, tuple[int, int]] = {
    "min": (2, 16),
    "max": (2, 16),
    "clamp": (3, 3),
    "logistic": (3, 3),
    "curve": (2, 2),
}
