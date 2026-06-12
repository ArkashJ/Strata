"""Tests for today + future market projection (`project_tam`).

Coverage:
- None (honest gap) when a concept declares no growth_index
- None when growth_index points at a missing / non-atomic primitive
- None when the growth primitive's unit is not a per-year rate
- projection math: horizon == today * (1+cagr)**years; point kinds + years
- base_year is the latest as_of among CONSUMED inputs (not the growth rate's)
- a modeled-tier growth rate raises a MODELED banner on the projection
- non-positive horizon_years raises
- the real seeded ai-coding-assistants-us concept projects, banner-flagged
- a real concept without a growth_index returns None
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from strata.evaluator import EvaluatorError, project_tam
from strata.loader import load_data_dir
from strata.models import (
    AnalysisLens,
    AtomicPrimitive,
    BannerKind,
    Concept,
    ConceptAnalysisLens,
    ConceptModifiers,
    Framework,
    FrameworkInput,
    FrameworkVariant,
    InputRole,
    MethodFamily,
    StandardSource,
    Unit,
    UnitBasis,
    UnitDimension,
    UnitKind,
)
from strata.models.geo import Geo, GeoLevel, GeoPerspective
from strata.registry import Registry

REPO_DATA = Path(__file__).resolve().parents[2] / "data"

_UNIT_USD_YEAR = Unit(
    kind=UnitKind.FLOW,
    dimension=UnitDimension.CURRENCY,
    denominator="year",
    currency="USD",
    basis=UnitBasis.NOMINAL,
)
_UNIT_PEOPLE = Unit(kind=UnitKind.STOCK, dimension=UnitDimension.PEOPLE, basis=UnitBasis.NOMINAL)
_UNIT_CAGR = Unit(kind=UnitKind.INTENSIVE, dimension=UnitDimension.PERCENT, denominator="per-year")
_UNIT_SHARE = Unit(kind=UnitKind.DIMENSIONLESS, dimension=UnitDimension.PERCENT)

_GEO_US = Geo(level=GeoLevel.COUNTRY, codes=("US",))
_FAKE_SHA = "a" * 64


def _source(slug: str, tier: str = "regulator") -> StandardSource:
    return StandardSource(
        slug=slug,
        tier=tier,
        url="https://example.com",
        accessed=date(2024, 1, 1),
        snapshot_sha256=_FAKE_SHA,
    )


def _atomic(
    slug: str,
    value: float,
    *,
    unit: Unit = _UNIT_PEOPLE,
    as_of: date = date(2024, 1, 1),
    tier: str = "regulator",
) -> AtomicPrimitive:
    return AtomicPrimitive(
        kind="atomic_primitive",
        slug=slug,
        schema_version=1,
        concept_slug="test-concept",
        name=slug,
        description="synthetic test primitive",
        value=value,
        unit=unit,
        as_of=as_of,
        geo=_GEO_US,
        geo_perspective=GeoPerspective.DEMAND,
        source=_source(slug, tier),
    )


def _framework(slug: str, input_name: str) -> Framework:
    return Framework(
        kind="framework",
        slug=slug,
        schema_version=1,
        name=slug,
        method_family=MethodFamily.BOTTOMS_UP_SEATS,
        lens=AnalysisLens.COST_EFFICIENCY,
        inputs=(
            FrameworkInput(
                name=input_name,
                role=InputRole.BASE_VALUE,
                unit_signature=_UNIT_PEOPLE,
                required=True,
            ),
        ),
        formula=input_name,
        output_unit=_UNIT_USD_YEAR,
        applicable_to=("test-concept",),
        variants=(FrameworkVariant(scope="test-concept", default_inputs={input_name: input_name}),),
    )


def _concept(growth_index: str | None = None) -> Concept:
    return Concept(
        kind="concept",
        slug="test-concept",
        schema_version=1,
        name="Test Concept",
        definition="Synthetic concept for projection tests.",
        analysis_lens=ConceptAnalysisLens(primary=AnalysisLens.COST_EFFICIENCY),
        modifiers=ConceptModifiers(),
        growth_index=growth_index,
    )


def _registry(
    atomics: list[AtomicPrimitive], frameworks: list[Framework], concept: Concept
) -> Registry:
    return Registry(
        atomic={p.slug: p for p in atomics},
        composite={},
        concepts={concept.slug: concept},
        frameworks={fw.slug: fw for fw in frameworks},
        annotations={},
        tam_outputs={},
    )


def _real_registry() -> Registry:
    return Registry.from_loaded(load_data_dir(REPO_DATA))


# --- honest-gap behaviour -----------------------------------------------------


def test_no_growth_index_returns_none() -> None:
    base = _atomic("base", 100.0)
    reg = _registry([base], [_framework("fw", "base")], _concept(growth_index=None))
    assert project_tam(reg, "test-concept") is None


def test_missing_growth_primitive_returns_none() -> None:
    base = _atomic("base", 100.0)
    reg = _registry([base], [_framework("fw", "base")], _concept(growth_index="not-in-registry"))
    assert project_tam(reg, "test-concept") is None


def test_non_rate_growth_unit_returns_none() -> None:
    """A static percent share (no per-year denominator) must NOT be mistaken
    for a growth series."""
    base = _atomic("base", 100.0)
    share = _atomic("share", 0.6, unit=_UNIT_SHARE)
    reg = _registry([base, share], [_framework("fw", "base")], _concept(growth_index="share"))
    assert project_tam(reg, "test-concept") is None


# --- projection math ----------------------------------------------------------


def test_projection_compounds_today_by_cagr() -> None:
    base = _atomic("base", 100.0, as_of=date(2024, 6, 30))
    cagr = _atomic("cagr", 0.2, unit=_UNIT_CAGR)
    reg = _registry([base, cagr], [_framework("fw", "base")], _concept(growth_index="cagr"))
    proj = project_tam(reg, "test-concept", horizon_years=5)
    assert proj is not None
    assert proj.today.value == pytest.approx(100.0)
    assert proj.horizon.value == pytest.approx(100.0 * 1.2**5)  # 248.832
    assert proj.today.kind == "realized"
    assert proj.horizon.kind == "projected"
    assert proj.base_year == 2024
    assert proj.horizon_year == 2029
    assert proj.cagr == pytest.approx(0.2)
    assert proj.today.year == 2024 and proj.horizon.year == 2029


def test_base_year_is_latest_consumed_input_not_growth_rate() -> None:
    """base_year comes from the primitives the TAM consumed, not the CAGR's as_of."""
    base = _atomic("base", 100.0, as_of=date(2023, 1, 1))
    cagr = _atomic("cagr", 0.1, unit=_UNIT_CAGR, as_of=date(2025, 1, 1))
    reg = _registry([base, cagr], [_framework("fw", "base")], _concept(growth_index="cagr"))
    proj = project_tam(reg, "test-concept", horizon_years=3)
    assert proj is not None
    assert proj.base_year == 2023
    assert proj.horizon_year == 2026


