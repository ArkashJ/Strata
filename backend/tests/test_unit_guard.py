"""Wave 1 / AC1.6 — the resolver unit guard blocks dimensionally-invalid TAMs.

Multiplying two currency factors (money²) or zero currency factors must fail
loudly before any number is emitted, not silently produce a wrong TAM.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.resolver.search import PrimitiveHit
from strata.resolver.units import UnitMismatchError, assert_multipliable
from tests.test_resolve import MOCK_PARSED, _parse_sse

_CURRENCY = {"kind": "intensive", "dimension": "currency", "currency": "USD"}
_PEOPLE = {"kind": "stock", "dimension": "people"}


def test_assert_multipliable_unit_cases() -> None:
    assert_multipliable([_PEOPLE, _CURRENCY])  # one currency factor — valid
    with pytest.raises(UnitMismatchError):
        assert_multipliable([_CURRENCY, _CURRENCY])  # money²
    with pytest.raises(UnitMismatchError):
        assert_multipliable([_PEOPLE, _PEOPLE])  # no currency → not a TAM


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
@pytest.mark.asyncio
async def test_resolve_unit_guard(mock_parse, mock_search, client: AsyncClient) -> None:
    mock_parse.return_value = MOCK_PARSED
    # Two currency hits → money², the guard must reject before emitting a TAM.
    mock_search.side_effect = [
        PrimitiveHit(
            role="a",
            name="spend A",
            value=1000.0,
            unit=_CURRENCY,
            source_url="https://www.bls.gov/x",
            source_tier="regulator",
        ),
        PrimitiveHit(
            role="b",
            name="spend B",
            value=2000.0,
            unit=_CURRENCY,
            source_url="https://www.census.gov/y",
            source_tier="regulator",
        ),
    ]
    resp = await client.post("/resolve", json={"query": "novel money squared market"})
    assert resp.status_code == 200
    types = [e["event"] for e in _parse_sse(resp.text)]
    assert "error" in types
    # No result event with a fabricated TAM should be emitted.
    results = [e for e in _parse_sse(resp.text) if e["event"] == "result"]
    if results:
        # If a result slips through it must not carry a positive TAM.
        assert json.loads(results[0]["data"]).get("tam_value", 0) == 0
