"""The /resolve route delegates to ``strata.resolver.pipeline.run`` and must
never leak CLI-only pipeline event kinds onto the wire.

Complements ``test_sse_event_contract.py``: that file freezes the allowed
event-name set; this file proves the route stays inside it even when the
underlying ``ResolverResult`` carries CLI-only events, and that the route
actually calls ``run`` (not the deleted inline path).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.resolver.events import (
    PipelineEvent,
    PipelineEventKind,
    PipelineStatus,
    ResolverResult,
)

# CLI-only kinds that must NOT appear on the wire (spec §9.1).
CLI_ONLY = {
    "slug_resolved",
    "concept_hit",
    "primitive_hit",
    "router_decision",
    "connector_call",
    "wrote_primitive",
    "budget_exceeded",
}
ALLOWED = {
    "parsing",
    "searching",
    "framework_selected",
    "evaluating",
    "result",
    "error",
    "step",
    "done",
}


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event:").strip()
        for line in body.splitlines()
        if line.startswith("event:")
    ]


def _result_with_cli_events() -> ResolverResult:
    return ResolverResult(
        status=PipelineStatus.OK,
        via="connector",
        tam_value=1_000_000.0,
        formatted_tam="$1M",
        concept_name="Test",
        lens="cost_efficiency",
        framework_name="Bottoms-up",
        primitives_used=[
            {"role": "a", "name": "A", "value": 100.0, "unit": {}, "source_url": "https://x"},
            {"role": "b", "name": "B", "value": 5.0, "unit": {}, "source_url": "https://x"},
        ],
        wrote_primitives=["fdic-bank-count-us-2024"],
        events=[
            PipelineEvent(kind=PipelineEventKind.SLUG_RESOLVED, step="pre", payload={}),
            PipelineEvent(kind=PipelineEventKind.ROUTER_DECISION, step="3", payload={}),
            PipelineEvent(kind=PipelineEventKind.CONNECTOR_CALL, step="3", payload={}),
            PipelineEvent(kind=PipelineEventKind.WROTE_PRIMITIVE, step="3", payload={}),
        ],
    )


@patch("strata.api.routes.resolve.run")
async def test_route_calls_pipeline_run(mock_run: MagicMock, client: AsyncClient) -> None:
    mock_run.return_value = _result_with_cli_events()
    resp = await client.post("/resolve", json={"query": "anything"})
    assert resp.status_code == 200
    assert mock_run.called


@patch("strata.api.routes.resolve.run")
async def test_route_never_leaks_cli_only_events(mock_run: MagicMock, client: AsyncClient) -> None:
    mock_run.return_value = _result_with_cli_events()
    resp = await client.post("/resolve", json={"query": "anything"})
    names = set(_event_names(resp.text))
    assert not (names & CLI_ONLY), f"CLI-only events leaked: {names & CLI_ONLY}"
    assert not (names - ALLOWED), f"unknown events: {names - ALLOWED}"


@patch("strata.api.routes.resolve.run")
async def test_route_emits_result_for_successful_run(
    mock_run: MagicMock, client: AsyncClient
) -> None:
    mock_run.return_value = _result_with_cli_events()
    resp = await client.post("/resolve", json={"query": "anything"})
    names = _event_names(resp.text)
    assert "result" in names
    assert names[-1] == "done"


@patch("strata.api.routes.resolve.run")
async def test_route_emits_error_when_pipeline_fails(
    mock_run: MagicMock, client: AsyncClient
) -> None:
    mock_run.return_value = ResolverResult(
        status=PipelineStatus.FAILED,
        via="none",
        error="not enough primitives synthesized via fallback",
    )
    resp = await client.post("/resolve", json={"query": "anything"})
    names = _event_names(resp.text)
    assert "error" in names
    assert names[-1] == "done"
