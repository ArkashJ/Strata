"""Admin cross-org feedback governance (Pillar A).

The non-DB tests (the ``is_admin`` gate, the shared-bank fence, the tool 403/
no-tenant envelopes) run anywhere. The CRUD/RLS paths need a live Postgres
migrated to head (cross-org read + promote); skipped when PG is unreachable,
exactly like ``test_feedback.py``.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from strata.api.auth import Principal, is_admin
from strata.config import settings
from strata.db.feedback import record_feedback
from strata.guards.fence import (
    ModeledFenceError,
    validate_and_fence_shared_primitive,
)
from strata.models.feedback import FeedbackKind, FeedbackStatus, TargetType

_ADMIN_ORG = "clerk_org:strata-ops"
_TENANT_A = "clerk_user:adm_a"
_TENANT_B = "clerk_user:adm_b"


def _sourced_primitive(slug: str = "adm-test-headcount-2024") -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "demo-ai-sales-ops-us",
        "name": "Corrected headcount",
        "description": "A corrected private primitive.",
        "value": 654321,
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": "2024-12-31",
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": {
            "slug": "adm-src",
            "tier": "regulator",
            "url": "https://www.bls.gov/x",
            "accessed": "2026-05-30",
            "snapshot_sha256": "b" * 64,
        },
    }


def _modeled_primitive(slug: str = "adm-test-modeled-2024") -> dict[str, Any]:
    p = _sourced_primitive(slug)
    p["source"] = {**p["source"], "tier": "community-modeled"}
    return p


# --------------------------------------------------------------------------- #
# is_admin gate — pure, no DB.                                                 #
# --------------------------------------------------------------------------- #


def test_is_admin_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_orgs", f"{_ADMIN_ORG}, other-admin")
    assert is_admin(Principal(org_id=_ADMIN_ORG, key_id="k", scopes=("*",))) is True
    assert is_admin(Principal(org_id="other-admin", key_id="k", scopes=("*",))) is True
    # A normal tenant is never admin.
    assert is_admin(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",))) is False


def test_is_admin_rejects_anonymous_and_public(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if "public" were misconfigured onto the allowlist, the anonymous/public
    # guard refuses it (defense in depth).
    monkeypatch.setattr(settings, "admin_orgs", "public")
    assert is_admin(Principal(org_id="public", key_id="anonymous", scopes=("read",))) is False
    assert is_admin(Principal(org_id="public", key_id="clerk:x", scopes=("*",))) is False
    assert is_admin(None) is False


def test_is_admin_empty_allowlist_means_no_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_orgs", "")
    assert is_admin(Principal(org_id=_ADMIN_ORG, key_id="k", scopes=("*",))) is False


# --------------------------------------------------------------------------- #
# Shared-bank fence — pure, no DB. Q20 holds at the shared door.               #
# --------------------------------------------------------------------------- #


def test_shared_fence_promotes_sourced_as_public() -> None:
    shared = validate_and_fence_shared_primitive(_sourced_primitive())
    assert shared["visibility"] == "public"
    assert shared.get("org_id") is None
    assert shared["slug"] == "adm-test-headcount-2024"


def test_shared_fence_strips_private_org() -> None:
    # An org-private payload (visibility=private + org_id) is promoted to public.
    payload = {**_sourced_primitive(), "visibility": "private", "org_id": _TENANT_A}
    shared = validate_and_fence_shared_primitive(payload)
    assert shared["visibility"] == "public"
    assert shared.get("org_id") is None


def test_shared_fence_refuses_modeled() -> None:
    with pytest.raises(ModeledFenceError):
        validate_and_fence_shared_primitive(_modeled_primitive())


# --------------------------------------------------------------------------- #
# Admin tool envelopes — gate without a DB.                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_admin_tool_no_tenant_over_stdio() -> None:
    """No principal (local stdio) → honest no_tenant, never a cross-org leak."""
    from strata.mcp.admin_tools import admin_list_feedback

    out = await admin_list_feedback(None)  # type: ignore[arg-type]
    assert out["error"] == "no_tenant"


@pytest.mark.asyncio
async def test_admin_tool_forbidden_for_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-admin authenticated org is refused before any cross-org read."""
    from strata.mcp import context
    from strata.mcp.admin_tools import admin_list_feedback, admin_promote_correction

    monkeypatch.setattr(settings, "admin_orgs", _ADMIN_ORG)
    token = context.current_principal.set(
        Principal(org_id=_TENANT_A, key_id="key_a", scopes=("*",))
    )
    try:
        out = await admin_list_feedback(None)  # type: ignore[arg-type]
        assert out["error"] == "forbidden"
        out2 = await admin_promote_correction(None, feedback_id=1)  # type: ignore[arg-type]
        assert out2["error"] == "forbidden"
    finally:
        context.current_principal.reset(token)


