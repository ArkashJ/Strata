"""Tests for the connector dispatch registry (PR-B.3).

The registry bridges a router decision (connector + method + args) to a
validated AtomicPrimitive YAML dict. Coverage is pinned to
``all_capabilities()`` and the conversion path is exercised with fabricated
responses for the four named exemplar converters (BLS, FRED, FDIC, EDGAR),
which between them cover every positional shape the generic extractor handles:
a single object, an object pulled from a tuple field, and a whole tuple.
"""

from __future__ import annotations

from typing import Any

import pytest

from strata.connectors import _dispatch
from strata.connectors._capability import all_capabilities
from strata.connectors._dispatch import (
    CONNECTOR_DISPATCH,
    DispatchEntry,
    call_and_convert,
)
from strata.models import AtomicPrimitive

# ── coverage ──────────────────────────────────────────────────────────────


def test_dispatch_covers_exactly_all_capabilities() -> None:
    expected = {(s.connector, s.method) for s in all_capabilities()}
    assert set(CONNECTOR_DISPATCH) == expected


def test_every_entry_has_callable_factory_and_converter() -> None:
    for key, entry in CONNECTOR_DISPATCH.items():
        assert callable(entry.client_factory), key
        assert callable(entry.converter), key


# ── converter selection (multi-converter connectors) ───────────────────────


def test_multi_converter_connectors_select_the_right_converter() -> None:
    from strata.connectors import (
        concept_to_primitive_yaml,
        firm_to_primitive_yaml,
        frame_to_primitive_yaml,
        industry_to_primitive_yaml,
        passenger_count_to_primitive_yaml,
        spending_to_primitive_yaml,
    )

    assert CONNECTOR_DISPATCH[("census", "get_cbp")].converter is industry_to_primitive_yaml
    assert CONNECTOR_DISPATCH[("census", "get_susb")].converter is firm_to_primitive_yaml
    assert CONNECTOR_DISPATCH[("cms", "get_spending")].converter is spending_to_primitive_yaml
    assert (
        CONNECTOR_DISPATCH[("edgar", "get_company_concept")].converter is concept_to_primitive_yaml
    )
    assert CONNECTOR_DISPATCH[("edgar", "get_frames")].converter is frame_to_primitive_yaml
    assert (
        CONNECTOR_DISPATCH[("faa", "get_total_passengers")].converter
        is passenger_count_to_primitive_yaml
    )


# ── client factory ──────────────────────────────────────────────────────────


def test_factory_passes_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Recorder:
        def __init__(self, *, api_key: str | None = None) -> None:
            captured["api_key"] = api_key

    monkeypatch.setenv("STRATA_BLS_API_KEY", "secret-key")
    _dispatch.build_factory("bls", Recorder)()
    assert captured["api_key"] == "secret-key"


def test_factory_constructs_bare_when_ctor_takes_no_credential() -> None:
    constructed: dict[str, bool] = {}

    class NoCred:
        def __init__(self) -> None:
            constructed["ok"] = True

    _dispatch.build_factory("cms", NoCred)()
    assert constructed["ok"] is True


def test_factory_honors_non_api_key_credential_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Recorder:
        def __init__(self, *, subscription_key: str | None = None) -> None:
            captured["subscription_key"] = subscription_key

    monkeypatch.setenv("STRATA_COMTRADE_API_KEY", "sub-key")
    _dispatch.build_factory("comtrade", Recorder)()
    assert captured["subscription_key"] == "sub-key"


def test_registry_factories_construct_real_clients() -> None:
    from strata.connectors import BLSClient, FREDClient

    with CONNECTOR_DISPATCH[("bls", "get_series")].client_factory() as bls:
        assert isinstance(bls, BLSClient)
    with CONNECTOR_DISPATCH[("fred", "get_observations")].client_factory() as fred:
        assert isinstance(fred, FREDClient)


# ── call_and_convert: the four named exemplars ─────────────────────────────


def _use_fake(
    monkeypatch: pytest.MonkeyPatch,
    key: tuple[str, str],
    fake_client: object,
    converter: Any,
) -> None:
    monkeypatch.setitem(
        CONNECTOR_DISPATCH,
        key,
        DispatchEntry(client_factory=lambda: fake_client, converter=converter),
    )


def test_call_and_convert_bls_single_object_from_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.connectors import series_to_primitive_yaml
    from strata.connectors.bls import BLSResponse, BLSStatus, DataPoint, Series

    point = DataPoint(year=2024, period="A01", period_name="Annual", value=164850.0, latest=True)
    resp = BLSResponse(
        status=BLSStatus.REQUEST_SUCCEEDED,
        response_time_ms=12,
        messages=(),
        series=(Series(series_id="OEUS000000000000015125201", data=(point,)),),
    )

    class FakeBLS:
        def __enter__(self) -> FakeBLS:
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def get_series(self, series_id: str) -> BLSResponse:
            assert series_id == "OEUS000000000000015125201"
            return resp

    _use_fake(monkeypatch, ("bls", "get_series"), FakeBLS(), series_to_primitive_yaml)

    out = call_and_convert(
        "bls",
        "get_series",
        {
            "series_id": "OEUS000000000000015125201",
            "concept_slug": "software-eng-productivity",
            "primitive_slug": "bls-test-devs-2024",
            "name": "US software developers",
            "description": "BLS OES employment count.",
            "source_url": "https://www.bls.gov/oes/",
            "unit_dimension": "people",
        },
    )

    assert out["value"] == 164850.0
    assert out["slug"] == "bls-test-devs-2024"
    AtomicPrimitive.model_validate(out)


