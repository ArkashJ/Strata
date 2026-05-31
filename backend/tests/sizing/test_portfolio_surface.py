"""GET /portfolio route + MCP write-tool tests (spec §7, F3, F6).

The read path always serves the cached demo (no live calls); the write tools
gate on STRATA_PORTFOLIO_ENABLED.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from strata.api.app import app
from strata.config import settings
from strata.mcp.server import load_registry
from strata.mcp.tools import call_tool


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def portfolio_enabled() -> Iterator[None]:
    prev = settings.portfolio_enabled
    settings.portfolio_enabled = True
    try:
        yield
    finally:
        settings.portfolio_enabled = prev


# ── GET /portfolio (read path — always on, F3-safe) ─────────────────────────
def test_portfolio_route_serves_cached_demo(client: TestClient) -> None:
    r = client.get("/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["total"] == 25
    assert body["counts"]["sized"] == 20
    assert body["counts"]["unsizable"] == 5
    sized = [c for c in body["companies"] if c["status"] == "sized"]
    assert all(c["tam_value"] and c["market_concept_slug"] for c in sized)
    uns = [c for c in body["companies"] if c["status"] == "unsizable"]
    assert all(c["reason"] for c in uns)  # honesty: every unsizable explains itself


# ── MCP write tools (F6 gate) ───────────────────────────────────────────────
def test_write_tools_disabled_by_default() -> None:
    # settings.portfolio_enabled defaults False in test env.
    reg = load_registry()
    out = call_tool(reg, "import_portfolio", {"rows": [{"name": "X", "domain": "x.com"}]})
    assert "error" in out
    assert "disabled" in out["error"]


def test_import_and_list_when_enabled(
    portfolio_enabled: None, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Point the store at a tmp file so we don't touch ~/.strata.
    import strata.mcp.portfolio_tools as pt

    monkeypatch.setattr(
        pt, "_store", lambda: pt.CompanyStore(tmp_path / "p.json", org_id="default")
    )
    reg = load_registry()

    out = call_tool(
        reg,
        "import_portfolio",
        {"rows": [{"name": "Cursor", "domain": "cursor.com", "vertical": "Dev"}]},
    )
    assert out["imported"] == 1

    listed = call_tool(reg, "list_portfolio", {})
    assert listed["source"] == "store"
    assert listed["counts"]["total"] == 1


def test_list_portfolio_falls_back_to_demo_when_store_empty(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    import strata.mcp.portfolio_tools as pt

    monkeypatch.setattr(
        pt, "_store", lambda: pt.CompanyStore(tmp_path / "empty.json", org_id="default")
    )
    reg = load_registry()
    listed = call_tool(reg, "list_portfolio", {"status": "unsizable"})
    assert listed["source"] == "cached_demo"
    assert listed["counts"]["total"] == 25
    assert all(c["status"] == "unsizable" for c in listed["companies"])
