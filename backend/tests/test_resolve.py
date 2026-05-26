"""Tests for the /resolve dynamic TAM resolution endpoint."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Shared mock payloads
# ---------------------------------------------------------------------------

MOCK_PARSED: dict[str, object] = {
    "lens": "productivity_uplift",
    "concept_name": "Test market",
    "definition": "A test market definition.",
    "primitives_needed": [
        {
            "role": "persona_count",
            "description": "number of people",
            "search_query": "test query 1",
            "expected_unit": {"kind": "stock", "dimension": "people"},
        },
        {
            "role": "value_per_persona",
            "description": "cost per person",
            "search_query": "test query 2",
            "expected_unit": {"kind": "intensive", "dimension": "currency"},
        },
    ],
}

MOCK_PRIMITIVE_1: dict[str, object] = {
    "role": "persona_count",
    "name": "Test headcount",
    "value": 1_000_000.0,
    "unit": {"kind": "stock", "dimension": "people"},
    "source_url": "https://example.com/1",
    "source_tier": "regulator",
}

MOCK_PRIMITIVE_2: dict[str, object] = {
    "role": "value_per_persona",
    "name": "Test cost",
    "value": 500.0,
    "unit": {"kind": "intensive", "dimension": "currency"},
    "source_url": "https://example.com/2",
    "source_tier": "analyst",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[dict[str, str]]:
    """Return list of {event, data} dicts from a raw SSE body."""
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            current["data"] = line.removeprefix("data:").strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def _event_types(body: str) -> list[str]:
    return [e["event"] for e in _parse_sse(body)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("strata.api.routes.resolve._search_primitive_with_exa")
@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_happy_path(mock_parse, mock_search, client: AsyncClient) -> None:
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [MOCK_PRIMITIVE_1, MOCK_PRIMITIVE_2]

    response = await client.post("/resolve", json={"query": "test market"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    types = _event_types(body)

    assert "step" in types
    assert "result" in types
    assert "done" in types
    assert "error" not in types

    # Find the result event and verify TAM arithmetic: 1_000_000 * 500 = 500_000_000
    result_events = [e for e in _parse_sse(body) if e["event"] == "result"]
    assert len(result_events) == 1
    result_data = json.loads(result_events[0]["data"])
    assert result_data["tam_value"] == 500_000_000.0
    assert result_data["concept_name"] == "Test market"
    assert result_data["lens"] == "productivity_uplift"
    assert "$500M" in result_data["formatted_tam"]


@patch("strata.api.routes.resolve._search_primitive_with_exa")
@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_not_enough_primitives(mock_parse, mock_search, client: AsyncClient) -> None:
    mock_parse.return_value = MOCK_PARSED
    # Second primitive search returns None (not found)
    mock_search.side_effect = [MOCK_PRIMITIVE_1, None]

    response = await client.post("/resolve", json={"query": "test market"})
    assert response.status_code == 200

    body = response.text
    types = _event_types(body)
    assert "error" in types
    assert "done" in types

    # Confirm the error message is user-facing (not a raw exception)
    error_events = [e for e in _parse_sse(body) if e["event"] == "error"]
    assert len(error_events) >= 1
    error_data = json.loads(error_events[0]["data"])
    assert "Could not find enough" in error_data["message"]


@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_claude_parse_failure(mock_parse, client: AsyncClient) -> None:
    mock_parse.side_effect = Exception("Claude API down")

    response = await client.post("/resolve", json={"query": "test"})
    assert response.status_code == 200

    body = response.text
    types = _event_types(body)
    assert "error" in types
    assert "done" in types

    # Raw exception message must NOT leak to the client
    assert "Claude API down" not in body

    error_events = [e for e in _parse_sse(body) if e["event"] == "error"]
    error_msg = json.loads(error_events[0]["data"])["message"].lower()
    assert "internal error" in error_msg or "try again" in error_msg


@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_claude_invalid_json(mock_parse, client: AsyncClient) -> None:
    mock_parse.side_effect = json.JSONDecodeError("test", "doc", 0)

    response = await client.post("/resolve", json={"query": "test"})
    assert response.status_code == 200

    body = response.text
    types = _event_types(body)
    assert "error" in types
    assert "done" in types


async def test_resolve_missing_query(client: AsyncClient) -> None:
    """Omitting the required `query` field returns a 422 validation error."""
    response = await client.post("/resolve", json={})
    assert response.status_code == 422


@patch("strata.api.routes.resolve._search_primitive_with_exa")
@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_step_events_ordering(mock_parse, mock_search, client: AsyncClient) -> None:
    """SSE events must appear in the expected logical order."""
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [MOCK_PRIMITIVE_1, MOCK_PRIMITIVE_2]

    response = await client.post("/resolve", json={"query": "test market"})
    body = response.text
    types = _event_types(body)

    # Must begin with a step and end with done
    assert types[0] == "step"
    assert types[-1] == "done"
    # result must appear before done
    result_idx = next(i for i, t in enumerate(types) if t == "result")
    done_idx = next(i for i, t in enumerate(types) if t == "done")
    assert result_idx < done_idx


@patch("strata.api.routes.resolve._search_primitive_with_exa")
@patch("strata.api.routes.resolve._parse_query_with_claude")
async def test_resolve_both_primitives_missing(mock_parse, mock_search, client: AsyncClient) -> None:
    """When all primitive searches fail, should return an error event."""
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [None, None]

    response = await client.post("/resolve", json={"query": "unknowable market"})
    assert response.status_code == 200

    body = response.text
    assert "event: error" in body
    assert "event: done" in body
    assert "event: result" not in body
