"""Provider registry (Wave 5B). Adding a provider is one entry here + a
``SaaSConnector`` subclass — no route or core changes (AC5B.5)."""

from __future__ import annotations

from ...config import settings
from .base import SaaSConnector
from .hubspot import HubSpotConnector
from .stub import StubConnector

_PROVIDERS: dict[str, SaaSConnector] = {
    "hubspot": HubSpotConnector(
        client_id=getattr(settings, "hubspot_client_id", "") or "",
        client_secret=getattr(settings, "hubspot_client_secret", "") or "",
    ),
    "stub": StubConnector(),
}


def get_connector(provider: str) -> SaaSConnector | None:
    return _PROVIDERS.get(provider)


def provider_names() -> list[str]:
    return sorted(_PROVIDERS)
