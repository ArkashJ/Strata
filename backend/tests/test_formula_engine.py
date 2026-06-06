"""Phase 2 — closed formula engine: lexer, parser, interpreter, unit algebra.

Mirrors the §10 test matrix. The safety tests assert that code-injection shapes
never parse (let alone execute) — the engine has no ``eval``/``exec`` path."""

from __future__ import annotations

import math

import pytest

from strata.evaluator.formula import (
    BinOp,
    Call,
    FormulaEvalError,
    FormulaSyntaxError,
    FormulaUnitError,
    Identifier,
    StructuralConst,
    eval_node,
    identifiers,
    infer_unit,
    parse,
)
from strata.models.framework import FrameworkInput, InputRole
from strata.models.unit import Unit, UnitDimension, UnitKind


# --------------------------------------------------------------------------- #
# Lexer / parser — structure & rejection
# --------------------------------------------------------------------------- #
def test_parse_simple_product() -> None:
    ast = parse("a * b")
    assert isinstance(ast, BinOp)
    assert ast.op == "*"
    assert ast == BinOp("*", Identifier("a"), Identifier("b"))


def test_precedence_plus_below_times() -> None:
    # a + b * c  ==  a + (b * c)
    ast = parse("a + b * c")
    assert ast == BinOp("+", Identifier("a"), BinOp("*", Identifier("b"), Identifier("c")))


def test_left_associative_product() -> None:
    # a * b * c  ==  (a * b) * c
    ast = parse("a * b * c")
    assert ast == BinOp("*", BinOp("*", Identifier("a"), Identifier("b")), Identifier("c"))


def test_parens_override() -> None:
    ast = parse("(a + b) * c")
    assert ast == BinOp("*", BinOp("+", Identifier("a"), Identifier("b")), Identifier("c"))


def test_discount_idiom_allowed() -> None:
    ast = parse("tools * rate * (1 - discount)")
    assert isinstance(ast, BinOp)
    assert "discount" in identifiers(ast)


def test_bare_const_outside_idiom_rejected() -> None:
    for bad in ("1", "a * 1", "1 * a", "a + 1", "min(a, 1)"):
        with pytest.raises(FormulaSyntaxError):
            parse(bad)


def test_clamp_bounds_allow_consts() -> None:
    ast = parse("clamp(x, 0, 1)")
    assert isinstance(ast, Call)
    assert ast.func == "clamp"


@pytest.mark.parametrize("bad", ["a / b", "a * 2", "a + 0.3", "1e6 * a", "a ** b"])
def test_stray_literals_and_division_rejected(bad: str) -> None:
    with pytest.raises(FormulaSyntaxError):
        parse(bad)


def test_unknown_function_rejected() -> None:
    with pytest.raises(FormulaSyntaxError):
        parse("sqrt(a)")


@pytest.mark.parametrize("evil", ["__import__('os')", "a ; b", "a `b`", "exec('x')", "a.b"])
def test_injection_shapes_never_parse(evil: str) -> None:
    with pytest.raises(FormulaSyntaxError):
        parse(evil)


def test_call_arity_enforced() -> None:
    with pytest.raises(FormulaSyntaxError):
        parse("clamp(x, 0)")  # needs 3
    with pytest.raises(FormulaSyntaxError):
        parse("curve(x)")  # needs 2


# --------------------------------------------------------------------------- #
# Interpreter — values
# --------------------------------------------------------------------------- #
def test_eval_product_exact() -> None:
    assert eval_node(parse("a * b"), {"a": 1000.0, "b": 12.5}) == 1000.0 * 12.5


def test_eval_sum_and_diff() -> None:
    env = {"a": 3.0, "b": 7.0}
    assert eval_node(parse("a + b"), env) == 10.0
    assert eval_node(parse("a - b"), env) == -4.0


def test_eval_min_max_clamp() -> None:
    assert eval_node(parse("min(a, b)"), {"a": 3.0, "b": 9.0}) == 3.0
    assert eval_node(parse("max(a, b)"), {"a": 3.0, "b": 9.0}) == 9.0
    assert eval_node(parse("clamp(x, 0, 1)"), {"x": 1.7}) == 1.0
    assert eval_node(parse("clamp(x, 0, 1)"), {"x": -0.4}) == 0.0


def test_eval_curve_bounds() -> None:
    assert eval_node(parse("curve(x, k)"), {"x": 0.0, "k": 1.0}) == 0.0
    # 1 - e^(-5) ≈ 0.9933 — strictly inside (0, 1); larger x*k saturates to 1.0.
    near_one = eval_node(parse("curve(x, k)"), {"x": 5.0, "k": 1.0})
    assert 0.99 < near_one < 1.0


