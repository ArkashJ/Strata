"""MCP ``add_portfolio_company`` — agent parity with ``strata portfolio add``.

Mirrors the CLI semantics including ADV-1: an explicit market_concept_slug that
isn't in the registry is an honest error with suggestions, never a fuzzy
reroute.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from strata.config import settings
from strata.mcp.server import load_registry
from strata.mcp.tools import call_tool
from strata.registry import Registry


def _call(reg: Registry, name: str, args: dict[str, Any]) -> dict[str, Any]:
    # add_portfolio_company is synchronous and dict-returning; narrow the
    # call_tool union for strict pyright.
    out = call_tool(reg, name, args)
    assert isinstance(out, dict)
    return out


@pytest.fixture
def portfolio_enabled() -> Iterator[None]:
    prev = settings.portfolio_enabled
    settings.portfolio_enabled = True
    try:
        yield
    finally:
        settings.portfolio_enabled = prev


@pytest.fixture
def tmp_store(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    # Point the store at a tmp file so we don't touch ~/.strata.
    import strata.mcp.portfolio_tools as pt

    store = tmp_path / "p.json"
    monkeypatch.setattr(pt, "_store", lambda: pt.CompanyStore(store, org_id="default"))
    return store


def test_add_disabled_by_default(tmp_store: Path) -> None:
    reg = load_registry()
    out = _call(reg, "add_portfolio_company", {"name": "X"})
    assert "disabled" in out["error"]


def test_add_unknown_explicit_market_is_honest_error(
    portfolio_enabled: None, tmp_store: Path
) -> None:
    reg = load_registry()
    out = _call(
        reg,
        "add_portfolio_company",
        {"name": "Acme", "domain": "acme.example", "market_concept_slug": "doc-gen-pc"},
    )
    assert out["error"] == "unknown_market_concept_slug"
    assert "doc-gen-pc-insurance" in out["suggestions"]
    assert not tmp_store.exists()  # honest refusal writes nothing


def test_add_blank_name_rejected(portfolio_enabled: None, tmp_store: Path) -> None:
    reg = load_registry()
    out = _call(reg, "add_portfolio_company", {"name": "   "})
    assert "error" in out
    assert not tmp_store.exists()


def test_add_then_update_then_size(portfolio_enabled: None, tmp_store: Path) -> None:
    import strata.mcp.portfolio_tools as pt

    reg = load_registry()
    out = _call(reg, "add_portfolio_company", {"name": "Acme", "domain": "acme.example"})
    assert out["action"] == "added"
    assert out["key"] == "acme.example"

    # Re-add carrying new info updates the row (ADV-3 parity).
    out = _call(
        reg,
        "add_portfolio_company",
        {
            "name": "Acme",
            "domain": "acme.example",
            "market_concept_slug": "doc-gen-pc-insurance",
        },
    )
    assert out["action"] == "updated"
    rec = pt.CompanyStore(tmp_store, org_id="default").get("acme.example")
    assert rec is not None and rec.market_concept_slug == "doc-gen-pc-insurance"

    # Sized happy path — registry-first, sourced concept, real state hash.
    out = _call(
        reg,
        "add_portfolio_company",
        {"name": "Acme", "domain": "acme.example", "size": True},
    )
    assert out["status"] == "sized"
    assert out["market_concept_slug"] == "doc-gen-pc-insurance"
    assert out["tam_value"] and out["tam_value"] > 0
    assert out["state_hash"]


def test_add_plain_readd_is_idempotent(portfolio_enabled: None, tmp_store: Path) -> None:
    reg = load_registry()
    _call(reg, "add_portfolio_company", {"name": "Acme", "domain": "acme.example"})
    out = _call(reg, "add_portfolio_company", {"name": "Acme", "domain": "acme.example"})
    assert out["action"] == "existing"