# --------------------------------------------------------------------------- #
# DB-backed cross-org governance.                                             #
# --------------------------------------------------------------------------- #


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
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback_events'"
        )
        if not has:
            return
        has_prims = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_primitives'"
        )
        for org in (_TENANT_A, _TENANT_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute("DELETE FROM feedback_events WHERE org_id = $1", org)
                if has_prims:
                    await conn.execute("DELETE FROM user_primitives WHERE org_id = $1", org)
    finally:
        await conn.close()


@pytest.fixture
async def _clean() -> Any:
    await _cleanup()
    yield
    await _cleanup()


@_PG
@pytest.mark.asyncio
async def test_admin_list_feedback_sees_every_org(_clean: None) -> None:
    """An admin session reads flags across ALL tenants; a tenant session does not."""
    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.feedback import admin_list_feedback
    from strata.db.feedback import list_feedback as tenant_list

    async with org_session_scope(_TENANT_A) as s:
        await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.BAD_ASSUMPTION,
            target_type=TargetType.TAM,
            body="A's flag",
        )
    async with org_session_scope(_TENANT_B) as s:
        await record_feedback(
            s,
            org_id=_TENANT_B,
            user_id=None,
            kind=FeedbackKind.MISSING_DATA,
            target_type=TargetType.QUERY,
            body="B's flag",
        )

    async with admin_session_scope("cli-admin") as s:
        rows = await admin_list_feedback(s)
        orgs = {r.org_id for r in rows}
        assert _TENANT_A in orgs and _TENANT_B in orgs

        only_b = await admin_list_feedback(s, org_id=_TENANT_B)
        assert {r.org_id for r in only_b} == {_TENANT_B}

    # A tenant session still sees only its own (isolation intact).
    async with org_session_scope(_TENANT_A) as s:
        a_rows = await tenant_list(s, org_id=_TENANT_A)
        assert {r.org_id for r in a_rows} == {_TENANT_A}


@pytest.fixture(scope="module")
def reg() -> Any:
    from pathlib import Path

    from strata.loader import load_data_dir
    from strata.registry import Registry

    return Registry.from_loaded(load_data_dir(Path(__file__).resolve().parents[2] / "data"))