def test_modeled_growth_raises_modeled_banner() -> None:
    base = _atomic("base", 100.0)
    cagr = _atomic("cagr", 0.2, unit=_UNIT_CAGR, tier="community-modeled")
    reg = _registry([base, cagr], [_framework("fw", "base")], _concept(growth_index="cagr"))
    proj = project_tam(reg, "test-concept")
    assert proj is not None
    assert proj.cagr_source_tier == "community-modeled"
    assert any(b.kind == BannerKind.MODELED for b in proj.banners)


def test_sourced_growth_has_no_modeled_banner() -> None:
    base = _atomic("base", 100.0)
    cagr = _atomic("cagr", 0.2, unit=_UNIT_CAGR, tier="regulator")
    reg = _registry([base, cagr], [_framework("fw", "base")], _concept(growth_index="cagr"))
    proj = project_tam(reg, "test-concept")
    assert proj is not None
    assert proj.cagr_source_tier == "regulator"
    assert not any(b.kind == BannerKind.MODELED for b in proj.banners)


def test_non_positive_horizon_raises() -> None:
    base = _atomic("base", 100.0)
    cagr = _atomic("cagr", 0.2, unit=_UNIT_CAGR)
    reg = _registry([base, cagr], [_framework("fw", "base")], _concept(growth_index="cagr"))
    with pytest.raises(EvaluatorError):
        project_tam(reg, "test-concept", horizon_years=0)