def test_call_and_convert_fred_two_positionals(monkeypatch: pytest.MonkeyPatch) -> None:
    # FakeFRED is intentionally NOT a context manager -> exercises the
    # nullcontext fallback path in call_and_convert.
    from strata.connectors import observations_to_primitive_yaml
    from strata.connectors.fred import FREDResponse, Observation, SeriesInfo

    info = SeriesInfo(
        id="GDP",
        title="Gross Domestic Product",
        frequency="Quarterly",
        frequency_short="Q",
        units="Billions of Dollars",
        units_short="Bil. $",
        seasonal_adjustment="Seasonally Adjusted Annual Rate",
        seasonal_adjustment_short="SAAR",
        observation_start="1947-01-01",
        observation_end="2023-10-01",
        last_updated="2024-01-25",
    )
    resp = FREDResponse(
        status="ok",
        observations=(Observation(date="2023-01-01", value=27000.0),),
        series_list=(info,),
    )

    class FakeFRED:
        def get_observations(self, series_id: str) -> FREDResponse:
            assert series_id == "GDP"
            return resp

    _use_fake(monkeypatch, ("fred", "get_observations"), FakeFRED(), observations_to_primitive_yaml)

    out = call_and_convert(
        "fred",
        "get_observations",
        {
            "series_id": "GDP",
            "concept_slug": "us-gdp",
            "primitive_slug": "fred-gdp-2023",
            "name": "US nominal GDP",
            "description": "FRED nominal GDP.",
            "source_url": "https://fred.stlouisfed.org/series/GDP",
        },
    )

    assert out["value"] == 27000.0
    assert out["slug"] == "fred-gdp-2023"
    AtomicPrimitive.model_validate(out)


def test_call_and_convert_fdic_financial(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.connectors import financial_to_primitive_yaml
    from strata.connectors.fdic import FDICResponse, FinancialRecord

    record = FinancialRecord(
        cert=628,
        name="JPMorgan Chase Bank",
        report_date="20231231",
        assets=3500000.0,
        deposits=2400000.0,
        net_income=49000.0,
        interest_income=90000.0,
        non_interest_income=50000.0,
        roa=1.3,
        roe=15.0,
        state="OH",
        city="Columbus",
    )
    resp = FDICResponse(kind="financials", financials=(record,))

    class FakeFDIC:
        def __enter__(self) -> FakeFDIC:
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def get_total_assets(self, report_date: str) -> FDICResponse:
            return resp

    _use_fake(monkeypatch, ("fdic", "get_total_assets"), FakeFDIC(), financial_to_primitive_yaml)

    out = call_and_convert(
        "fdic",
        "get_total_assets",
        {
            "report_date": "20231231",
            "concept_slug": "us-bank-assets",
            "primitive_slug": "fdic-jpm-asset-2023",
            "name": "JPMorgan total assets",
            "description": "FDIC reported total assets.",
        },
    )

    assert out["value"] == 3500000.0
    AtomicPrimitive.model_validate(out)


def test_call_and_convert_edgar_concept(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.connectors import concept_to_primitive_yaml
    from strata.connectors.edgar import CompanyConcept, EDGARResponse, Fact

    fact = Fact(
        value=383285000000.0,
        form="10-K",
        filed="2023-11-03",
        frame="CY2023",
        fiscal_year=2023,
        fiscal_period="FY",
    )
    concept = CompanyConcept(
        cik="320193",
        entity_name="Apple Inc.",
        taxonomy="us-gaap",
        tag="Revenues",
        label="Revenues",
        description="Total net sales.",
        units={"USD": (fact,)},
    )
    resp = EDGARResponse(kind="concept", concept=concept)

    class FakeEDGAR:
        def __enter__(self) -> FakeEDGAR:
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def get_company_concept(self, cik: str, taxonomy: str, tag: str) -> EDGARResponse:
            return resp

    _use_fake(monkeypatch, ("edgar", "get_company_concept"), FakeEDGAR(), concept_to_primitive_yaml)

    out = call_and_convert(
        "edgar",
        "get_company_concept",
        {
            "cik": "320193",
            "taxonomy": "us-gaap",
            "tag": "Revenues",
            "concept_slug": "apple-revenue",
            "primitive_slug": "edgar-aapl-rev-2023",
            "name": "Apple FY2023 revenue",
            "description": "SEC 10-K total net sales.",
            "source_url": "https://www.sec.gov/cgi-bin/browse-edgar",
            "year": 2023,
        },
    )

    assert out["value"] == 383285000000.0
    AtomicPrimitive.model_validate(out)


# ── error paths ─────────────────────────────────────────────────────────────


def test_unknown_connector_method_raises() -> None:
    with pytest.raises(ValueError, match="no dispatch entry"):
        call_and_convert("does_not_exist", "nope", {})