@_PG
@pytest.mark.asyncio
async def test_whoami_admin_sees_open_corrections(
    reg: Any, _clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An admin caller's whoami carries the open primitive_correction backlog
    count; a noise-quarantined or resolved flag does not inflate it."""
    import inspect

    from strata.db.engine import org_session_scope
    from strata.mcp import context
    from strata.mcp.tools import _h_whoami

    monkeypatch.setattr(settings, "admin_orgs", _ADMIN_ORG)
    async with org_session_scope(_TENANT_A) as s:
        await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="headcount looks stale",
        )

    token = context.current_principal.set(Principal(org_id=_ADMIN_ORG, key_id="k", scopes=("*",)))
    try:
        res = _h_whoami(reg, {})
        assert inspect.isawaitable(res)
        out = await res
    finally:
        context.current_principal.reset(token)
    assert out["ok"] is True
    assert out["open_corrections"] >= 1


def test_whoami_non_admin_has_no_backlog(reg: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-admin (or stdio) caller keeps the synchronous, DB-free whoami —
    the backlog count is an admin-only field."""
    from strata.mcp import context
    from strata.mcp.tools import _h_whoami

    monkeypatch.setattr(settings, "admin_orgs", _ADMIN_ORG)
    token = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        out = _h_whoami(reg, {})
        assert isinstance(out, dict)
        assert "open_corrections" not in out
    finally:
        context.current_principal.reset(token)
    # stdio: no principal at all → same sync path.
    out = _h_whoami(reg, {})
    assert isinstance(out, dict)
    assert "open_corrections" not in out


@_PG
@pytest.mark.asyncio
async def test_admin_list_feedback_correction_path(
    _clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """primitive_correction rows carry a correction_path: the apply→promote→CLI
    chain when a promotable payload exists, a submit_feedback template when not.
    Other kinds carry none."""
    from strata.db.engine import org_session_scope
    from strata.mcp import context
    from strata.mcp.admin_tools import admin_list_feedback as mcp_admin_list

    monkeypatch.setattr(settings, "admin_orgs", _ADMIN_ORG)
    async with org_session_scope(_TENANT_A) as s:
        with_payload = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="corrected headcount attached",
            suggested_value=_sourced_primitive("adm-path-with-payload"),
        )
        without_payload = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            target_id="some-flagged-slug",
            body="this number looks wrong",
        )
        commentary = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.BAD_ASSUMPTION,
            target_type=TargetType.TAM,
            body="adoption looks aggressive",
        )

    token = context.current_principal.set(Principal(org_id=_ADMIN_ORG, key_id="k", scopes=("*",)))
    try:
        out = await mcp_admin_list(None, org_id=_TENANT_A)  # type: ignore[arg-type]
    finally:
        context.current_principal.reset(token)
    by_id = {r["id"]: r for r in out["feedback"]}

    path = by_id[with_payload.id]["correction_path"]
    assert [step.get("tool", step.get("cli")) for step in path] == [
        "apply_feedback",
        "admin_promote_correction",
        f"strata admin promote {with_payload.id}",
    ]
    assert path[0]["arguments"] == {"feedback_id": with_payload.id}

    template = by_id[without_payload.id]["correction_path"]
    assert len(template) == 1
    assert template[0]["tool"] == "submit_feedback"
    payload = template[0]["arguments"]["payload"]
    assert payload["target_id"] == "some-flagged-slug"
    assert "suggested_value" in payload  # shows exactly what a promotable correction needs

    assert "correction_path" not in by_id[commentary.id]


# --------------------------------------------------------------------------- #
# `strata admin correct` — the operator's correction loop.                     #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_admin_correct_org_private_happy_path(_clean: None, tmp_path: Any) -> None:
    """Default mode applies the correction ORG-PRIVATE via the existing apply
    path: primitive created under the flag's own org, flag resolved + linked."""
    from strata.cli import _admin_correct_run
    from strata.db.engine import org_session_scope
    from strata.db.feedback import list_feedback
    from strata.db.user_primitives import list_user_primitives

    async with org_session_scope(_TENANT_A) as s:
        ev = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="corrected headcount attached",
            suggested_value=_sourced_primitive("adm-correct-private"),
        )
        fid = ev.id

    outcome = await _admin_correct_run(
        fid, payload=None, shared=False, data_dir=tmp_path, assume_yes=True
    )
    assert outcome["mode"] == "org-private"
    assert outcome["org_id"] == _TENANT_A
    assert outcome["slug"] == "adm-correct-private"
    assert outcome["status"] == "resolved"

    async with org_session_scope(_TENANT_A) as s:
        prims = await list_user_primitives(s, org_id=_TENANT_A)
        assert any(p.slug == "adm-correct-private" and p.visibility == "private" for p in prims)
        rows = await list_feedback(s, org_id=_TENANT_A)
        assert rows[0].status is FeedbackStatus.RESOLVED
        assert rows[0].resolved_primitive_id is not None


