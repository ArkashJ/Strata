"""PR 1 / U6 — per-user PRIVATE primitive CRUD (``/me/primitives``).

Server-authoritative honesty fences:
- POST/PATCH force ``visibility=private`` + the caller's ``org_id`` even when the
  body claims public / another org.
- the MODELED fence rejects (422) a soft-tier (community-modeled / analyst)
  primitive — the private bank stores sourced output only (Q20).
- GET/PATCH/DELETE are RLS-scoped: a second tenant sees / touches none of the
  first tenant's rows.
- promote routes into the ``/contribute`` review queue (needs_review), never a
  direct public write.
- every verb is 401 for an anonymous caller (``require_authenticated``).

The CRUD/RLS paths need a live Postgres migrated to head; skipped when PG is
unreachable so keyless CI stays green. The Clerk verifier is stubbed (the bridge
itself is unit-tested in ``test_auth_clerk_bridge`` / ``test_clerk_auth``); the
anonymous-401 checks do not need Postgres and always run.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api import auth
from strata.api.app import create_app
from strata.api.clerk_auth import ClerkClaims
from strata.config import settings

_USER_A = "user_me_a"
_USER_B = "user_me_b"
_ORG_A = f"clerk_user:{_USER_A}"
_ORG_B = f"clerk_user:{_USER_B}"

_BEARER_A = {"Authorization": "Bearer token.a"}
_BEARER_B = {"Authorization": "Bearer token.b"}


def _sourced_primitive(slug: str = "me-test-headcount-2024") -> dict[str, Any]:
    """A valid REGULATOR-tier primitive (provenance derives to sourced)."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "demo-ai-sales-ops-us",
        "name": "My private headcount",
        "description": "A private primitive.",
        "value": 123456,
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": "2024-12-31",
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": {
            "slug": "me-src",
            "tier": "regulator",
            "url": "https://www.bls.gov/x",
            "accessed": "2026-05-30",
            "snapshot_sha256": "a" * 64,
        },
    }


def _modeled_primitive(slug: str = "me-test-modeled-2024") -> dict[str, Any]:
    """A COMMUNITY-MODELED estimate — provenance derives to modeled (fence 422)."""
    p = _sourced_primitive(slug)
    p["source"] = {**p["source"], "tier": "community-modeled"}
    return p


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


_PG = pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")


def _asyncpg_dsn() -> str:
    return str(settings.database_url).replace("+asyncpg", "")


