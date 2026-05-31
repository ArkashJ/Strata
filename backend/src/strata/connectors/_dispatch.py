"""Connector dispatch registry (spec PR-B.3).

Bridges a router ``RoutingDecision`` (connector + method + args) to the data
bank: instantiate the connector client, call the chosen method, and convert
the typed response into a validated AtomicPrimitive YAML dict.

Coverage is driven by :func:`._capability.all_capabilities` — every
router-visible ``(connector, method)`` pair gets exactly one
:class:`DispatchEntry`. ``tests/test_dispatch.py`` asserts the registry keys
and the capability set are identical, so a new capability without a dispatch
entry fails CI.

Two things are non-uniform and handled here:

- **Client construction.** Most ctors accept ``api_key`` and are built as
  ``Client(api_key=os.getenv("STRATA_<X>_API_KEY"))``. Connectors that name
  the credential differently (Comtrade ``subscription_key``, GitHub ``token``,
  ...) are listed in ``_CREDENTIALS``; clients that take no credential are
  built bare. The factory introspects the ctor and only passes a kwarg the
  ctor actually declares.

- **Converters.** Each takes one or more positional domain objects (BLS
  ``Series``; FRED ``(SeriesInfo, tuple[Observation, ...])``; EDGAR frame
  ``tuple[FrameEntry, ...]``) followed by keyword-only metadata.
  :func:`call_and_convert` fills the positionals by type-matching the
  response's dataclass fields and routes the remaining ``args`` to the
  keyword-only metadata params.

``args`` therefore carries *both* the method-call arguments (from the router)
*and* the converter metadata (concept_slug, primitive_slug, name, ...) that the
caller supplies; the split is done by signature introspection.
"""

from __future__ import annotations

import contextlib
import dataclasses
import inspect
import os
import typing
from collections.abc import Callable
from typing import Any

from ..models import AtomicPrimitive
from . import (
    AlphaVantageClient,
    BLSClient,
    CensusClient,
    CMSClient,
    ComtradeClient,
    DuneClient,
    EDGARClient,
    EIAClient,
    EurostatClient,
    FAAClient,
    FDICClient,
    FREDClient,
    GitHubClient,
    KalshiClient,
    NasdaqDataLinkClient,
    NASSClient,
    OECDClient,
    OpenFDAClient,
    RedditClient,
    StackExchangeClient,
    TwitterClient,
    WorldBankClient,
    YFinanceClient,
    airport_to_primitive_yaml,
    concept_to_primitive_yaml,
    datapoint_to_primitive_yaml,
    dune_run_query_result_to_primitive_yaml,
    enrollment_to_primitive_yaml,
    event_count_to_primitive_yaml,
    financial_to_primitive_yaml,
    firm_to_primitive_yaml,
    frame_to_primitive_yaml,
    indicator_to_primitive_yaml,
    industry_to_primitive_yaml,
    market_cap_to_primitive_yaml,
    market_to_primitive_yaml,
    nasdaq_observation_to_primitive_yaml,
    nass_record_to_primitive_yaml,
    observation_to_primitive_yaml,
    observations_to_primitive_yaml,
    oecd_observation_to_primitive_yaml,
    passenger_count_to_primitive_yaml,
    quote_to_primitive_yaml,
    repo_to_primitive_yaml,
    series_to_primitive_yaml,
    spending_to_primitive_yaml,
    subreddit_to_primitive_yaml,
    tag_to_primitive_yaml,
    trade_to_primitive_yaml,
    user_to_primitive_yaml,
)
from ._capability import all_capabilities

Converter = Callable[..., dict[str, Any]]
ClientFactory = Callable[[], Any]


@dataclasses.dataclass(frozen=True)
class DispatchEntry:
    """How to run one ``(connector, method)``: build a client, then convert."""

    client_factory: ClientFactory
    converter: Converter


