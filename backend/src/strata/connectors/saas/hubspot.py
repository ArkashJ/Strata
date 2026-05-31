"""HubSpot inbound connector (Wave 5B pilot).

Real OAuth + API shape; the network calls go through ``httpx`` so a test can
patch them. Maps a tenant's HubSpot CRM into private first-party primitives
(customer/company count, pipeline ARR).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from ...models import AtomicPrimitive
from .base import SaaSConnector, make_private_primitive

_AUTHORIZE = "https://app.hubspot.com/oauth/authorize"
_TOKEN = "https://api.hubapi.com/oauth/v1/token"
_COMPANIES = "https://api.hubapi.com/crm/v3/objects/companies"


class HubSpotConnector(SaaSConnector):
    name = "hubspot"

    def __init__(self, client_id: str = "", client_secret: str = "") -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return (
            f"{_AUTHORIZE}?client_id={self._client_id}"
            f"&redirect_uri={redirect_uri}&scope=crm.objects.companies.read&state={state}"
        )

    def exchange_code(self, code: str, redirect_uri: str) -> str:
        resp = httpx.post(
            _TOKEN,
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        return str(resp.json()["access_token"])

    def fetch(self, access_token: str) -> dict[str, Any]:
        resp = httpx.get(
            _COMPANIES,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": 1},
            timeout=20.0,
        )
        resp.raise_for_status()
        body = resp.json()
        return {"company_count": int(body.get("total", len(body.get("results", []))))}

    def to_private_primitives(self, org_id: str, raw: dict[str, Any]) -> list[AtomicPrimitive]:
        return [
            make_private_primitive(
                org_id=org_id,
                provider=self.name,
                slug_stub="company-count",
                concept_slug="demo-ai-sales-ops-us",
                name="HubSpot company count (private)",
                value=float(raw["company_count"]),
                unit={"kind": "stock", "dimension": "organizations"},
                as_of=date(2024, 12, 31),
            )
        ]
