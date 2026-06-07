"""MCP tool error taxonomy (Phase 0 / A5).

A ``ToolError`` is a *non-protocol* failure: the call reached a handler but the
inputs / state could not produce a sourced answer. The server turns it into a
``CallToolResult`` with ``isError=True`` and an actionable payload (code +
message + retriable + remediation) rather than a transport-level error, so the
driving agent gets a structured signal it can act on (fix the slug, enable a
gate, widen the scope) instead of an opaque 500.

The positional ``message`` constructor is kept backward-compatible so the dozens
of existing ``raise ToolError("...")`` call sites keep working unchanged; they
default to the generic ``TOOL_ERROR`` code.
"""

from __future__ import annotations

from typing import Any

# Error codes — a small, stable taxonomy the agent (and tests) can branch on.
CODE_TOOL_ERROR = "TOOL_ERROR"
CODE_CONCEPT_NOT_FOUND = "CONCEPT_NOT_FOUND"
CODE_PRIMITIVE_NOT_FOUND = "PRIMITIVE_NOT_FOUND"
CODE_NO_MATCH = "NO_MATCH"
CODE_UNIT_MISMATCH = "UNIT_MISMATCH"
CODE_MODELED_FENCE = "MODELED_FENCE"
CODE_INVALID_INPUT = "INVALID_INPUT"
CODE_LIVE_DISABLED = "LIVE_DISABLED"
CODE_PORTFOLIO_DISABLED = "PORTFOLIO_DISABLED"
CODE_INTEGRITY_STALE = "INTEGRITY_STALE"
CODE_EVALUATOR_ERROR = "EVALUATOR_ERROR"


class ToolError(RuntimeError):
    """A tool was called with bad arguments, an unknown slug, or hit a gate.

    ``message`` stays positional for backward compatibility. ``code`` keys the
    taxonomy; ``retriable`` tells the agent whether re-calling unchanged could
    ever succeed (e.g. a transient network failure) vs a structural problem;
    ``remediation`` is a one-line, agent-actionable next step.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = CODE_TOOL_ERROR,
        retriable: bool = False,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.remediation = remediation

    def to_payload(self) -> dict[str, Any]:
        """The structured error envelope embedded in an ``isError`` result."""
        err: dict[str, Any] = {
            "code": self.code,
            "message": str(self),
            "retriable": self.retriable,
        }
        if self.remediation is not None:
            err["remediation"] = self.remediation
        return {"error": err}


__all__ = [
    "CODE_CONCEPT_NOT_FOUND",
    "CODE_EVALUATOR_ERROR",
    "CODE_INTEGRITY_STALE",
    "CODE_INVALID_INPUT",
    "CODE_LIVE_DISABLED",
    "CODE_MODELED_FENCE",
    "CODE_NO_MATCH",
    "CODE_PORTFOLIO_DISABLED",
    "CODE_PRIMITIVE_NOT_FOUND",
    "CODE_TOOL_ERROR",
    "CODE_UNIT_MISMATCH",
    "ToolError",
]