# connector → client class.
_CLIENTS: dict[str, type] = {
    "alpha_vantage": AlphaVantageClient,
    "bls": BLSClient,
    "census": CensusClient,
    "cms": CMSClient,
    "comtrade": ComtradeClient,
    "dune": DuneClient,
    "edgar": EDGARClient,
    "eia": EIAClient,
    "eurostat": EurostatClient,
    "faa": FAAClient,
    "fdic": FDICClient,
    "fred": FREDClient,
    "github": GitHubClient,
    "kalshi": KalshiClient,
    "nasdaq_data_link": NasdaqDataLinkClient,
    "oecd": OECDClient,
    "openfda": OpenFDAClient,
    "reddit": RedditClient,
    "stack_exchange": StackExchangeClient,
    "twitter": TwitterClient,
    "usda_nass": NASSClient,
    "worldbank": WorldBankClient,
    "yfinance": YFinanceClient,
}

# connector → converter used for all of its methods unless overridden below.
_DEFAULT_CONVERTERS: dict[str, Converter] = {
    "alpha_vantage": market_cap_to_primitive_yaml,
    "bls": series_to_primitive_yaml,
    "census": industry_to_primitive_yaml,
    "cms": enrollment_to_primitive_yaml,
    "comtrade": trade_to_primitive_yaml,
    "dune": dune_run_query_result_to_primitive_yaml,
    "edgar": concept_to_primitive_yaml,
    "eia": datapoint_to_primitive_yaml,
    "eurostat": observation_to_primitive_yaml,
    "faa": airport_to_primitive_yaml,
    "fdic": financial_to_primitive_yaml,
    "fred": observations_to_primitive_yaml,
    "github": repo_to_primitive_yaml,
    "kalshi": market_to_primitive_yaml,
    "nasdaq_data_link": nasdaq_observation_to_primitive_yaml,
    "oecd": oecd_observation_to_primitive_yaml,
    "openfda": event_count_to_primitive_yaml,
    "reddit": subreddit_to_primitive_yaml,
    "stack_exchange": tag_to_primitive_yaml,
    "twitter": user_to_primitive_yaml,
    "usda_nass": nass_record_to_primitive_yaml,
    "worldbank": indicator_to_primitive_yaml,
    "yfinance": quote_to_primitive_yaml,
}

# (connector, method) → converter, for connectors that expose more than one
# convertible shape. Anything not listed falls back to _DEFAULT_CONVERTERS.
_CONVERTER_OVERRIDES: dict[tuple[str, str], Converter] = {
    ("census", "get_susb"): firm_to_primitive_yaml,
    ("cms", "get_spending"): spending_to_primitive_yaml,
    ("cms", "get_national_health_expenditure"): spending_to_primitive_yaml,
    ("edgar", "get_frames"): frame_to_primitive_yaml,
    ("faa", "get_total_passengers"): passenger_count_to_primitive_yaml,
}

# connector → ordered (ctor_param, env_var) credentials the factory passes when
# the ctor declares the param. Connectors absent here use the api_key default.
_CREDENTIALS: dict[str, tuple[tuple[str, str], ...]] = {
    "comtrade": (("subscription_key", "STRATA_COMTRADE_API_KEY"),),
    "github": (("token", "STRATA_GITHUB_TOKEN"),),
    "twitter": (("bearer_token", "STRATA_TWITTER_BEARER_TOKEN"),),
    "reddit": (
        ("client_id", "STRATA_REDDIT_CLIENT_ID"),
        ("client_secret", "STRATA_REDDIT_CLIENT_SECRET"),
    ),
}


def _build_factory(connector: str, client_cls: type) -> ClientFactory:
    """Make a zero-arg factory that constructs ``client_cls`` with credentials.

    Only kwargs the ctor actually declares are passed, so credential-free
    clients are built bare and the call never raises on an unexpected kwarg.
    """
    params = inspect.signature(client_cls).parameters
    creds = _CREDENTIALS.get(connector, (("api_key", f"STRATA_{connector.upper()}_API_KEY"),))
    accepted = tuple((param, env) for param, env in creds if param in params)

    def factory() -> Any:
        return client_cls(**{param: os.getenv(env) for param, env in accepted})

    return factory


