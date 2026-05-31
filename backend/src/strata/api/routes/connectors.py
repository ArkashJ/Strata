"""Connector routes — the ingest catalog (connector-explorer).

Read-only teaching surface that answers "how do the connectors come into play":
each typed connector turns a regulator/aggregator API into hash-pinned atomic
primitives that frameworks consume. This lists the 22 connectors from the
capability registry (`connectors._capability`) and cross-references the live data
bank, so a connector that has actually produced primitives shows a real count and
a sample slug. No live API calls in the request path — counts come from the
already-ingested registry.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.connectors._capability import CapabilitySpec, all_capabilities
from strata.models import AtomicPrimitive
from strata.registry import Registry

router = APIRouter(prefix="/connectors", tags=["connectors"])

_REG = Depends(get_registry)

# Maps a connector to the source hosts its primitives carry, so we can count how
# many primitives in the bank each connector has actually produced. Invariant:
# presence here == the connector has data in reg.atomic. Connectors absent here
# simply report 0 ingested-so-far (honest — capability ≠ data yet).
# NB: kalshi is intentionally absent — its 202 primitives are quarantined to
# reg.signals (Q20, prediction_market), never reg.atomic, so it has no evaluable
# bank data by design (its signals surface lives at /signals instead).
_CONNECTOR_HOSTS: dict[str, tuple[str, ...]] = {
    "bls": ("www.bls.gov",),
    "census": ("api.census.gov", "www.census.gov"),
    "fred": ("fred.stlouisfed.org",),
    "edgar": ("data.sec.gov", "www.sec.gov"),
    "worldbank": ("data.worldbank.org",),
}


def _host_of(url: str) -> str:
    return url.split("/")[2] if "://" in url else ""


class CapabilityOut(BaseModel):
    method: str
    description: str
    returns: str


class ConnectorOut(BaseModel):
    connector: str
    source_tier: str
    method_count: int
    capabilities: list[CapabilityOut]
    primitives_in_bank: int
    sample_primitive_slug: str | None
    sample_source_url: str | None


@router.get(
    "",
    response_model=list[ConnectorOut],
    summary="List ingest connectors",
    description=(
        "The typed connectors that manufacture sourced primitives (connector → primitive → "
        "framework → TAM). Each carries its capability methods + source tier, plus a live "
        "count of primitives it has produced in the current data bank and a sample slug."
    ),
)
async def list_connectors(reg: Registry = _REG) -> list[ConnectorOut]:
    by_connector: dict[str, list[CapabilitySpec]] = defaultdict(list)
    for cap in all_capabilities():
        by_connector[cap.connector].append(cap)

    # Index bank primitives by source host once.
    by_host: dict[str, list[AtomicPrimitive]] = defaultdict(list)
    for prim in reg.atomic.values():
        by_host[_host_of(prim.source.url)].append(prim)

    out: list[ConnectorOut] = []
    for name, caps in sorted(by_connector.items()):
        hosts = _CONNECTOR_HOSTS.get(name, ())
        # Sort by slug so the sample is deterministic across platforms (registry
        # insertion order follows filesystem glob order, which is not portable).
        produced = sorted(
            (p for host in hosts for p in by_host.get(host, [])),
            key=lambda p: p.slug,
        )
        sample = produced[0] if produced else None
        out.append(
            ConnectorOut(
                connector=name,
                source_tier=str(caps[0].source_tier),
                method_count=len(caps),
                capabilities=[
                    CapabilityOut(method=c.method, description=c.description, returns=c.returns)
                    for c in caps
                ],
                primitives_in_bank=len(produced),
                sample_primitive_slug=sample.slug if sample else None,
                sample_source_url=sample.source.url if sample else None,
            )
        )
    return out