async def _cleanup() -> None:
    import asyncpg

    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        has = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_primitives'"
        )
        if not has:
            return
        for org in (_ORG_A, _ORG_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute("DELETE FROM user_primitives WHERE org_id = $1", org)
                await conn.execute("DELETE FROM contributions WHERE org_id = $1", org)
    finally:
        await conn.close()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def stub_clerk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Map each Bearer token to its test user (token.a → A, anything else → B)."""

    def _verify(token: str) -> ClerkClaims:
        if token == "token.a":
            return ClerkClaims(sub=_USER_A, org_id=None, raw={})
        return ClerkClaims(sub=_USER_B, org_id=None, raw={})

    monkeypatch.setattr(auth, "verify_clerk_jwt", _verify)


@pytest.fixture
async def _clean():
    await _cleanup()
    yield
    await _cleanup()
    # Dispose the module-level engine's pool inside THIS test's loop so no asyncpg
    # connection survives into the next test's (fresh) loop — asyncpg's graceful
    # close otherwise fires on a closed loop ("Event loop is closed").
    from strata.db.engine import engine

    await engine.dispose()


# --------------------------------------------------------------------------- #
# Anonymous → 401 on every verb (no Postgres needed).                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_anonymous_is_401_on_every_verb(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    assert (await client.get("/me/primitives")).status_code == 401
    assert (
        await client.post("/me/primitives", json={"payload": _sourced_primitive()})
    ).status_code == 401
    assert (
        await client.patch("/me/primitives/x", json={"payload": _sourced_primitive()})
    ).status_code == 401
    assert (await client.delete("/me/primitives/x")).status_code == 401
    assert (await client.post("/me/primitives/x/promote")).status_code == 401


# --------------------------------------------------------------------------- #
# MODELED fence does not need Postgres — it rejects before persistence.        #
# (Run only with PG so the request reaches the route under a real org scope.)  #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_modeled_fence_rejects_soft_tier(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    r = await client.post(
        "/me/primitives", headers=_BEARER_A, json={"payload": _modeled_primitive()}
    )
    assert r.status_code == 422, r.text


@_PG
@pytest.mark.asyncio
async def test_post_forces_private_and_org(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    """A body claiming public / another org is overridden to private + caller org."""
    body = _sourced_primitive()
    body["visibility"] = "public"
    body["org_id"] = "clerk_user:someone_else"
    r = await client.post("/me/primitives", headers=_BEARER_A, json={"payload": body})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["visibility"] == "private"
    assert out["org_id"] == _ORG_A
    assert out["created_by"] == _USER_A
    assert out["payload"]["visibility"] == "private"
    assert out["payload"]["org_id"] == _ORG_A


@_PG
@pytest.mark.asyncio
async def test_get_patch_delete_are_rls_scoped(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    """Tenant A's primitive is invisible / untouchable to tenant B."""
    slug = "me-test-headcount-2024"
    created = await client.post(
        "/me/primitives", headers=_BEARER_A, json={"payload": _sourced_primitive(slug)}
    )
    assert created.status_code == 201, created.text

    # A sees its own row; B sees none of A's.
    a_list = (await client.get("/me/primitives", headers=_BEARER_A)).json()
    assert {p["slug"] for p in a_list} == {slug}
    b_list = (await client.get("/me/primitives", headers=_BEARER_B)).json()
    assert b_list == []

    # B cannot PATCH or DELETE A's slug (404 under B's scope).
    patched_by_b = await client.patch(
        f"/me/primitives/{slug}", headers=_BEARER_B, json={"payload": _sourced_primitive(slug)}
    )
    assert patched_by_b.status_code == 404
    assert (await client.delete(f"/me/primitives/{slug}", headers=_BEARER_B)).status_code == 404

    # A can PATCH its own (new value persists).
    body = _sourced_primitive(slug)
    body["value"] = 999.0
    patched = await client.patch(
        f"/me/primitives/{slug}", headers=_BEARER_A, json={"payload": body}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["payload"]["value"] == 999.0

    # A can DELETE its own; a second delete is 404.
    assert (await client.delete(f"/me/primitives/{slug}", headers=_BEARER_A)).status_code == 204
    assert (await client.delete(f"/me/primitives/{slug}", headers=_BEARER_A)).status_code == 404


@_PG
@pytest.mark.asyncio
async def test_promote_routes_to_review_queue_not_public(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    """promote creates a needs_review contribution row, not a public primitive."""
    slug = "me-test-headcount-2024"
    assert (
        await client.post(
            "/me/primitives", headers=_BEARER_A, json={"payload": _sourced_primitive(slug)}
        )
    ).status_code == 201

    promoted = await client.post(f"/me/primitives/{slug}/promote", headers=_BEARER_A)
    assert promoted.status_code == 200, promoted.text
    out = promoted.json()
    assert out["status"] == "needs_review"
    assert out["contribution_id"] is not None

    # It landed in the review queue (migration 004 contributions), attributed to A.
    import asyncpg

    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        row = await conn.fetchrow(
            "SELECT org_id, kind, status FROM contributions WHERE id = $1",
            out["contribution_id"],
        )
    finally:
        await conn.close()
    assert row is not None
    assert row["org_id"] == _ORG_A
    assert row["kind"] == "atomic_primitive"
    assert row["status"] == "needs_review"

    # The primitive stays PRIVATE (promote never writes public) — still in A's bank.
    a_list = (await client.get("/me/primitives", headers=_BEARER_A)).json()
    assert {p["slug"] for p in a_list} == {slug}


@_PG
@pytest.mark.asyncio
async def test_promote_unknown_slug_is_404(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    assert (await client.post("/me/primitives/nope/promote", headers=_BEARER_A)).status_code == 404
