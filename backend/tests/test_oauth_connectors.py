"""Wave 5B — inbound OAuth connectors -> private, org-scoped primitives.

AC5B.1 encrypted+scoped tokens · AC5B.2 isolation · AC5B.3 evaluator feed +
private banner · AC5B.4 disconnect purge · AC5B.5 generic (2nd provider).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.auth import _KEY_STORE, hash_key, register_key
from strata.connectors.saas.base import SaaSConnector
from strata.connectors.saas.crypto import get_vault
from strata.connectors.saas.hubspot import HubSpotConnector
from strata.connectors.saas.providers import get_connector
from strata.connectors.saas.store import get_store, org_scoped_registry
from strata.connectors.saas.stub import StubConnector
from strata.evaluator.engine import EvalOverrides, size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"
_CONCEPT = "demo-ai-sales-ops-us"


@pytest.fixture(autouse=True)
def _reset():
    get_store().reset()
    yield
    get_store().reset()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── AC5B.1 — encrypted, org-scoped token ──────────────────────────────────


def test_oauth_token_scoped_encrypted() -> None:
    vault = get_vault()
    stored = vault.store("org-a", "stub", "super-secret-token")
    # Stored ciphertext is not the plaintext; only the org's slot holds it.
    assert b"super-secret-token" not in stored.ciphertext
    assert stored.reveal() == "super-secret-token"
    assert vault.get("org-a", "stub") is not None
    assert vault.get("org-b", "stub") is None  # scoped to org-a only
    vault.purge("org-a", "stub")


def _state_from(url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(url).query)["state"][0]


@pytest.mark.asyncio
async def test_oauth_flow_requires_auth_and_valid_state(client: AsyncClient) -> None:
    register_key("oauth-key", "org-z")
    headers = {"X-API-Key": "oauth-key"}
    try:
        # Anonymous (no key) is rejected on a tenant-secret route.
        anon = await client.get("/integrations/stub/authorize")
        assert anon.status_code == 401

        # Authorize mints a CSRF state bound to org-z.
        authz = await client.get("/integrations/stub/authorize", headers=headers)
        assert authz.status_code == 200
        state = _state_from(authz.json()["authorize_url"])

        # A forged/missing state is rejected.
        bad = await client.get(
            "/integrations/stub/callback",
            params={"code": "abc", "state": "forged"},
            headers=headers,
        )
        assert bad.status_code == 400

        # The real state completes the flow and stores an encrypted, org-scoped token.
        ok = await client.get(
            "/integrations/stub/callback",
            params={"code": "abc", "state": state},
            headers=headers,
        )
        assert ok.status_code == 200
        stored = get_vault().get("org-z", "stub")
        assert stored is not None and stored.reveal() == "stub-token-abc"
    finally:
        get_vault().purge("org-z", "stub")
        _KEY_STORE.pop(hash_key("oauth-key"), None)


# ── AC5B.2 — private primitive isolated per org ───────────────────────────


def test_private_primitive_isolated() -> None:
    conn = StubConnector()
    get_store().add("org-a", "stub", conn.to_private_primitives("org-a", conn.fetch("t")))
    assert len(get_store().for_org("org-a")) == 2
    assert get_store().for_org("org-b") == []  # cross-tenant read = 0


def test_private_primitives_excluded_from_public_registry() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    conn = StubConnector()
    get_store().add("org-a", "stub", conn.to_private_primitives("org-a", conn.fetch("t")))
    # The public registry never contains private slugs.
    assert not any(s.startswith("private-") for s in reg.atomic)
    org_reg = org_scoped_registry(reg, "org-a", get_store())
    assert any(s.startswith("private-org-a-") for s in org_reg.atomic)


# ── AC5B.3 — feeds the same evaluator + private banner ────────────────────


def test_private_primitive_feeds_evaluator() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    conn = StubConnector()
    get_store().add("org-a", "stub", conn.to_private_primitives("org-a", conn.fetch("t")))
    org_reg = org_scoped_registry(reg, "org-a", get_store())

    # Re-point the top-down org-count input to the tenant's private firm count.
    private_slug = "private-org-a-stub-customer-firms"
    overrides = EvalOverrides(
        framework_assumptions={"top-down-revenue-capture": {"target_segment_count": private_slug}}
    )
    tam = size_concept(org_reg, _CONCEPT, overrides=overrides)
    kinds = {b.kind.value for sc in tam.scenarios for b in sc.banners}
    assert "private" in kinds, "TAM fed by private data must carry a private banner"


# ── AC5B.4 — disconnect purges ────────────────────────────────────────────


def test_disconnect_purges() -> None:
    vault = get_vault()
    vault.store("org-a", "stub", "tok")
    conn = StubConnector()
    get_store().add("org-a", "stub", conn.to_private_primitives("org-a", conn.fetch("t")))
    assert get_store().for_org("org-a")

    tokens = vault.purge("org-a", "stub")
    prims = get_store().purge("org-a", "stub")
    assert tokens is True and prims == 2
    assert get_store().for_org("org-a") == []
    assert vault.get("org-a", "stub") is None


# ── AC5B.5 — generic framework (2nd provider, no core changes) ────────────


def test_connector_framework_is_generic() -> None:
    assert isinstance(get_connector("stub"), SaaSConnector)
    assert isinstance(get_connector("hubspot"), SaaSConnector)
    # Both implement the contract by producing org-scoped private primitives.
    for conn in (StubConnector(), HubSpotConnector()):
        prims = conn.to_private_primitives(
            "org-x", {"customers": 1, "arr_usd": 1.0, "company_count": 1}
        )
        assert prims and all(p.visibility == "private" and p.org_id == "org-x" for p in prims)
