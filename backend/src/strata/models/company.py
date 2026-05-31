"""Company record — an org-scoped pointer at a market (spec §3, §4).

A company does NOT have a TAM; the *market it competes in* does. So this record
is a cheap pointer (name + domain + vertical) that, once sized, links to a
shared MARKET concept and caches the resolved TAM value. Optional per-company
``overrides`` (an ``EvalOverrides`` payload) refine the shared market at size
time without ever persisting a new primitive (Q20-safe).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CompanyStatus = Literal["unsized", "sized", "unsizable"]

_SCHEME_RE = re.compile(r"^[a-z]+://")
_WWW_RE = re.compile(r"^www\.")


def normalize_domain(raw: str) -> str:
    """Lowercase, strip scheme / ``www.`` / path / trailing slash so import is
    idempotent on ``(org_id, domain)``. ``HTTPS://Cursor.com/pricing`` → ``cursor.com``."""
    d = (raw or "").strip().lower()
    d = _SCHEME_RE.sub("", d)
    d = d.split("/", 1)[0]
    d = _WWW_RE.sub("", d)
    return d.strip()


class CompanyRecord(BaseModel):
    """One portfolio company, carried between CLI / MCP / HTTP / sizing layers."""

    org_id: str = "default"
    name: str
    domain: str = ""
    vertical: str | None = None
    market_concept_slug: str | None = None
    status: CompanyStatus = "unsized"
    overrides: dict[str, Any] | None = None
    tam_value: float | None = None
    reason: str | None = None
    sized_at: datetime | None = None
    # Set when any sourced input is analyst-tier — drives the downstream
    # "contains unverified analyst inputs" banner (F2).
    has_analyst_input: bool = False

    @field_validator("domain")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_domain(v)

    @property
    def key(self) -> str:
        """Idempotency key — the normalized domain, falling back to the name when
        a row has no website (the CSV has blank-website rows)."""
        return self.domain or self.name.strip().lower()


class LensGap(BaseModel):
    """One ``unsizable`` outcome — the evidence base for P3 lens expansion (§9)."""

    company: str
    domain: str = ""
    proposed_lens: str | None = None
    missing_role: str | None = None
    reason: str = ""
    ts: str = Field(default="")
