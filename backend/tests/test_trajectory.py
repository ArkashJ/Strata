"""Tests for the TAM-over-time trajectory endpoint and evaluator function.

Coverage:
- monotonic as_of dates in returned points
- point omitted when a required input is not yet available at the cutoff date
- empty points when no framework is ever fully satisfiable
- value within [low, high] for every point
- concept with >=2 satisfiable dates yields >=2 points
- HTTP endpoint returns 200 with correct shape
- HTTP endpoint returns 422 for unknown concept
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.evaluator import EvaluatorError, trajectory
from strata.loader import load_data_dir
from strata.models import (
    AnalysisLens,
    AtomicPrimitive,
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
from strata.models.framework import HorizonClass
from strata.models.geo import Geo, GeoLevel, GeoPerspective
from strata.registry import Registry

REPO_DATA = Path(__file__).resolve().parents[2] / "data"

# --- helpers ------------------------------------------------------------------

_UNIT_USD_YEAR = Unit(
    kind=UnitKind.FLOW,
    dimension=UnitDimension.CURRENCY,
    denominator="year",
    currency="USD",
    basis=UnitBasis.NOMINAL,
)

_UNIT_PEOPLE = Unit(
    kind=UnitKind.STOCK,
    dimension=UnitDimension.PEOPLE,
    basis=UnitBasis.NOMINAL,
)

_GEO_US = Geo(level=GeoLevel.COUNTRY, codes=("US",))

_FAKE_SHA = "a" * 64


def _source(slug: str) -> StandardSource:
    return StandardSource(
        slug=slug,
        tier="regulator",
        url="https://example.com",
        accessed=date(2024, 1, 1),
        snapshot_sha256=_FAKE_SHA,
    )


def _atomic(slug: str, value: float, as_of: date) -> AtomicPrimitive:
    return AtomicPrimitive(
        kind="atomic_primitive",
        slug=slug,
        schema_version=1,
        concept_slug="test-concept",
        name=slug,
        description="synthetic test primitive",
        value=value,
        unit=_UNIT_PEOPLE,
        as_of=as_of,
        geo=_GEO_US,
        geo_perspective=GeoPerspective.DEMAND,
        source=_source(slug),
    )


def _framework(slug: str, input_name: str, lens: AnalysisLens) -> Framework:
    return Framework(
        kind="framework",
        slug=slug,
        schema_version=1,
        name=slug,
        method_family=MethodFamily.BOTTOMS_UP_SEATS,
        lens=lens,
        inputs=(
            FrameworkInput(
                name=input_name,
                role=InputRole.BASE_VALUE,
                unit_signature=_UNIT_PEOPLE,
                required=True,
            ),
        ),
        formula=f"product({input_name})",
        output_unit=_UNIT_USD_YEAR,
        applicable_to=("test-concept",),
        variants=(
            FrameworkVariant(
                scope="test-concept",
                default_inputs={input_name: input_name},
            ),
        ),
        horizon_class=HorizonClass.SNAPSHOT,
    )


def _concept(primary_lens: AnalysisLens, secondary_lens: AnalysisLens | None = None) -> Concept:
    return Concept(
        kind="concept",
        slug="test-concept",
        schema_version=1,
        name="Test Concept",
        definition="Synthetic concept for trajectory tests.",
        analysis_lens=ConceptAnalysisLens(primary=primary_lens, secondary=secondary_lens),
        modifiers=ConceptModifiers(),
    )


def _registry_from(
    atomics: list[AtomicPrimitive],
    frameworks: list[Framework],
    concept: Concept | None = None,
) -> Registry:
    c = concept or _concept(AnalysisLens.COST_EFFICIENCY)
    return Registry(
        atomic={p.slug: p for p in atomics},
        composite={},
        concepts={c.slug: c},
        frameworks={fw.slug: fw for fw in frameworks},
        annotations={},
        tam_outputs={},
    )


def _real_registry() -> Registry:
    return Registry.from_loaded(load_data_dir(REPO_DATA))


# --- unit tests: evaluator trajectory() function ----------------------------


def test_trajectory_dates_are_monotonically_increasing() -> None:
    """Points must be sorted ascending by as_of date."""
    p1 = _atomic("p1", 10.0, date(2023, 1, 1))
    p2 = _atomic("p2", 20.0, date(2024, 1, 1))
    fw1 = _framework("fw1", "p1", AnalysisLens.COST_EFFICIENCY)
    fw2 = _framework("fw2", "p2", AnalysisLens.COST_EFFICIENCY)
    reg = _registry_from([p1, p2], [fw1, fw2], _concept(AnalysisLens.COST_EFFICIENCY))
    result = trajectory(reg, "test-concept")
    dates = [pt.as_of for pt in result.points]
    assert dates == sorted(dates)


def test_trajectory_point_omitted_when_input_not_yet_available() -> None:
    """A framework that requires a later primitive must be skipped at the early date.

    fw1 needs p1 (date1=2023) — satisfiable at date1 and date2.
    fw2 needs p2 (date2=2024) — only satisfiable at date2.
    Both frameworks' primitives are in candidate_slugs, so dates = {2023, 2024}.
    At date1: fw2 is skipped (p2 not yet available); only fw1 fires → 1 point.
    At date2: both fire → 1 point.
    Total: 2 points, but date1 point only has 1 scenario.
    """
    p1 = _atomic("p1", 10.0, date(2023, 1, 1))
    p2 = _atomic("p2", 20.0, date(2024, 1, 1))
    fw1 = _framework("fw1", "p1", AnalysisLens.COST_EFFICIENCY)
    fw2 = _framework("fw2", "p2", AnalysisLens.COST_EFFICIENCY)
    reg = _registry_from([p1, p2], [fw1, fw2], _concept(AnalysisLens.COST_EFFICIENCY))
    result = trajectory(reg, "test-concept")
    # Both dates produce a satisfiable scenario (fw1 covers date1; both cover date2).
    assert len(result.points) == 2
    early = result.points[0]
    late = result.points[1]
    assert early.as_of == date(2023, 1, 1)
    assert early.scenarios_n == 1  # only fw1 satisfiable
    assert late.as_of == date(2024, 1, 1)
    assert late.scenarios_n == 2  # both frameworks satisfiable


def test_trajectory_empty_when_all_frameworks_require_later_primitives() -> None:
    """When all framework inputs arrive at the same (only) date, there is exactly
    one satisfiable point — not zero.  To get empty points we need a concept
    whose required inputs are never all available simultaneously, which we
    model by having the framework reference a primitive that doesn't exist in
    the registry.
    """
    # Build a framework that references a missing primitive.
    fw = _framework("fw1", "missing-primitive", AnalysisLens.COST_EFFICIENCY)
    # candidate_slugs will contain "missing-primitive", but it's not in registry.
    # So dates = {} (empty set) → points = [].
    reg = _registry_from([], [fw], _concept(AnalysisLens.COST_EFFICIENCY))
    result = trajectory(reg, "test-concept")
    assert result.points == []


def test_trajectory_value_within_low_high_for_every_point() -> None:
    """value == mean of scenario values; low/high are min/max; value ∈ [low, high]."""
    p1 = _atomic("p1", 10.0, date(2023, 1, 1))
    p2 = _atomic("p2", 30.0, date(2023, 1, 1))
    fw1 = _framework("fw1", "p1", AnalysisLens.COST_EFFICIENCY)
    fw2 = _framework("fw2", "p2", AnalysisLens.COST_EFFICIENCY)
    reg = _registry_from([p1, p2], [fw1, fw2], _concept(AnalysisLens.COST_EFFICIENCY))
    result = trajectory(reg, "test-concept")
    assert len(result.points) >= 1
    for pt in result.points:
        assert pt.low <= pt.value <= pt.high


def test_trajectory_two_distinct_dates_yield_two_points() -> None:
    """Concept with primitives at two dates where BOTH dates are satisfiable yields
    exactly 2 points.

    fw1 requires p1 (date1=2023).
    fw2 requires p2 (date2=2024).
    candidate_slugs = {p1, p2} → sorted dates = [2023, 2024].
    At date1: fw1 satisfies (p1 ≤ 2023), fw2 does NOT (p2 > 2023) → 1 scenario.
    At date2: both satisfy → 2 scenarios.
    → 2 points total.
    """
    p1 = _atomic("p1", 100.0, date(2023, 6, 30))
    p2 = _atomic("p2", 200.0, date(2024, 6, 30))
    fw1 = _framework("fw1", "p1", AnalysisLens.COST_EFFICIENCY)
    fw2 = _framework("fw2", "p2", AnalysisLens.COST_EFFICIENCY)
    reg = _registry_from([p1, p2], [fw1, fw2], _concept(AnalysisLens.COST_EFFICIENCY))
    result = trajectory(reg, "test-concept")
    assert len(result.points) >= 2


def test_trajectory_unknown_concept_raises() -> None:
    reg = _registry_from([], [])
    with pytest.raises(EvaluatorError):
        trajectory(reg, "no-such-concept")


def test_trajectory_real_concept_has_non_empty_metadata() -> None:
    """doc-gen-pc-insurance should return concept_slug and concept_name correctly."""
    result = trajectory(_real_registry(), "doc-gen-pc-insurance")
    assert result.concept_slug == "doc-gen-pc-insurance"
    assert result.concept_name == "P&C insurance document generation"
    assert result.unit is not None


def test_trajectory_real_concept_points_satisfiable() -> None:
    """doc-gen-pc-insurance has primitives at two distinct dates; at least the
    latest date (2024-12-31) must yield a satisfiable point since all framework
    inputs have as_of <= 2024-12-31.
    """
    result = trajectory(_real_registry(), "doc-gen-pc-insurance")
    # At a minimum the 2024-12-31 snapshot should be resolvable.
    assert len(result.points) >= 1
    for pt in result.points:
        assert pt.low <= pt.value <= pt.high
        assert pt.scenarios_n >= 1
        assert len(pt.method_families) >= 1


# --- integration tests: HTTP endpoint ----------------------------------------


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_trajectory_endpoint_200(client: AsyncClient) -> None:
    resp = await client.get("/build/doc-gen-pc-insurance/trajectory")
    assert resp.status_code == 200
    body = resp.json()
    assert body["concept_slug"] == "doc-gen-pc-insurance"
    assert "points" in body
    assert isinstance(body["points"], list)
    assert "unit" in body


@pytest.mark.asyncio
async def test_trajectory_endpoint_point_shape(client: AsyncClient) -> None:
    """Each point must contain all required fields with correct types."""
    resp = await client.get("/build/doc-gen-pc-insurance/trajectory")
    assert resp.status_code == 200
    body = resp.json()
    for pt in body["points"]:
        assert "as_of" in pt
        assert "value" in pt
        assert "low" in pt
        assert "high" in pt
        assert "method_families" in pt
        assert "scenarios_n" in pt
        assert isinstance(pt["method_families"], list)
        assert pt["low"] <= pt["value"] <= pt["high"]


@pytest.mark.asyncio
async def test_trajectory_endpoint_422_unknown_concept(client: AsyncClient) -> None:
    resp = await client.get("/build/no-such-concept/trajectory")
    assert resp.status_code == 422
