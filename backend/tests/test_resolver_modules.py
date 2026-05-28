"""Unit tests for the resolver/ submodules (audit fix J).

Covers slug.py, parse.py, search.py, writer.py — all with mocked Anthropic /
Exa where applicable.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from strata.resolver.parse import ParsedQuery, parse_query
from strata.resolver.search import PrimitiveHit, search_primitive
from strata.resolver.slug import (
    ConceptSummary,
    PrimitiveSummary,
    ResolverIntent,
    resolve_slug,
)
from strata.resolver.writer import AUTO_PRIMITIVES_DIR, upsert_primitive

# ---------------------------------------------------------------------------
# slug.py
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    # Block must be instance of TextBlock for isinstance() check
    from anthropic.types import TextBlock

    block.__class__ = TextBlock
    return resp


@patch("strata.resolver.slug.get_anthropic_client")
def test_resolve_slug_concept_hit(mock_client: MagicMock) -> None:
    mock_client.return_value.messages.create.return_value = _make_text_response(
        '{"intent": "concept", "concept_slug": "us-pc-doc-gen", "primitive_slugs": [], '
        '"framework_hint": null, "confidence": 0.92}'
    )
    out = resolve_slug(
        "P&C insurance doc-gen TAM",
        known_concepts=[
            ConceptSummary(
                slug="us-pc-doc-gen",
                name="US P&C doc-gen",
                one_line_description="Property/casualty insurance documentation automation",
            )
        ],
        known_primitives=[],
    )
    assert out.intent is ResolverIntent.CONCEPT
    assert out.concept_slug == "us-pc-doc-gen"
    assert out.confidence == 0.92


@patch("strata.resolver.slug.get_anthropic_client")
def test_resolve_slug_primitive_hit(mock_client: MagicMock) -> None:
    mock_client.return_value.messages.create.return_value = _make_text_response(
        '{"intent": "primitive", "concept_slug": null, '
        '"primitive_slugs": ["bls-software-developers-us-2024"], '
        '"framework_hint": "cost_efficiency", "confidence": 0.81}'
    )
    out = resolve_slug(
        "US software developer headcount",
        known_concepts=[],
        known_primitives=[
            PrimitiveSummary(
                slug="bls-software-developers-us-2024",
                name="BLS software developers (US)",
                one_line_description="OES 15-1252 total US employment",
            )
        ],
    )
    assert out.intent is ResolverIntent.PRIMITIVE
    assert out.primitive_slugs == ["bls-software-developers-us-2024"]
    assert out.framework_hint == "cost_efficiency"


@patch("strata.resolver.slug.get_anthropic_client")
def test_resolve_slug_novel(mock_client: MagicMock) -> None:
    mock_client.return_value.messages.create.return_value = _make_text_response(
        '{"intent": "novel", "concept_slug": null, "primitive_slugs": [], '
        '"framework_hint": null, "confidence": 0.4}'
    )
    out = resolve_slug("some unheard-of market", known_concepts=[], known_primitives=[])
    assert out.intent is ResolverIntent.NOVEL
    assert out.confidence < 0.5  # below threshold → pipeline skips registry steps


# ---------------------------------------------------------------------------
# parse.py
# ---------------------------------------------------------------------------


@patch("strata.resolver.parse.get_anthropic_client")
def test_parse_query_returns_pydantic(mock_client: MagicMock) -> None:
    mock_client.return_value.messages.create.return_value = _make_text_response(
        '{"lens": "cost_efficiency", "concept_name": "x", "definition": "y", '
        '"primitives_needed": [{"role": "a", "description": "b", "search_query": "c", '
        '"expected_unit": {"kind": "stock", "dimension": "people"}, "expected_currency": null}]}'
    )
    out = parse_query("any query")
    assert isinstance(out, ParsedQuery)
    assert out.lens == "cost_efficiency"
    assert len(out.primitives_needed) == 1


@patch("strata.resolver.parse.get_anthropic_client")
def test_parse_query_strips_markdown_fences(mock_client: MagicMock) -> None:
    mock_client.return_value.messages.create.return_value = _make_text_response(
        '```json\n{"lens": "latent_demand", "concept_name": "x", "definition": "y", '
        '"primitives_needed": []}\n```'
    )
    out = parse_query("q")
    assert out.lens == "latent_demand"


# ---------------------------------------------------------------------------
# search.py
# ---------------------------------------------------------------------------


@patch("strata.resolver.search.get_anthropic_client")
@patch("strata.resolver.search._get_exa")
def test_search_primitive_happy_path(mock_exa: MagicMock, mock_anthropic: MagicMock) -> None:
    """Exa returns a highlight → Claude extracts a number → PrimitiveHit."""
    result_item = MagicMock(
        url="https://example.com/x", title="Source", highlights=["The figure is 1234567."]
    )
    mock_exa.return_value.search.return_value = MagicMock(results=[result_item])
    mock_anthropic.return_value.messages.create.return_value = _make_text_response(
        '{"value": 1234567, "name": "Test source", "source_url": "https://example.com/x", '
        '"source_tier": "regulator"}'
    )

    from strata.resolver.parse import ParsedPrimitive

    hit = search_primitive(
        ParsedPrimitive(
            role="x",
            description="y",
            search_query="z",
            expected_unit={"kind": "stock", "dimension": "people"},
        )
    )
    assert isinstance(hit, PrimitiveHit)
    assert hit.value == 1234567
    assert hit.source_tier == "regulator"


@patch("strata.resolver.search._get_exa")
def test_search_primitive_returns_none_when_no_results(mock_exa: MagicMock) -> None:
    mock_exa.return_value.search.return_value = MagicMock(results=[])

    from strata.resolver.parse import ParsedPrimitive

    hit = search_primitive(
        ParsedPrimitive(role="x", description="y", search_query="z", expected_unit={})
    )
    assert hit is None


# ---------------------------------------------------------------------------
# writer.py
# ---------------------------------------------------------------------------


def _good_primitive_yaml(slug: str = "test-prim-2026") -> dict[str, object]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "test-concept",
        "name": "Test primitive",
        "description": "A test value",
        "value": 100.0,
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": "2026-05-27",
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "source": {
            "slug": "test-source-2026",
            "tier": "regulator",
            "url": "https://example.com",
            "accessed": "2026-05-27",
            "snapshot_sha256": "a" * 64,
        },
    }


def test_writer_upsert_creates_yaml(tmp_path: Path) -> None:
    out = upsert_primitive(
        primitive_yaml=_good_primitive_yaml(),
        connector="fdic",
        method="get_total_assets",
        args={"report_date": "20241231"},
        dir_override=tmp_path,
    )
    assert out.exists()
    text = out.read_text()
    assert "is_auto: true" in text
    assert "auto_connector: fdic" in text
    assert "auto_method: get_total_assets" in text


def test_writer_upsert_is_idempotent(tmp_path: Path) -> None:
    args = {"report_date": "20241231"}
    p1 = upsert_primitive(
        primitive_yaml=_good_primitive_yaml(),
        connector="fdic",
        method="get_total_assets",
        args=args,
        dir_override=tmp_path,
    )
    p2 = upsert_primitive(
        primitive_yaml=_good_primitive_yaml(),
        connector="fdic",
        method="get_total_assets",
        args=args,
        dir_override=tmp_path,
    )
    assert p1 == p2
    files = list(tmp_path.glob("*.yaml"))
    assert len(files) == 1


def test_writer_rejects_invalid_primitive(tmp_path: Path) -> None:
    bad = _good_primitive_yaml()
    bad["value"] = float("nan")  # NaN explicitly rejected by AtomicPrimitive
    with pytest.raises(ValueError):  # noqa: PT011 — Pydantic raises a subclass
        upsert_primitive(
            primitive_yaml=bad,
            connector="fdic",
            method="get_total_assets",
            args={},
            dir_override=tmp_path,
        )


def test_auto_primitives_dir_points_at_user_home() -> None:
    # Sanity: spec §8 mandates ~/.strata/auto-primitives/, not data/primitives/.
    assert Path.home() / ".strata" / "auto-primitives" == AUTO_PRIMITIVES_DIR
