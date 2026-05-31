"""A second, network-free SaaS provider (Wave 5B / AC5B.5).

Proves the connector framework is generic: a new provider is just a
``SaaSConnector`` subclass + object->primitive mapping, no core changes. Used as
the deterministic test vehicle for the full connect->sync->size->disconnect flow.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ...models import AtomicPrimitive
from .base import SaaSConnector, make_private_primitive


class StubConnector(SaaSConnector):
    name = "stub"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return f"https://stub.example/oauth?state={state}&redirect_uri={redirect_uri}"

    def exchange_code(self, code: str, redirect_uri: str) -> str:
        return f"stub-token-{code}"

    def fetch(self, access_token: str) -> dict[str, Any]:
        # Deterministic "tenant data": customer firm count + ARR.
        return {"customers": 4200, "arr_usd": 12_000_000.0}

    def to_private_primitives(self, org_id: str, raw: dict[str, Any]) -> list[AtomicPrimitive]:
        as_of = date(2024, 12, 31)
        return [
            make_private_primitive(
                org_id=org_id,
                provider=self.name,
                slug_stub="customer-firms",
                concept_slug="demo-ai-sales-ops-us",
                name="Tenant customer firm count (private)",
                value=float(raw["customers"]),
                unit={"kind": "stock", "dimension": "organizations"},
                as_of=as_of,
            ),
            make_private_primitive(
                org_id=org_id,
                provider=self.name,
                slug_stub="arr",
                concept_slug="demo-ai-sales-ops-us",
                name="Tenant ARR (private)",
                value=float(raw["arr_usd"]),
                unit={
                    "kind": "intensive",
                    "dimension": "currency",
                    "denominator": "per-firm-per-year",
                    "currency": "USD",
                    "basis": "nominal",
                },
                as_of=as_of,
            ),
        ]
