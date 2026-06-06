"""Formula error hierarchy. Distinct types so the validator can map a failure
to a specific ``cross.formula_*`` finding code and the evaluator can surface a
clean ``EvaluatorError``."""

from __future__ import annotations


class FormulaError(ValueError):
    """Base for any formula failure."""


class FormulaSyntaxError(FormulaError):
    """Unparseable text: unknown char, ``/``, a stray numeric literal, a bad
    call shape, or a structural constant outside the allowed idiom."""


class FormulaUnitError(FormulaError):
    """The unit algebra rejected the formula at load time (e.g. ``+`` across
    different dimensions, ``logistic`` over a non-dimensionless operand)."""


class FormulaEvalError(FormulaError):
    """Eval-time failure: an unbound identifier or a non-finite intermediate."""
