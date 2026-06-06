"""Recursive-descent parser over the EBNF in docs/plans/02 §2.6.

``parse`` is memoized on the formula string: a framework's formula is parsed
once for the lifetime of the process. The produced tree contains only the four
whitelisted node kinds; anything else raises ``FormulaSyntaxError`` before the
interpreter ever runs."""

from __future__ import annotations

from functools import lru_cache
from typing import get_args

from .ast_nodes import FUNC_ARITY, BinOp, Call, FuncName, Identifier, Node, StructuralConst
from .errors import FormulaSyntaxError
from .lexer import Token, tokenize

_FUNCS: frozenset[str] = frozenset(get_args(FuncName))


class _Parser:
    def __init__(self, tokens: list[Token], src: str) -> None:
        self._toks = tokens
        self._src = src
        self._i = 0

    def _peek(self) -> Token | None:
        return self._toks[self._i] if self._i < len(self._toks) else None

    def trailing(self) -> Token | None:
        """The current unconsumed token, or None at end — for detecting leftover input."""
        return self._peek()

    def _next(self) -> Token:
        tok = self._peek()
        if tok is None:
            raise FormulaSyntaxError(f"unexpected end of formula: {self._src!r}")
        self._i += 1
        return tok

    def _expect(self, kind: str) -> Token:
        tok = self._next()
        if tok.kind != kind:
            raise FormulaSyntaxError(
                f"expected {kind} but found {tok.text!r} at pos {tok.pos}: {self._src!r}"
            )
        return tok

    # expr = term { ('+' | '-') term }
    def parse_expr(self) -> Node:
        node = self.parse_term()
        while (tok := self._peek()) is not None and tok.kind in ("PLUS", "MINUS"):
            self._next()
            right = self.parse_term()
            node = BinOp("+" if tok.kind == "PLUS" else "-", node, right)
        return node

    # term = factor { '*' factor }
    def parse_term(self) -> Node:
        node = self.parse_factor()
        while (tok := self._peek()) is not None and tok.kind == "STAR":
            self._next()
            node = BinOp("*", node, self.parse_factor())
        return node

    # factor = primary
    def parse_factor(self) -> Node:
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self._next()
        if tok.kind == "LPAREN":
            inner = self.parse_expr()
            self._expect("RPAREN")
            return inner
        if tok.kind == "CONST":
            return StructuralConst(0 if tok.text == "0" else 1)
        if tok.kind == "IDENT":
            nxt = self._peek()
            if nxt is not None and nxt.kind == "LPAREN":
                return self._parse_call(tok)
            return Identifier(tok.text)
        raise FormulaSyntaxError(f"unexpected token {tok.text!r} at pos {tok.pos}: {self._src!r}")

    def _parse_call(self, name_tok: Token) -> Call:
        if name_tok.text not in _FUNCS:
            raise FormulaSyntaxError(
                f"unknown function {name_tok.text!r} at pos {name_tok.pos} "
                f"(allowed: {sorted(_FUNCS)}): {self._src!r}"
            )
        func: FuncName = name_tok.text  # type: ignore[assignment]
        self._expect("LPAREN")
        args: list[Node] = [self.parse_expr()]
        while (tok := self._peek()) is not None and tok.kind == "COMMA":
            self._next()
            args.append(self.parse_expr())
        self._expect("RPAREN")
        lo, hi = FUNC_ARITY[func]
        if not (lo <= len(args) <= hi):
            raise FormulaSyntaxError(
                f"{func} takes {lo}..{hi} args, got {len(args)}: {self._src!r}"
            )
        return Call(func, tuple(args))


def _check_structural(node: Node, *, const_ok: bool, src: str) -> None:
    """A ``StructuralConst`` is legal ONLY as the left operand of ``-`` (the
    ``1 - x`` complement idiom) or as an argument to ``clamp``/``logistic`` (the
    structural bounds). Anywhere else a bare ``0``/``1`` is a syntax error."""
    if isinstance(node, StructuralConst):
        if not const_ok:
            raise FormulaSyntaxError(
                f"structural constant {node.value} is only allowed in the "
                f"'(1 - x)' idiom or as a clamp/logistic bound: {src!r}"
            )
        return
    if isinstance(node, Identifier):
        return
    if isinstance(node, BinOp):
        # '1 - x': the left operand may be a structural const; nothing else may.
        _check_structural(node.left, const_ok=node.op == "-", src=src)
        _check_structural(node.right, const_ok=False, src=src)
        return
    # node is Call: structural consts are allowed only as clamp/logistic bounds.
    bound_ctx = node.func in ("clamp", "logistic")
    for arg in node.args:
        _check_structural(arg, const_ok=bound_ctx, src=src)


@lru_cache(maxsize=512)
def parse(formula: str) -> Node:
    """Parse a formula string into the closed AST (memoized per string)."""
    tokens = tokenize(formula)
    if not tokens:
        raise FormulaSyntaxError(f"empty formula: {formula!r}")
    p = _Parser(tokens, formula)
    node = p.parse_expr()
    leftover = p.trailing()
    if leftover is not None:
        raise FormulaSyntaxError(
            f"unexpected trailing token {leftover.text!r} at pos {leftover.pos}: {formula!r}"
        )
    _check_structural(node, const_ok=False, src=formula)
    return node
