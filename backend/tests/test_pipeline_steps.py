"""Tests for pipeline step 3 (connector dispatch) and step 2b (framework_hint
→ registered concept → evaluator).

These exercise ``strata.resolver.pipeline.run`` directly with the Anthropic /
Exa boundaries mocked. The router + connector dispatch + writer are stubbed so
no network or disk I/O happens.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from strata.loader import load_data_dir
from strata.registry import Registry
from strata.resolver import RunOptions, run
from strata.resolver.events import PipelineEventKind, PipelineStatus
from strata.resolver.slug import ResolvedQuery, ResolverIntent

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _registry() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA_DIR))


def _novel(framework_hint: str | None = None) -> ResolvedQuery:
    return ResolvedQuery(
        intent=ResolverIntent.NOVEL,
        confidence=0.2,
        framework_hint=framework_hint,
    )


def _good_primitive_yaml(slug: str) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "test-concept",
        "name": "Auto primitive",
        "description": "A value pulled from a connector",
        "value": 4577.0,
        "unit": {"kind": "stock", "dimension": "organizations"},
        "as_of": "2026-05-27",
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "source": {
            "slug": "auto-source-2026",
            "tier": "regulator",
            "url": "https://example.com",
            "accessed": "2026-05-27",
            "snapshot_sha256": "a" * 64,
        },
    }


def _decision(connector: str = "fdic", method: str = "get_institution_count") -> MagicMock:
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
        "rationale": "best fit",
    }
    return d


# ---------------------------------------------------------------------------
# Step 3 — connector live dispatch
# ---------------------------------------------------------------------------


@patch("strata.resolver.writer.upsert_primitive")
@patch("strata.resolver.pipeline.call_and_convert")
@patch("strata.router.choose")
@patch("strata.resolver.pipeline.resolve_slug")
def test_step3_dispatch_writes_primitive_and_emits_events(
    mock_slug: MagicMock,
    mock_choose: MagicMock,
    mock_dispatch: MagicMock,
    mock_upsert: MagicMock,
    tmp_path: Path,
) -> None:
    mock_slug.return_value = _novel()
    mock_choose.return_value = _decision()
    prim_yaml = _good_primitive_yaml("fdic-bank-count-us-2024")
    mock_dispatch.return_value = prim_yaml
    mock_upsert.return_value = tmp_path / "fdic-bank-count-us-2024.yaml"

    result = run(
        "how many US banks",
        registry=_registry(),
        options=RunOptions(allow_live=True, allow_fallback=False),
    )

    assert result.via == "connector"
    assert result.status is not PipelineStatus.FAILED
    assert "fdic-bank-count-us-2024" in result.wrote_primitives
    mock_dispatch.assert_called_once()
    mock_upsert.assert_called_once()

    kinds = {e.kind for e in result.events}
    assert PipelineEventKind.CONNECTOR_CALL in kinds
    assert PipelineEventKind.WROTE_PRIMITIVE in kinds


@patch("strata.resolver.writer.upsert_primitive")
@patch("strata.resolver.pipeline.call_and_convert")
@patch("strata.router.choose")
@patch("strata.resolver.pipeline.resolve_slug")
def test_step3_dispatch_failure_falls_through_to_fallback(
    mock_slug: MagicMock,
    mock_choose: MagicMock,
    mock_dispatch: MagicMock,
    mock_upsert: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_ALLOW_EXA_FALLBACK", "1")  # Phase 4 fence opt-in
    mock_slug.return_value = _novel()
    mock_choose.return_value = _decision()
    mock_dispatch.side_effect = RuntimeError("connector 500")

    with (
        patch("strata.resolver.pipeline.parse_query") as mock_parse,
        patch("strata.resolver.pipeline.search_primitive") as mock_search,
    ):
        from strata.resolver.parse import ParsedPrimitive, ParsedQuery
        from strata.resolver.search import PrimitiveHit

        mock_parse.return_value = ParsedQuery(
            lens="cost_efficiency",
            concept_name="X",
            definition="Y",
            primitives_needed=[
                ParsedPrimitive(role="a", description="d", search_query="q"),
                ParsedPrimitive(role="b", description="d", search_query="q"),
            ],
        )
        mock_search.side_effect = [
            PrimitiveHit(
                role="a", name="A", value=10.0, unit={}, source_url="https://x", source_tier="r"
            ),
            PrimitiveHit(
                role="b", name="B", value=5.0, unit={}, source_url="https://x", source_tier="r"
            ),
        ]
        result = run(
            "novel query",
            registry=_registry(),
            options=RunOptions(allow_live=True, allow_fallback=True),
        )

    assert result.via == "fallback"
    mock_upsert.assert_not_called()


@patch("strata.resolver.writer.upsert_primitive")
@patch("strata.resolver.pipeline.call_and_convert")
@patch("strata.router.choose")
@patch("strata.resolver.pipeline.resolve_slug")
def test_step3_honors_expansion_budget(
    mock_slug: MagicMock,
    mock_choose: MagicMock,
    mock_dispatch: MagicMock,
    mock_upsert: MagicMock,
    tmp_path: Path,
) -> None:
    mock_slug.return_value = _novel()
    # Router returns a list of three decisions; budget caps to 2.
    mock_choose.return_value = [
        _decision(method="m1"),
        _decision(method="m2"),
        _decision(method="m3"),
    ]
    counter = {"n": 0}

    def _convert(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        counter["n"] += 1
        return _good_primitive_yaml(f"fdic-{method}-us-2024")

    mock_dispatch.side_effect = _convert
    mock_upsert.side_effect = lambda **kw: tmp_path / f"{kw['primitive_yaml']['slug']}.yaml"

    result = run(
        "multi",
        registry=_registry(),
        options=RunOptions(allow_live=True, allow_fallback=False, expansion_budget=2),
    )

    assert result.via == "connector"
    assert counter["n"] == 2
    assert len(result.wrote_primitives) == 2


# ---------------------------------------------------------------------------
# Step 2b — framework_hint maps to a REGISTERED concept → evaluator
# ---------------------------------------------------------------------------


@patch("strata.resolver.pipeline.resolve_slug")
def test_step2b_framework_hint_registered_concept_uses_evaluator(mock_slug: MagicMock) -> None:
    registry = _registry()
    # Two primitive hits + a framework_hint that is a registered concept slug.
    prim_slugs = [
        s
        for s in ["bls-pc-claims-adjusters-headcount", "naic-active-pc-carriers-2024"]
        if s in registry.atomic
    ]
    assert len(prim_slugs) == 2, "fixture data drifted"
    mock_slug.return_value = ResolvedQuery(
        intent=ResolverIntent.PRIMITIVE,
        confidence=0.9,
        primitive_slugs=prim_slugs,
        framework_hint="doc-gen-pc-insurance",
    )

    result = run(
        "P&C doc gen TAM",
        registry=registry,
        options=RunOptions(allow_live=False, allow_fallback=False),
    )

    assert result.status is PipelineStatus.OK
    assert result.via == "primitive"
    assert result.tam_value is not None
    assert result.tam_value > 0


@patch("strata.resolver.pipeline.resolve_slug")
def test_step2b_unknown_framework_hint_keeps_partial_banner(mock_slug: MagicMock) -> None:
    registry = _registry()
    prim_slugs = [
        s
        for s in ["bls-pc-claims-adjusters-headcount", "naic-active-pc-carriers-2024"]
        if s in registry.atomic
    ]
    assert len(prim_slugs) == 2
    mock_slug.return_value = ResolvedQuery(
        intent=ResolverIntent.PRIMITIVE,
        confidence=0.9,
        primitive_slugs=prim_slugs,
        framework_hint="not-a-real-concept",
    )

    result = run(
        "ambiguous",
        registry=registry,
        options=RunOptions(allow_live=False, allow_fallback=False),
    )

    assert result.status is PipelineStatus.PARTIAL
    assert result.banner is not None
