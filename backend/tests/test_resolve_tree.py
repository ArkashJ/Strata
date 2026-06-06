"""Wave 0 / AC0.2 + AC0.3 — resolver is registry-first and tree-shaped.

A query that names a curated concept resolves through the registry (no LLM) and
returns a ≥2-scenario tree spanning ≥2 method families (``estimate_kind ==
"triangulated"``). A novel query falls through to single-method synthesis with a
mandatory honesty banner and never dresses a point up as a triangulated TAM.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.loader import load_data_dir
from strata.registry import Registry
from strata.resolver.match import match_concept
from tests.test_resolve import MOCK_PARSED, MOCK_PRIMITIVE_1, MOCK_PRIMITIVE_2, _parse_sse

_TRIANGULATED_CONCEPT = "doc-gen-pc-insurance"
_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(autouse=True)
def _allow_exa_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_ALLOW_EXA_FALLBACK", "1")  # Phase 4 fence opt-in


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _result(body: str) -> dict:
    events = [e for e in _parse_sse(body) if e["event"] == "result"]
    assert len(events) == 1, f"expected exactly one result event, got {len(events)}"
    return json.loads(events[0]["data"])


# ── match_concept unit tests ───────────────────────────────────────────────


def test_match_concept_exact_slug() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    assert match_concept(reg, _TRIANGULATED_CONCEPT) == _TRIANGULATED_CONCEPT


def test_match_concept_fuzzy() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    # Spaced / filler variant of the slug still resolves.
    assert match_concept(reg, "doc gen pc insurance") == _TRIANGULATED_CONCEPT


def test_match_concept_miss() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    assert match_concept(reg, "wholly unrelated zylophone market 2099") is None


# ── AC0.2: concept hit returns a triangulated tree ─────────────────────────


@pytest.mark.asyncio
async def test_resolve_concept_returns_tree(client: AsyncClient) -> None:
    resp = await client.post("/resolve", json={"query": _TRIANGULATED_CONCEPT})
    assert resp.status_code == 200
    data = _result(resp.text)

    assert data["estimate_kind"] == "triangulated"
    scenarios = data["scenarios"]
    assert len(scenarios) >= 2, "concept hit must emit ≥2 scenarios"
    assert len({s["framework"] for s in scenarios}) >= 2, "≥2 distinct frameworks"
    assert len({s["method"] for s in scenarios}) >= 2, "≥2 distinct method families"
    # A triangulated tree is not a single point dressed as a TAM.
    assert all(s["label"] != "point" for s in scenarios)


# ── AC0.3: novel query is single_method + honesty banner ───────────────────


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
@pytest.mark.asyncio
async def test_resolve_novel_single_method(mock_parse, mock_search, client: AsyncClient) -> None:
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [MOCK_PRIMITIVE_1, MOCK_PRIMITIVE_2]

    resp = await client.post("/resolve", json={"query": "wholly unrelated zylophone market 2099"})
    assert resp.status_code == 200
    data = _result(resp.text)

    assert data["estimate_kind"] == "single_method"
    assert data["banner"], "novel single-method result must carry an honesty banner"
    scenarios = data["scenarios"]
    assert len(scenarios) == 1
    assert scenarios[0]["triangulated"] is False
