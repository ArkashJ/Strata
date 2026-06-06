"""Lexer: formula text → tokens. Recognizes ONLY the characters of the grammar.

Rejects, with a clear ``FormulaSyntaxError``: the division operator ``/`` (a
reserved-but-disabled op in Phase 2), any numeric literal other than a bare
``0``/``1`` (so ``2``, ``0.3``, ``1e6`` all fail), and any character outside
identifiers, the three operators, parentheses, and commas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .errors import FormulaSyntaxError

TokenKind = Literal["IDENT", "CONST", "PLUS", "MINUS", "STAR", "LPAREN", "RPAREN", "COMMA"]

_SINGLE: dict[str, TokenKind] = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
}


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    pos: int


def _is_ident_start(c: str) -> bool:
    return c.isascii() and c.isalpha()


def _is_ident_part(c: str) -> bool:
    return c.isascii() and (c.isalnum() or c == "_")


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c == "/":
            raise FormulaSyntaxError(f"division '/' is not supported in Phase 2 (pos {i}): {src!r}")
        if c in _SINGLE:
            tokens.append(Token(_SINGLE[c], c, i))
            i += 1
            continue
        if _is_ident_start(c):
            j = i + 1
            while j < n and _is_ident_part(src[j]):
                j += 1
            tokens.append(Token("IDENT", src[i:j], i))
            i = j
            continue
        if c.isdigit() or c == ".":
            j = i + 1
            while j < n and (src[j].isdigit() or src[j] in "._eE+-"):
                # Greedily consume the whole numeric-looking run so a stray
                # literal like 0.3 or 1e6 is reported whole, not split.
                if src[j] in "+-" and src[j - 1] not in "eE":
                    break
                j += 1
            text = src[i:j]
            if text not in ("0", "1"):
                raise FormulaSyntaxError(
                    f"numeric literal {text!r} is not allowed (only structural 0/1, "
                    f"pos {i}): {src!r}"
                )
            tokens.append(Token("CONST", text, i))
            i = j
            continue
        raise FormulaSyntaxError(f"unexpected character {c!r} at pos {i}: {src!r}")
    return tokens
