"""Frozen SSE event-name contract (spec §9.1, audit fix H).

The /resolve refactor moved logic into ``strata.resolver`` but the wire
format is frozen. This test asserts that the canonical event-name set is
the exact set in spec §9.1; the refactor is rejected if any name changes.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.resolver.parse import ParsedQuery
from strata.resolver.search import PrimitiveHit

# Per spec §9.1, the resolver emits exactly these wire-level events:
FROZEN_EVENTS: frozenset[str] = frozenset(
    {
        "parsing",
        "searching",
        "framework_selected",
        "evaluating",
        "result",
        "error",
    }
)

# Legacy backwards-compat events kept so the current frontend keeps working.
LEGACY_EVENTS: frozenset[str] = frozenset({"step", "done"})


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _parse_sse_event_names(body: str) -> list[str]:
    names: list[str] = []
    for line in body.splitlines():
        if line.startswith("event:"):
            names.append(line.removeprefix("event:").strip())
    return names


MOCK_PARSED = ParsedQuery.model_validate(
    {
        "lens": "productivity_uplift",
        "concept_name": "Test",
        "definition": "test",
        "primitives_needed": [
            {
                "role": "a",
                "description": "x",
                "search_query": "y",
                "expected_unit": {"kind": "stock", "dimension": "people"},
            },
            {
                "role": "b",
                "description": "x",
                "search_query": "y",
                "expected_unit": {"kind": "intensive", "dimension": "currency"},
            },
        ],
    }
)
MOCK_HIT_A = PrimitiveHit(
    role="a",
    name="A",
    value=100.0,
    unit={"kind": "stock", "dimension": "people"},
    source_url="https://example.com",
    source_tier="regulator",
)
MOCK_HIT_B = PrimitiveHit(
    role="b",
    name="B",
    value=50.0,
    unit={"kind": "intensive", "dimension": "currency"},
    source_url="https://example.com",
    source_tier="regulator",
)


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
async def test_resolve_emits_only_known_event_names(
    mock_parse, mock_search, client: AsyncClient
) -> None:
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [MOCK_HIT_A, MOCK_HIT_B]

    resp = await client.post("/resolve", json={"query": "test"})
    names = set(_parse_sse_event_names(resp.text))

    allowed = FROZEN_EVENTS | LEGACY_EVENTS
    unknown = names - allowed
    assert not unknown, f"unknown SSE events emitted: {unknown}"


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
async def test_resolve_happy_path_emits_full_contract(
    mock_parse, mock_search, client: AsyncClient
) -> None:
    """Happy path must emit every §9.1 lifecycle event in order."""
    mock_parse.return_value = MOCK_PARSED
    mock_search.side_effect = [MOCK_HIT_A, MOCK_HIT_B]

    resp = await client.post("/resolve", json={"query": "test"})
    names = _parse_sse_event_names(resp.text)

    required_in_order = ["parsing", "searching", "framework_selected", "evaluating", "result"]
    indices = [names.index(n) for n in required_in_order]
    assert indices == sorted(indices), f"events out of order: {names}"


@patch("strata.api.routes.resolve.parse_query")
async def test_resolve_failure_emits_error_event(mock_parse, client: AsyncClient) -> None:
    mock_parse.side_effect = RuntimeError("Claude blew up")
    resp = await client.post("/resolve", json={"query": "test"})
    names = _parse_sse_event_names(resp.text)
    assert "error" in names
    assert names[-1] == "done"


def test_frozen_events_set_is_exactly_spec_91() -> None:
    """If someone tries to remove an event from §9.1, this catches it."""
    assert {
        "parsing",
        "searching",
        "framework_selected",
        "evaluating",
        "result",
        "error",
    } == FROZEN_EVENTS


def test_pipeline_event_kind_enum_includes_spec_91() -> None:
    """The enum source-of-truth must keep the 6 §9.1 wire events.

    If someone renames ``PipelineEventKind.PARSING = "parse_start"`` this test
    fails at the enum boundary, BEFORE the SSE-emit code has a chance to
    silently drift away from the wire contract.
    """
    from strata.resolver.events import PipelineEventKind

    enum_values = {e.value for e in PipelineEventKind}
    missing = FROZEN_EVENTS - enum_values
    assert not missing, (
        f"PipelineEventKind is missing §9.1 wire events: {missing}. "
        f"Renaming a frozen wire-level event silently breaks SSE clients."
    )