@_PG
@pytest.mark.asyncio
async def test_admin_correct_shared_happy_path(_clean: None, tmp_path: Any) -> None:
    """--shared promotes through the existing fence and writes the committable
    data/primitives/<slug>.yaml into the given data dir."""
    import yaml

    from strata.cli import _admin_correct_run
    from strata.db.engine import org_session_scope

    async with org_session_scope(_TENANT_A) as s:
        ev = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="corrected headcount attached",
            suggested_value=_sourced_primitive("adm-correct-shared"),
        )
        fid = ev.id

    outcome = await _admin_correct_run(
        fid, payload=None, shared=True, data_dir=tmp_path, assume_yes=True
    )
    assert outcome["mode"] == "shared"
    written = tmp_path / "primitives" / "adm-correct-shared.yaml"
    assert written.exists()
    shared = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert shared["visibility"] == "public"
    assert shared.get("org_id") is None


@_PG
@pytest.mark.asyncio
async def test_admin_correct_shared_refuses_modeled(_clean: None, tmp_path: Any) -> None:
    """--shared on a modeled-tier correction is refused by the EXISTING shared
    fence (Q20) — the flag stays open, the payload stays intact (never deleted),
    and nothing lands in the shared data dir."""
    from strata.cli import _admin_correct_run
    from strata.db.engine import org_session_scope
    from strata.db.feedback import list_feedback

    async with org_session_scope(_TENANT_A) as s:
        ev = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="proposed (modeled) correction",
            suggested_value=_modeled_primitive("adm-correct-modeled"),
        )
        fid = ev.id

    with pytest.raises(ModeledFenceError):
        await _admin_correct_run(fid, payload=None, shared=True, data_dir=tmp_path, assume_yes=True)

    assert not (tmp_path / "primitives" / "adm-correct-modeled.yaml").exists()
    async with org_session_scope(_TENANT_A) as s:
        rows = await list_feedback(s, org_id=_TENANT_A)
        assert rows[0].status is FeedbackStatus.OPEN
        assert rows[0].suggested_value is not None  # feedback is never deleted


@_PG
@pytest.mark.asyncio
async def test_admin_promote_correction_returns_shared_yaml(_clean: None) -> None:
    """Promote an applied org-private correction → public YAML, flag resolved,
    and the modeled fence still blocks soft data at the shared door."""
    import yaml

    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.feedback import (
        admin_correction_payload,
        admin_get_feedback_row,
        apply_feedback_correction,
    )

    # Tenant A files + applies a sourced correction (creates an org-private primitive).
    async with org_session_scope(_TENANT_A) as s:
        ev = await record_feedback(
            s,
            org_id=_TENANT_A,
            user_id=None,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="corrected headcount",
            suggested_value=_sourced_primitive(),
        )
        fid = ev.id
    async with org_session_scope(_TENANT_A) as s:
        await apply_feedback_correction(s, fid, org_id=_TENANT_A)

    # Admin reads the correction cross-org and promotes it to the shared bank.
    async with admin_session_scope("cli-admin") as s:
        row = await admin_get_feedback_row(s, fid)
        assert row is not None and row.org_id == _TENANT_A
        payload = await admin_correction_payload(s, row)
        assert payload is not None
        shared = validate_and_fence_shared_primitive(payload)
        assert shared["visibility"] == "public"
        assert shared.get("org_id") is None
        # round-trips as YAML (what the CLI writes to data/primitives/)
        assert yaml.safe_load(yaml.safe_dump(shared))["slug"] == "adm-test-headcount-2024"
        row.status = FeedbackStatus.RESOLVED.value
        await s.flush()

    # The resolution persisted cross-org.
    async with admin_session_scope("cli-admin") as s:
        row = await admin_get_feedback_row(s, fid)
        assert row is not None and row.status == FeedbackStatus.RESOLVED.value
