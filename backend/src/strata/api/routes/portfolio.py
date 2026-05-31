"""Portfolio routes (spec §7, F4, F6).

``GET /portfolio`` is **read-only and always available** — it serves the cached,
pre-sized demo subset (F3-safe: no live LLM/Exa). The write routes (import /
size) only exist when ``STRATA_PORTFOLIO_ENABLED`` is on AND the caller carries
an authenticated principal; otherwise they 404, so prod can't accept untrusted
portfolio writes before review. This keeps the read path that powers the
``/portfolio`` page open while the write surface ships dark.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from strata.config import settings
from strata.sizing.demo import demo_counts, load_demo_portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioCompany(BaseModel):
    name: str
    domain: str
    vertical: str | None
    status: str
    market_concept_slug: str | None
    tam_value: float | None
    reason: str | None
    state_hash: str | None
    has_analyst_input: bool = False


class PortfolioResponse(BaseModel):
    org_id: str
    enabled: bool
    counts: dict[str, int]
    companies: list[PortfolioCompany]


@router.get(
    "",
    response_model=PortfolioResponse,
    summary="List the portfolio (cached demo subset)",
    description=(
        "Read-only portfolio view. Serves the deterministic, pre-sized demo "
        "subset — every number is computed offline and cached; this route never "
        "calls an LLM or Exa. 'unsizable' rows are intentional: the platform "
        "refuses to invent a number it cannot source (the Q20 thesis, visible)."
    ),
)
async def get_portfolio() -> PortfolioResponse:
    rows = load_demo_portfolio()
    companies = [
        PortfolioCompany(
            name=str(r.get("name", "")),
            domain=str(r.get("domain", "")),
            vertical=(str(r["vertical"]) if r.get("vertical") else None),
            status=str(r.get("status", "unsized")),
            market_concept_slug=(
                str(r["market_concept_slug"]) if r.get("market_concept_slug") else None
            ),
            tam_value=(float(r["tam_value"]) if r.get("tam_value") is not None else None),  # type: ignore[arg-type]
            reason=(str(r["reason"]) if r.get("reason") else None),
            state_hash=(str(r["state_hash"]) if r.get("state_hash") else None),
            has_analyst_input=bool(r.get("has_analyst_input", False)),
        )
        for r in rows
    ]
    return PortfolioResponse(
        org_id="default",
        enabled=settings.portfolio_enabled,
        counts=demo_counts(),
        companies=companies,
    )
