"""Usage + metrics endpoints (Wave 3 / AC3.3 + AC3.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from strata.api.auth import Principal, require_principal
from strata.api.metering import get_meter
from strata.api.responses import UNAUTHORIZED

router = APIRouter(tags=["ops"])

_PRINCIPAL = Depends(require_principal)


class UsageResponse(BaseModel):
    org_id: str
    total: int
    by_route: dict[str, int]


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Per-key usage counts",
    description="Fetch request counts by route for the authenticated key.",
    responses=UNAUTHORIZED,
)
async def get_usage(principal: Principal = _PRINCIPAL) -> UsageResponse:
    meter = get_meter()
    return UsageResponse(
        org_id=principal.org_id,
        total=meter.total_for(principal.org_id),
        by_route=meter.usage_for(principal.org_id),
    )


@router.get(
    "/metrics",
    summary="Prometheus-style request metrics",
    description="Export metered request counts in Prometheus text exposition format.",
)
async def metrics() -> Response:
    snapshot = get_meter().snapshot()
    lines = [
        "# HELP strata_requests_total Metered requests by org and route.",
        "# TYPE strata_requests_total counter",
    ]
    for org_id in sorted(snapshot):
        for route, count in sorted(snapshot[org_id].items()):
            lines.append(f'strata_requests_total{{org="{org_id}",route="{route}"}} {count}')
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
