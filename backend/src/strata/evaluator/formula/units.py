"""Load-time unit algebra over the AST (docs/plans/02 §5).

The interpreter is unit-blind; all unit safety happens here, once, at registry
load. ``infer_unit`` walks the AST with a *unit* algebra and raises
``FormulaUnitError`` on a soundly-detectable incoherence:

  * ``+`` / ``-`` / ``min`` / ``max`` / ``clamp`` operands that are not the same
    unit, and
  * ``logistic`` / ``curve`` operands that are not dimensionless.

Products (``*``) are unit-crossing by design (Q3); a product of two concrete
dimensions reduces to ``UNKNOWN`` rather than guessing a dimension that the bare
``unit_signature`` (which omits the implicit per-X denominator on intensive
inputs) cannot soundly support. The dimensional output-unit match is therefore
deferred — see the note in ``validator/cross_record``. This keeps the five
existing pure-product frameworks loading unchanged while still catching the
non-product mistakes new frameworks can make."""

from __future__ import annotations

from dataclasses import dataclass

from ...models.framework import FrameworkInput
from .ast_nodes import BinOp, Identifier, Node, StructuralConst
from .errors import FormulaUnitError


@dataclass(frozen=True, slots=True)
class ReducedUnit:
    """A reduced unit signature for the algebra. ``unknown`` marks a product
    whose dimension cannot be soundly reduced; ``kind == 'dimensionless'`` marks
    a fraction / structural constant."""

    kind: str | None = None
    dimension: str | None = None
    currency: str | None = None
    unknown: bool = False

    @property
    def is_dimensionless(self) -> bool:
        return self.kind == "dimensionless"

    def same_as(self, other: ReducedUnit) -> bool:
        if self.unknown or other.unknown:
            return True  # lenient: cannot disprove equality of an unreduced product
        if self.is_dimensionless and other.is_dimensionless:
            return True
        if self.dimension != other.dimension or self.kind != other.kind:
            return False
        if self.currency is not None and other.currency is not None:
            return self.currency == other.currency
        return True


DIMENSIONLESS = ReducedUnit(kind="dimensionless")
UNKNOWN = ReducedUnit(unknown=True)


def _require_same(units: list[ReducedUnit], ctx: str, src: str) -> ReducedUnit:
    first = units[0]
    for u in units[1:]:
        if not first.same_as(u):
            raise FormulaUnitError(f"{ctx} operands must share a unit, got {first} vs {u}: {src!r}")
    # Prefer a concrete unit as the result when present.
    for u in units:
        if not u.unknown:
            return u
    return first


def _require_dimensionless(units: list[ReducedUnit], ctx: str, src: str) -> ReducedUnit:
    for u in units:
        if not u.is_dimensionless:
            raise FormulaUnitError(f"{ctx} operands must be dimensionless, got {u}: {src!r}")
    return DIMENSIONLESS


def infer_unit(node: Node, inputs_by_name: dict[str, FrameworkInput], src: str) -> ReducedUnit:
    if isinstance(node, Identifier):
        inp = inputs_by_name.get(node.name)
        if inp is None:
            raise FormulaUnitError(f"identifier {node.name!r} is not a declared input: {src!r}")
        sig = inp.unit_signature
        return ReducedUnit(kind=str(sig.kind), dimension=str(sig.dimension), currency=sig.currency)
    if isinstance(node, StructuralConst):
        return DIMENSIONLESS
    if isinstance(node, BinOp):
        left = infer_unit(node.left, inputs_by_name, src)
        right = infer_unit(node.right, inputs_by_name, src)
        if node.op == "*":
            if left.is_dimensionless:
                return right
            if right.is_dimensionless:
                return left
            return UNKNOWN
        return _require_same([left, right], f"'{node.op}'", src)
    # Call
    arg_units = [infer_unit(a, inputs_by_name, src) for a in node.args]
    if node.func in ("logistic", "curve"):
        return _require_dimensionless(arg_units, node.func, src)
    # min / max / clamp — all operands share a unit; result is that unit.
    return _require_same(arg_units, node.func, src)
