"""Session 2 — pipeline step-3 dispatch + /resolve→pipeline SSE translation.

Two surfaces are covered:

- ``pipeline.run`` step 3: a router decision now actually dispatches the
  connector, writes the auto-primitive, and records it on the result.
- ``/resolve`` delegates to ``pipeline.run`` but the wire output must stay
  inside the frozen §9.1 event set — CLI-only event kinds must not leak.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.loader import LoadedRecords
from strata.registry import Registry
from strata.resolver.events import PipelineEventKind, PipelineStatus
from strata.resolver.parse import ParsedQuery
from strata.resolver.pipeline import RunOptions, run
from strata.resolver.search import PrimitiveHit

# Wire-level event set the /resolve endpoint is allowed to emit (frozen §9.1
# plus the two legacy compatibility events kept for the existing frontend).
FROZEN_WIRE = {"parsing", "searching", "framework_selected", "evaluating", "result", "error"}
LEGACY_WIRE = {"step", "done"}
CLI_ONLY = {
    PipelineEventKind.SLUG_RESOLVED.value,
    PipelineEventKind.CONCEPT_HIT.value,
    PipelineEventKind.PRIMITIVE_HIT.value,
    PipelineEventKind.ROUTER_DECISION.value,
    PipelineEventKind.CONNECTOR_CALL.value,
    PipelineEventKind.WROTE_PRIMITIVE.value,
    PipelineEventKind.BUDGET_EXCEEDED.value,
}


# ---------------------------------------------------------------------------
# /resolve SSE translation
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


_PARSED = ParsedQuery.model_validate(
    {
        "lens": "productivity_uplift",
        "concept_name": "Test",
        "definition": "d",
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
_HIT_A = PrimitiveHit(
    role="a",
    name="A",
    value=10.0,
    unit={"kind": "stock", "dimension": "people"},
    source_url="https://example.com",
    source_tier="regulator",
)
_HIT_B = PrimitiveHit(
    role="b",
    name="B",
    value=5.0,
    unit={"kind": "intensive", "dimension": "currency"},
    source_url="https://example.com",
    source_tier="regulator",
)


def _event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event:").strip()
        for line in body.splitlines()
        if line.startswith("event:")
    ]


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
async def test_resolve_does_not_leak_cli_only_events(
    mock_parse: MagicMock, mock_search: MagicMock, client: AsyncClient
) -> None:
    mock_parse.return_value = _PARSED
    mock_search.side_effect = [_HIT_A, _HIT_B]

    resp = await client.post("/resolve", json={"query": "test"})
    names = set(_event_names(resp.text))

    assert not (names & CLI_ONLY), f"CLI-only events leaked to wire: {names & CLI_ONLY}"
    assert not (names - (FROZEN_WIRE | LEGACY_WIRE)), "unknown events on wire"


@patch("strata.api.routes.resolve.search_primitive")
@patch("strata.api.routes.resolve.parse_query")
async def test_resolve_result_payload_via_pipeline(
    mock_parse: MagicMock, mock_search: MagicMock, client: AsyncClient
) -> None:
    mock_parse.return_value = _PARSED
    mock_search.side_effect = [_HIT_A, _HIT_B]

    resp = await client.post("/resolve", json={"query": "test"})
    body = resp.text
    result_line = next(seg for seg in body.split("\n\n") if seg.startswith("event: result"))
    data = json.loads(result_line.splitlines()[1].removeprefix("data:").strip())
    assert data["tam_value"] == 50.0  # 10 * 5


# ---------------------------------------------------------------------------
# pipeline step 3 — connector dispatch + writer
# ---------------------------------------------------------------------------


def _empty_registry() -> Registry:
    return Registry.from_loaded(LoadedRecords())


def _decision(connector: str = "fdic", method: str = "get_total_assets") -> Any:
    d = MagicMock()
    d.connector = connector
    d.method = method
    d.args = {"report_date": "20241231"}
    d.confidence = 0.9
    d.model_dump.return_value = {
        "connector": connector,
        "method": method,
        "args": d.args,
        "confidence": 0.9,
        "rationale": "r",
    }
    return d


_FAKE_PRIMITIVE = {"slug": "fdic-total-assets-us-2024", "value": 1.0}


def test_step3_dispatch_writes_primitive_and_records_it(tmp_path: Path) -> None:
    """A router decision dispatches the connector, upserts, and records the slug."""

    with (
        patch("strata.router.choose", return_value=_decision()) as mock_choose,
        patch(
            "strata.connectors._dispatch.call_and_convert", return_value=_FAKE_PRIMITIVE
        ) as mock_call,
        patch(
            "strata.resolver.writer.upsert_primitive",
            return_value=tmp_path / "fdic-total-assets-us-2024.yaml",
        ) as mock_write,
    ):
        result = run(
            "TAM for US bank assets",
            registry=_empty_registry(),
            options=RunOptions(allow_live=True, allow_fallback=False),
        )

    assert mock_choose.called
    assert mock_call.called
    assert mock_write.called
    assert "fdic-total-assets-us-2024" in result.wrote_primitives
    kinds = {e.kind for e in result.events}
    assert PipelineEventKind.CONNECTOR_CALL in kinds
    assert PipelineEventKind.WROTE_PRIMITIVE in kinds


def test_step3_dispatch_failure_falls_through_to_fallback() -> None:
    """If the connector call raises, step 3 does not crash — it falls through."""

    with (
        patch("strata.router.choose", return_value=_decision()),
        patch(
            "strata.connectors._dispatch.call_and_convert",
            side_effect=RuntimeError("connector down"),
        ),
    ):
        result = run(
            "TAM for US bank assets",
            registry=_empty_registry(),
            options=RunOptions(allow_live=True, allow_fallback=False),
        )

    # No fallback allowed → terminal FAILED, but the process did not raise and
    # no primitive was recorded.
    assert result.status is PipelineStatus.FAILED
    assert result.wrote_primitives == []


def test_step3_honors_expansion_budget() -> None:
    """expansion_budget caps how many connector dispatches step 3 performs."""

    decisions = [_decision(method=f"m{i}") for i in range(5)]

    with (
        patch("strata.router.choose", return_value=decisions),
        patch(
            "strata.connectors._dispatch.call_and_convert", return_value=_FAKE_PRIMITIVE
        ) as mock_call,
        patch(
            "strata.resolver.writer.upsert_primitive",
            return_value=Path("/tmp/x.yaml"),
        ),
    ):
        run(
            "TAM",
            registry=_empty_registry(),
            options=RunOptions(allow_live=True, allow_fallback=False, expansion_budget=2),
        )

    assert mock_call.call_count <= 2
