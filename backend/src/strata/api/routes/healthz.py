"""Liveness probe endpoint."""

from __future__ import annotations

import os
import shutil
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from strata import __version__
from strata.config import settings

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    env: str
    version: str


class LLMHealth(BaseModel):
    backend: Literal["claude-cli", "anthropic-sdk"]
    available: bool


@router.get(
    "/healthz",
    response_model=Health,
    summary="Liveness probe",
    description="Report the service status, environment, and version.",
)
async def healthz() -> Health:
    return Health(env=settings.env, version=__version__)


@router.get(
    "/healthz/llm",
    response_model=LLMHealth,
    summary="Resolver LLM backend probe",
    description=(
        "Report the resolver's selected LLM backend and whether it looks reachable. "
        "Never makes a completion call, never echoes key/token material."
    ),
)
async def healthz_llm() -> LLMHealth:
    """Report the resolver's selected LLM backend and whether it looks reachable.

    Lets the UI/ops tell "no backend configured" apart from a transient error.
    Read-only and cheap: never makes a completion call, never echoes key/token
    material (presence is reported as a bool only).
    """
    if os.environ.get("STRATA_LLM_BACKEND", "").strip().lower() == "anthropic":
        return LLMHealth(
            backend="anthropic-sdk", available=bool(os.environ.get("ANTHROPIC_API_KEY"))
        )
    return LLMHealth(backend="claude-cli", available=shutil.which("claude") is not None)
