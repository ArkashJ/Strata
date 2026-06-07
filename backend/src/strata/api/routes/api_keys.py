"""Self-serve API-key management (``/me/api-keys``) — PR / agent connector.

A signed-in VC mints a key here, then pastes it into Claude as the Bearer
credential for the hosted ``/mcp`` connector. Every verb requires a real
(non-anonymous) principal, and a caller only ever sees or revokes keys for its
own ``org_id``. The raw secret is returned exactly once, at mint.

    POST   /me/api-keys        → { key: "strata_sk_live_…" (ONCE), key_id, … }
    GET    /me/api-keys        → [ { key_id, label, prefix, last_used_at } … ]
    DELETE /me/api-keys/{id}   → 204 (key stops authenticating immediately)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from strata.api.auth import Principal, hash_key, register_hashed, require_authenticated, unregister
from strata.api.responses import UNAUTHORIZED
from strata.db.api_keys import ApiKeyRecord, list_for_org, mint, revoke
from strata.db.engine import session_scope

router = APIRouter(prefix="/me/api-keys", tags=["api-keys"])

_AUTH = Depends(require_authenticated)


class CreateKeyRequest(BaseModel):
    label: str = Field(
        default="",
        max_length=200,
        description="A human name for the key, e.g. 'Claude Desktop' or 'research laptop'.",
    )


class ApiKeyOut(BaseModel):
    """A key as shown to its owner — never the secret or its hash."""

    key_id: str
    label: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None

    @classmethod
    def of(cls, r: ApiKeyRecord) -> ApiKeyOut:
        return ApiKeyOut(
            key_id=r.key_id,
            label=r.label,
            prefix=r.prefix,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )


class CreatedKeyOut(ApiKeyOut):
    """Mint response — carries the one-time raw secret in ``key``."""

    key: str = Field(
        description="The full secret. Shown ONCE — copy it now; it is not recoverable."
    )

    @classmethod
    def with_secret(cls, r: ApiKeyRecord, raw: str) -> CreatedKeyOut:
        return cls(
            key=raw,
            key_id=r.key_id,
            label=r.label,
            prefix=r.prefix,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )


@router.post(
    "",
    response_model=CreatedKeyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an API key",
    description=(
        "Mint a key scoped to the caller's org. The raw secret is returned once "
        "and never stored — copy it immediately. Use it as the Bearer token for "
        "the hosted MCP connector."
    ),
    responses=UNAUTHORIZED,
)
async def create_key(body: CreateKeyRequest, principal: Principal = _AUTH) -> CreatedKeyOut:
    async with session_scope() as session:
        raw, record = await mint(
            session, org_id=principal.org_id, label=body.label, created_by=principal.user_id
        )
    # Usable immediately in this process — no wait for a cache reload.
    register_hashed(hash_key(raw), principal.org_id, key_id=record.key_id)
    return CreatedKeyOut.with_secret(record, raw)


@router.get(
    "",
    response_model=list[ApiKeyOut],
    summary="List my API keys",
    description="Active (non-revoked) keys for the caller's org. Secrets are never returned.",
    responses=UNAUTHORIZED,
)
async def list_keys(principal: Principal = _AUTH) -> list[ApiKeyOut]:
    async with session_scope() as session:
        records = await list_for_org(session, principal.org_id)
    return [ApiKeyOut.of(r) for r in records]


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
    description="Revoke a key the caller owns. It stops authenticating immediately.",
    responses=UNAUTHORIZED,
)
async def delete_key(key_id: str, principal: Principal = _AUTH) -> Response:
    async with session_scope() as session:
        key_hash = await revoke(session, org_id=principal.org_id, key_id=key_id)
    if key_hash is None:
        raise HTTPException(status_code=404, detail="no such key for this org")
    unregister(key_hash)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
