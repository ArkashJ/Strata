"""Generic inbound SaaS connector framework (Wave 5B / AC5B.5).

A provider plugs in by subclassing ``SaaSConnector`` and supplying an
object->primitive mapping — no core changes. Each connector turns a tenant's
connected data into **private, org-scoped, first-party** ``AtomicPrimitive``s.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from ...models import AtomicPrimitive


class SaaSConnector(ABC):
    """Provider contract. Concrete connectors implement the four steps; the
    routes + store handle OAuth persistence, isolation, and the evaluator feed."""

    name: str

    @abstractmethod
    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """The provider's OAuth consent URL to redirect the user to."""

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> str:
        """Exchange an auth code for an access token (provider HTTP call)."""

    @abstractmethod
    def fetch(self, access_token: str) -> dict[str, Any]:
        """Fetch the raw tenant data needed for the mapped primitives."""

    @abstractmethod
    def to_private_primitives(self, org_id: str, raw: dict[str, Any]) -> list[AtomicPrimitive]:
        """Normalize raw data into private, org-scoped first-party primitives."""


def make_private_primitive(
    *,
    org_id: str,
    provider: str,
    slug_stub: str,
    concept_slug: str,
    name: str,
    value: float,
    unit: dict[str, Any],
    as_of: date,
) -> AtomicPrimitive:
    """Build a private first-party primitive. Slug is org-namespaced so two
    tenants' same metric never collide, and it can never shadow a public slug."""
    return AtomicPrimitive.model_validate(
        {
            "kind": "atomic_primitive",
            "slug": f"private-{org_id}-{provider}-{slug_stub}",
            "schema_version": 1,
            "concept_slug": concept_slug,
            "name": name,
            "description": f"Private first-party measurement from {provider} for org {org_id}.",
            "value": value,
            "unit": unit,
            "as_of": as_of.isoformat(),
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "supply",
            "distribution_shape": "normal",
            "delivery_mode": "n/a",
            "source": {
                "slug": f"private-{org_id}-{provider}-src",
                "tier": "first_party",
                "url": f"https://{provider}.com/",
                "accessed": as_of.isoformat(),
                "snapshot_sha256": "f1" * 32,
            },
            "visibility": "private",
            "org_id": org_id,
        }
    )