def test_eval_logistic_midpoint_half() -> None:
    v = eval_node(parse("logistic(x, m, s)"), {"x": 5.0, "m": 5.0, "s": 1.0})
    assert v == pytest.approx(0.5)
    lo = eval_node(parse("logistic(x, m, s)"), {"x": 0.0, "m": 5.0, "s": 1.0})
    hi = eval_node(parse("logistic(x, m, s)"), {"x": 10.0, "m": 5.0, "s": 1.0})
    assert lo < 0.5 < hi  # monotone increasing


def test_eval_discount_idiom_value() -> None:
    v = eval_node(
        parse("tools * rate * (1 - discount)"), {"tools": 10.0, "rate": 2.0, "discount": 0.25}
    )
    assert v == 10.0 * 2.0 * (1 - 0.25)


def test_unbound_identifier_raises() -> None:
    with pytest.raises(FormulaEvalError):
        eval_node(parse("a * b"), {"a": 1.0})


def test_non_finite_operand_raises() -> None:
    with pytest.raises(FormulaEvalError):
        eval_node(parse("a * b"), {"a": math.inf, "b": 1.0})


# --------------------------------------------------------------------------- #
# Byte-identical fold property (§4.5)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "a,b",
    [(3.0, 7.0), (1e9, 0.33), (2.5, 4.0), (1.234567e-3, 9.87e5), (0.0, 123.0)],
)
def test_product_byte_identical_to_old_fold(a: float, b: float) -> None:
    # Old fold: value=1.0; value*=a; value*=b  ==  (1.0*a)*b
    assert (1.0 * a) * b == eval_node(parse("a * b"), {"a": a, "b": b})


# --------------------------------------------------------------------------- #
# Unit algebra (load-time)
# --------------------------------------------------------------------------- #
def _inp(
    name: str, kind: UnitKind, dim: UnitDimension, currency: str | None = None
) -> FrameworkInput:
    return FrameworkInput(
        name=name,
        role=InputRole.BASE_VALUE,
        unit_signature=Unit(kind=kind, dimension=dim, currency=currency),
        required=True,
    )


def test_sum_across_dimensions_rejected() -> None:
    inputs = {
        "people": _inp("people", UnitKind.STOCK, UnitDimension.PEOPLE),
        "money": _inp("money", UnitKind.FLOW, UnitDimension.CURRENCY, "USD"),
    }
    with pytest.raises(FormulaUnitError):
        infer_unit(parse("people + money"), inputs, "people + money")


def test_logistic_over_currency_rejected() -> None:
    inputs = {
        "money": _inp("money", UnitKind.FLOW, UnitDimension.CURRENCY, "USD"),
        "m": _inp("m", UnitKind.DIMENSIONLESS, UnitDimension.PERCENT),
        "s": _inp("s", UnitKind.DIMENSIONLESS, UnitDimension.PERCENT),
    }
    with pytest.raises(FormulaUnitError):
        infer_unit(parse("logistic(money, m, s)"), inputs, "logistic(money, m, s)")


def test_same_unit_sum_ok() -> None:
    inputs = {
        "ent": _inp("ent", UnitKind.FLOW, UnitDimension.CURRENCY, "USD"),
        "smb": _inp("smb", UnitKind.FLOW, UnitDimension.CURRENCY, "USD"),
    }
    res = infer_unit(parse("ent + smb"), inputs, "ent + smb")
    assert res.dimension == "currency"


def test_product_is_allowed_unit_crossing() -> None:
    inputs = {
        "people": _inp("people", UnitKind.STOCK, UnitDimension.PEOPLE),
        "cost": _inp("cost", UnitKind.INTENSIVE, UnitDimension.CURRENCY, "USD"),
    }
    # No raise — products are unit-crossing by design (Q3).
    infer_unit(parse("people * cost"), inputs, "people * cost")


def test_discount_idiom_unit_coheres() -> None:
    inputs = {
        "tools": _inp("tools", UnitKind.STOCK, UnitDimension.ORGANIZATIONS),
        "rate": _inp("rate", UnitKind.DIMENSIONLESS, UnitDimension.PERCENT),
        "discount": _inp("discount", UnitKind.DIMENSIONLESS, UnitDimension.PERCENT),
    }
    infer_unit(parse("tools * rate * (1 - discount)"), inputs, "tools * rate * (1 - discount)")


def test_struct_const_node_value_constrained() -> None:
    assert StructuralConst(0).value == 0
    assert StructuralConst(1).value == 1
