"""Tests for the Dune Analytics connector (httpx-mocked, no network)."""

from __future__ import annotations

import httpx
import pytest

from strata.connectors.dune import (
    DuneClient,
    DuneClientError,
    ExecutionState,
    QueryResult,
    capabilities,
    run_query_result_to_primitive_yaml,
)


def _client(handler: httpx.MockTransport) -> DuneClient:
    c = DuneClient(api_key="test-key")
    c._http = httpx.Client(transport=handler)  # type: ignore[attr-defined]
    return c


def test_execute_query_parses_handle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/query/649046/execute")
        assert request.headers["X-Dune-API-Key"] == "test-key"
        return httpx.Response(200, json={"execution_id": "01ABC", "state": "QUERY_STATE_PENDING"})

    client = _client(httpx.MockTransport(handler))
    handle = client.execute_query(649046)
    assert handle.execution_id == "01ABC"
    assert handle.state == ExecutionState.PENDING


def test_get_status_executing_then_completed() -> None:
    states = iter(["QUERY_STATE_EXECUTING", "QUERY_STATE_COMPLETED"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "execution_id": "01ABC",
                "state": next(states),
                "result_metadata": {"total_row_count": 5, "row_count": 5},
            },
        )

    client = _client(httpx.MockTransport(handler))
    s1 = client.get_status("01ABC")
    assert s1.state == ExecutionState.EXECUTING
    assert not s1.is_complete
    s2 = client.get_status("01ABC")
    assert s2.state == ExecutionState.COMPLETED
    assert s2.is_complete
    assert s2.total_row_count == 5


def test_get_results_parses_rows_and_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "execution_id": "01ABC",
                "state": "QUERY_STATE_COMPLETED",
                "result": {
                    "rows": [
                        {"volume_usd": 12345.67, "chain": "ethereum"},
                        {"volume_usd": 999.0, "chain": "base"},
                    ],
                    "metadata": {"column_names": ["volume_usd", "chain"], "row_count": 2},
                },
            },
        )

    client = _client(httpx.MockTransport(handler))
    result = client.get_results("01ABC", query_id=649046)
    assert result.row_count == 2
    assert result.column_names == ("volume_usd", "chain")
    assert result.rows[0]["chain"] == "ethereum"
    assert result.column("chain") == ("ethereum", "base")


def test_run_query_happy_path() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/execute"):
            return httpx.Response(
                200, json={"execution_id": "01ABC", "state": "QUERY_STATE_PENDING"}
            )
        if request.url.path.endswith("/status"):
            return httpx.Response(
                200,
                json={
                    "execution_id": "01ABC",
                    "state": "QUERY_STATE_COMPLETED",
                    "result_metadata": {"total_row_count": 1},
                },
            )
        if request.url.path.endswith("/results"):
            return httpx.Response(
                200,
                json={
                    "execution_id": "01ABC",
                    "state": "QUERY_STATE_COMPLETED",
                    "result": {
                        "rows": [{"volume_usd": 12345.67, "chain": "ethereum"}],
                        "metadata": {"column_names": ["volume_usd", "chain"], "row_count": 1},
                    },
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _client(httpx.MockTransport(handler))
    result = client.run_query(649046, poll_interval=0)
    assert result.rows[0]["volume_usd"] == 12345.67
    assert result.column_names == ("volume_usd", "chain")
    assert result.row_count == 1
    assert any(p.endswith("/execute") for p in calls)
    assert any(p.endswith("/status") for p in calls)
    assert any(p.endswith("/results") for p in calls)


def test_run_query_failed_state_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/execute"):
            return httpx.Response(200, json={"execution_id": "01X", "state": "QUERY_STATE_PENDING"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"execution_id": "01X", "state": "QUERY_STATE_FAILED"})
        return httpx.Response(500, json={"error": "should not fetch results"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(DuneClientError, match="FAILED"):
        client.run_query(1, poll_interval=0)


def test_http_error_body_raises_connector_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Query not found"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(DuneClientError, match="Query not found"):
        client.get_status("missing")


def test_inline_error_payload_raises_connector_error() -> None:
    # 200 OK body that nonetheless carries an ``error`` key.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "query is private"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(DuneClientError, match="query is private"):
        client.get_status("01ABC")


def test_unauthorized_raises_connector_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid API key"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(DuneClientError, match="Authentication failed"):
        client.execute_query(1)


def test_converter_emits_valid_strata_primitive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/execute"):
            return httpx.Response(
                200, json={"execution_id": "01ABC", "state": "QUERY_STATE_PENDING"}
            )
        if request.url.path.endswith("/status"):
            return httpx.Response(
                200, json={"execution_id": "01ABC", "state": "QUERY_STATE_COMPLETED"}
            )
        return httpx.Response(
            200,
            json={
                "execution_id": "01ABC",
                "state": "QUERY_STATE_COMPLETED",
                "result": {
                    "rows": [{"volume_usd": 12345.67, "chain": "ethereum"}],
                    "metadata": {"column_names": ["volume_usd", "chain"], "row_count": 1},
                },
            },
        )

    client = _client(httpx.MockTransport(handler))
    result = client.run_query(649046, poll_interval=0)
    prim = run_query_result_to_primitive_yaml(
        result,
        query_id=649046,
        column="volume_usd",
        concept_slug="dex-volume",
        primitive_slug="dune-dex-volume-eth",
        name="Monthly DEX volume (Ethereum)",
        description="Sum of dex.trades amount_usd.",
    )
    assert prim["kind"] == "atomic_primitive"
    assert prim["source"]["tier"] == "onchain"
    assert prim["value"] == 12345.67
    assert prim["source"]["url"].endswith("/queries/649046")
    assert len(prim["source"]["snapshot_sha256"]) == 64


def test_converter_missing_column_raises() -> None:
    result = QueryResult(
        execution_id="x",
        state=ExecutionState.COMPLETED,
        rows=({"a": 1},),
        column_names=("a",),
        row_count=1,
    )
    with pytest.raises(DuneClientError, match="not in result columns"):
        run_query_result_to_primitive_yaml(
            result,
            query_id=1,
            column="missing",
            concept_slug="c",
            primitive_slug="p",
            name="n",
            description="d",
        )


def test_capabilities_methods_exist_on_client() -> None:
    specs = capabilities()
    assert specs, "dune connector must expose at least one capability"
    for spec in specs:
        assert spec.connector == "dune"
        assert spec.source_tier == "onchain"
        assert hasattr(DuneClient, spec.method), f"missing method {spec.method}"