# Public alias: lets callers/tests build a single client factory in isolation
# without reaching into a private name across module boundaries.
build_factory = _build_factory


def _converter_for(connector: str, method: str) -> Converter:
    override = _CONVERTER_OVERRIDES.get((connector, method))
    return override if override is not None else _DEFAULT_CONVERTERS[connector]


def _build_dispatch() -> dict[tuple[str, str], DispatchEntry]:
    factories = {conn: _build_factory(conn, cls) for conn, cls in _CLIENTS.items()}
    table: dict[tuple[str, str], DispatchEntry] = {}
    for spec in all_capabilities():
        table[(spec.connector, spec.method)] = DispatchEntry(
            client_factory=factories[spec.connector],
            converter=_converter_for(spec.connector, spec.method),
        )
    return table


CONNECTOR_DISPATCH: dict[tuple[str, str], DispatchEntry] = _build_dispatch()


def _response_field_values(response: Any) -> list[Any]:
    if dataclasses.is_dataclass(response) and not isinstance(response, type):
        return [getattr(response, f.name) for f in dataclasses.fields(response)]
    return list(vars(response).values())


def _match_positional(annotation: Any, response: Any, param_name: str) -> Any:
    """Find the response field that satisfies one converter positional param.

    ``tuple[X, ...]`` matches a tuple/list field of ``X`` and is passed whole;
    a plain class matches a field of that type, or the first element of a
    tuple/list field of that type.
    """
    values = _response_field_values(response)
    origin = typing.get_origin(annotation)

    if origin in (tuple, list):
        type_args = typing.get_args(annotation)
        elem: Any = type_args[0] if type_args else object
        for val in values:
            if isinstance(val, (tuple, list)) and val and isinstance(val[0], elem):
                return tuple(val) if origin is tuple else list(val)
        raise ValueError(
            f"converter positional {param_name!r} expects a sequence of "
            f"{getattr(elem, '__name__', elem)!r}; response had none"
        )

    for val in values:
        if isinstance(val, annotation):
            return val
    for val in values:
        if isinstance(val, (tuple, list)) and val and isinstance(val[0], annotation):
            return val[0]
    raise ValueError(
        f"converter positional {param_name!r} expects "
        f"{getattr(annotation, '__name__', annotation)!r}; response had none"
    )


def call_and_convert(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run a connector method and convert its response to an AtomicPrimitive.

    ``args`` carries both the method-call arguments and the converter
    metadata; they are split by signature: keyword-only converter params are
    taken as converter metadata, everything else is passed to the method.

    Returns the AtomicPrimitive YAML dict (validated before return). Raises
    ``ValueError`` for an unknown ``(connector, method)`` or when the response
    lacks a field matching a converter positional.
    """
    entry = CONNECTOR_DISPATCH.get((connector, method))
    if entry is None:
        raise ValueError(f"no dispatch entry for connector={connector!r} method={method!r}")

    converter = entry.converter
    sig = inspect.signature(converter)
    converter_param_names = set(sig.parameters)
    keyword_only = {
        name for name, p in sig.parameters.items() if p.kind is inspect.Parameter.KEYWORD_ONLY
    }
    converter_kwargs = {k: v for k, v in args.items() if k in keyword_only}
    method_args = {k: v for k, v in args.items() if k not in converter_param_names}

    client = entry.client_factory()
    cm = client if hasattr(client, "__enter__") else contextlib.nullcontext(client)
    with cm as active:
        response = getattr(active, method)(**method_args)

    hints = typing.get_type_hints(converter)
    positionals = [
        _match_positional(hints.get(p.name, p.annotation), response, p.name)
        for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]

    yaml_dict = converter(*positionals, **converter_kwargs)
    AtomicPrimitive.model_validate(yaml_dict)
    return yaml_dict
