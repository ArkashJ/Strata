"""Reusable OpenAPI response declarations for error outcomes.

FastAPI auto-documents 2xx responses (from ``response_model``) and 422 (for any
route with a validated request body), but the non-2xx outcomes a handler can
*raise* — 400/401/403/404/409/429/5xx via ``HTTPException`` — are invisible in
``/openapi.json`` unless declared with the route's ``responses=`` kwarg. These
helpers keep that declaration uniform across every route so the generated spec
honestly advertises each endpoint's failure modes.

Usage::

    from strata.api.responses import UNAUTHORIZED, error, merge

    @router.get("/{slug}", responses=error(404, "Concept not found."))
    ...

    @router.post("/sync", responses=merge(UNAUTHORIZED, error(409, "Already syncing.")))
    ...
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """The envelope FastAPI returns for an ``HTTPException``: ``{"detail": "..."}``."""

    detail: str


# A ``responses=`` mapping: HTTP status code -> OpenAPI response object.
ResponseSpec = dict[int | str, dict[str, Any]]


def error(code: int, description: str) -> ResponseSpec:
    """One error response carrying the standard ``ErrorDetail`` schema."""
    return {code: {"model": ErrorDetail, "description": description}}


def merge(*specs: ResponseSpec) -> ResponseSpec:
    """Combine several response specs into one ``responses=`` mapping."""
    out: ResponseSpec = {}
    for spec in specs:
        out.update(spec)
    return out


# Reusable specs for the two cross-cutting failure modes (auth + rate limiting).
UNAUTHORIZED: ResponseSpec = error(401, "Missing or invalid API key.")
RATE_LIMITED: ResponseSpec = error(
    429, "Rate limit exceeded — retry after the interval in the Retry-After header."
)
