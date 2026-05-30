"""OAuth integration routes (Wave 5B). All org-scoped via the request Principal:
authorize → callback (store encrypted token) → sync (fetch → private primitives)
→ disconnect (purge tokens + tombstone private primitives)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.auth import Principal, require_principal
from strata.connectors.saas.crypto import get_vault
from strata.connectors.saas.providers import get_connector, provider_names
from strata.connectors.saas.store import get_store

router = APIRouter(prefix="/integrations", tags=["integrations"])

_PRINCIPAL = Depends(require_principal)


class AuthorizeResponse(BaseModel):
    provider: str
    authorize_url: str


class SyncResponse(BaseModel):
    provider: str
    org_id: str
    primitives_added: int


class DisconnectResponse(BaseModel):
    provider: str
    org_id: str
    tokens_purged: bool
    primitives_purged: int


def _connector_or_404(provider: str):
    connector = get_connector(provider)
    if connector is None:
        raise HTTPException(404, f"unknown provider {provider!r}; known: {provider_names()}")
    return connector


@router.get("/{provider}/authorize", response_model=AuthorizeResponse)
async def authorize(
    provider: str, redirect_uri: str = "", principal: Principal = _PRINCIPAL
) -> AuthorizeResponse:
    connector = _connector_or_404(provider)
    # The org_id is the OAuth state so the callback knows which tenant to bind.
    url = connector.authorize_url(state=principal.org_id, redirect_uri=redirect_uri)
    return AuthorizeResponse(provider=provider, authorize_url=url)


@router.get("/{provider}/callback")
async def callback(
    provider: str, code: str, redirect_uri: str = "", principal: Principal = _PRINCIPAL
) -> dict[str, str]:
    connector = _connector_or_404(provider)
    try:
        access_token = connector.exchange_code(code, redirect_uri)
    except Exception as exc:  # provider error — don't leak internals
        raise HTTPException(502, "OAuth token exchange failed") from exc
    # Stored ENCRYPTED + scoped to org_id (AC5B.1).
    get_vault().store(principal.org_id, provider, access_token)
    return {"status": "connected", "provider": provider, "org_id": principal.org_id}


@router.post("/{provider}/sync", response_model=SyncResponse)
async def sync(provider: str, principal: Principal = _PRINCIPAL) -> SyncResponse:
    connector = _connector_or_404(provider)
    stored = get_vault().get(principal.org_id, provider)
    if stored is None:
        raise HTTPException(409, f"{provider} not connected for this org")
    raw = connector.fetch(stored.reveal())
    primitives = connector.to_private_primitives(principal.org_id, raw)
    get_store().add(principal.org_id, provider, primitives)
    return SyncResponse(
        provider=provider, org_id=principal.org_id, primitives_added=len(primitives)
    )


@router.delete("/{provider}", response_model=DisconnectResponse)
async def disconnect(provider: str, principal: Principal = _PRINCIPAL) -> DisconnectResponse:
    _connector_or_404(provider)
    purged_tokens = get_vault().purge(principal.org_id, provider)
    purged_primitives = get_store().purge(principal.org_id, provider)
    return DisconnectResponse(
        provider=provider,
        org_id=principal.org_id,
        tokens_purged=purged_tokens,
        primitives_purged=purged_primitives,
    )