def test_unknown_concept_raises() -> None:
    reg = _registry([], [], _concept())
    with pytest.raises(EvaluatorError):
        project_tam(reg, "no-such-concept")


# --- real seeded data ---------------------------------------------------------


def test_real_ai_coding_concept_projects_with_modeled_banner() -> None:
    proj = project_tam(_real_registry(), "ai-coding-assistants-us", horizon_years=5)
    assert proj is not None
    assert proj.cagr == pytest.approx(0.22)
    assert proj.cagr_primitive == "ai-coding-assistant-spend-cagr-2024"
    assert proj.base_year == 2024
    assert proj.horizon_year == 2029
    # future > today, and the modeled CAGR is loudly flagged.
    assert proj.horizon.value > proj.today.value
    assert any(b.kind == BannerKind.MODELED for b in proj.banners)


def test_real_concept_without_growth_index_returns_none() -> None:
    # doc-gen-pc-insurance has no growth_index → honest gap, no fabricated future.
    assert project_tam(_real_registry(), "doc-gen-pc-insurance") is None


# --- chart builder ------------------------------------------------------------


def test_penetration_spec_has_realized_and_projected_series() -> None:
    from strata.evaluator import trajectory
    from strata.mcp.charts import penetration_spec

    reg = _real_registry()
    proj = project_tam(reg, "ai-coding-assistants-us")
    assert proj is not None
    spec = penetration_spec(trajectory(reg, "ai-coding-assistants-us"), proj)
    rows = spec["data"]["values"]
    series = {r["series"] for r in rows}
    assert series == {"realized", "projected"}
    # The projected leg connects the base year to the horizon year.
    projected_years = sorted(r["year"] for r in rows if r["series"] == "projected")
    assert projected_years == [proj.base_year, proj.horizon_year]


# --- MCP surface (size_tam carries today + future) ----------------------------


def test_mcp_size_tam_carries_projection_and_populated_chart() -> None:
    from mcp.types import CallToolResult

    from strata.mcp.tools import call_tool

    out = call_tool(_real_registry(), "size_tam", {"concept_slug": "ai-coding-assistants-us"})
    assert isinstance(out, CallToolResult) and out.structuredContent is not None
    payload = out.structuredContent
    proj = payload["projection"]
    assert proj["base_year"] == 2024 and proj["horizon_year"] == 2029
    assert proj["today"]["kind"] == "realized" and proj["horizon"]["kind"] == "projected"
    assert proj["horizon"]["value"] > proj["today"]["value"]
    # The once-dead penetration chart is now populated from real data.
    assert payload["charts"]["penetration"]["spec"]["data"]["values"]


def test_mcp_size_tam_projection_unavailable_without_growth_index() -> None:
    from mcp.types import CallToolResult

    from strata.mcp.tools import call_tool

    out = call_tool(_real_registry(), "size_tam", {"concept_slug": "doc-gen-pc-insurance"})
    assert isinstance(out, CallToolResult) and out.structuredContent is not None
    payload = out.structuredContent
    assert payload["projection"]["available"] is False
    # Honest gap → the penetration chart stays the empty placeholder.
    assert payload["charts"]["penetration"]["spec"]["data"]["values"] == []
