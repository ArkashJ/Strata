"""FastAPI application factory. Exposes `create_app()` and a module-level `app`."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from strata import __version__
from strata.api.routes import (
    audit,
    build,
    concepts,
    connectors,
    contribute,
    frameworks,
    healthz,
    integrations,
    lineage,
    me,
    portfolio,
    primitives,
    report,
    resolve,
    signals,
    usage,
)
from strata.config import settings
from strata.logging import configure_logging, get_logger

load_dotenv()

log = get_logger(__name__)

# Per-tag descriptions surfaced in /docs and /redoc. One entry per router tag so
# the spec groups endpoints with a human explanation instead of a bare label.
OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "health", "description": "Liveness and LLM-backend health probes."},
    {
        "name": "concepts",
        "description": "Curated market concepts and their competing measurements.",
    },
    {
        "name": "report",
        "description": "Question-driven market reports — sourced or TAM-derived answers to curated analysis questions, never LLM-authored.",
    },
    {
        "name": "primitives",
        "description": "Atomic and composite sourced primitives (value + unit + SHA256-pinned source).",
    },
    {
        "name": "signals",
        "description": "Quarantined prediction-market signals — surfaced read-only, never fed into a TAM.",
    },
    {
        "name": "frameworks",
        "description": "Parameterized TAM recipes (the six analysis lenses) and their variants.",
    },
    {
        "name": "build",
        "description": "Interactive TAM composition: size a concept, recompute with what-if overrides, browse/promote frozen artifacts.",
    },
    {
        "name": "resolve",
        "description": "Dynamic natural-language market resolution via Claude + Exa, streamed over SSE.",
    },
    {"name": "audit", "description": "Recent resolve/recompute audit events."},
    {"name": "ops", "description": "Per-org usage metering and Prometheus metrics."},
    {
        "name": "integrations",
        "description": "Inbound OAuth connectors (SaaS) producing org-private first-party primitives. Authentication required.",
    },
    {
        "name": "connectors",
        "description": "Catalog of typed ingest connectors cross-referenced with the live data bank.",
    },
    {
        "name": "contribute",
        "description": "Validator-gated community contribution intake and review queue.",
    },
    {"name": "portfolio", "description": "Portfolio company sizing (cached demo subset)."},
]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    log.info("strata.startup", env=settings.env, version=__version__)

    if settings.env == "prod":
        from strata.registry import Registry

        log.info("strata.registry.loading_from_db")
        application.state.registry = await Registry.from_db()
        log.info("strata.registry.loaded_from_db")

    # Run the mounted MCP server's session-manager lifespan alongside the API
    # (Wave 5A). Mounted sub-apps don't get their lifespan run automatically, so
    # delegate to it here; the hosted /mcp transport is local-trust until the
    # Wave-3 API-key middleware gates it.
    mcp_app = getattr(application.state, "mcp_app", None)
    if mcp_app is not None:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    else:
        yield
    log.info("strata.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Strata API",
        version=__version__,
        description=(
            "Proprietary curated market-sizing engine for VCs and operators.\n\n"
            "**Data bank:** 307 atomic primitives from BLS, FRED, Census, EDGAR, and World Bank. "
            "All SHA256-pinned to source snapshots.\n\n"
            "**Six TAM lenses:** cost_efficiency, revenue_generation, latent_demand, "
            "platform_throughput, bundle_consolidation, productivity_uplift.\n\n"
            "**Dynamic resolution:** POST /resolve accepts natural language market queries, "
            "parses them into lens + primitives via Claude, searches for data via Exa, "
            "and streams results via SSE."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "Strata", "email": "arkash@benmore.tech"},
        license_info={"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
    )

    # AC3.4: CORS must not be wildcard in prod. A "*" origin list in prod is a
    # misconfiguration — narrow to the explicit regex (Vercel previews) only, so
    # an unconfigured prod deploy fails closed rather than open.
    cors_origins = settings.cors_origins
    cors_origin_regex = settings.cors_origin_regex
    if settings.env == "prod" and cors_origins == ["*"]:
        log.warning("strata.cors.wildcard_blocked_in_prod")
        cors_origins = []
        # An unconfigured prod deploy would otherwise fail closed and block the
        # deployed frontend entirely (the "stratabank.vercel.app is empty" bug:
        # the API has data but the browser can't read it without an allow-origin
        # header). Default to the canonical Strata Vercel domains — the named
        # production app and any ``strata-<hash>`` preview deploy. Still fully
        # overridable via STRATA_CORS_ORIGIN / STRATA_CORS_ORIGIN_REGEX.
        if not cors_origin_regex:
            cors_origin_regex = r"https://(stratabank|strata-[a-z0-9-]+)\.vercel\.app"
    elif settings.env != "prod" and not cors_origin_regex:
        # Dev/test: `next dev` grabs whatever localhost port is free (3000,
        # 3001, 3008, ...), so an exact-origin list silently breaks the app
        # with CORS preflight failures whenever the port drifts. Allow any
        # localhost origin in non-prod only; prod stays locked to its regex.
        cors_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # AC3.5/AC3.3: request-id + structured timing log + per-org metering.
    @app.middleware("http")
    async def _observability(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Any
    ) -> Any:
        from strata.api.auth import principal_for
        from strata.api.metering import get_meter

        request_id = uuid4().hex
        request.state.request_id = request_id
        start = perf_counter()
        try:
            principal = principal_for(request)
            org_id = principal.org_id
        except HTTPException:
            org_id = "public"
        response = await call_next(request)
        elapsed_ms = (perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id
        # Meter only the real API surface (skip docs/openapi/metrics) and never
        # count rejected-auth probes — a bad-key 401 must not inflate the public
        # org's meter or mask credential-stuffing.
        route = request.url.path
        if response.status_code != 401 and not route.startswith(
            ("/docs", "/redoc", "/openapi", "/metrics", "/mcp")
        ):
            get_meter().record(org_id, route)
        log.info(
            "strata.request",
            request_id=request_id,
            method=request.method,
            path=route,
            status=response.status_code,
            org=org_id,
            ms=round(elapsed_ms, 1),
        )
        return response

    app.include_router(healthz.router)
    app.include_router(concepts.router)
    app.include_router(report.router)
    app.include_router(primitives.router)
    app.include_router(signals.router)
    app.include_router(frameworks.router)
    app.include_router(build.router)
    app.include_router(resolve.router)
    app.include_router(audit.router)
    app.include_router(usage.router)
    app.include_router(integrations.router)
    app.include_router(connectors.router)
    app.include_router(contribute.router)
    app.include_router(portfolio.router)
    app.include_router(me.router)
    app.include_router(lineage.router)

    # Mount the read-only Strata MCP server at /mcp (Wave 5A). Best-effort: a
    # failure to build it must not take down the REST API.
    try:
        from strata.mcp.server import build_streamable_http_app, load_registry

        # Resolved per request: in prod the lifespan sets app.state.registry to
        # the DB-loaded registry; fall back to on-disk YAML in dev. This keeps
        # the hosted MCP surface in sync with the REST API's data (review fix).
        def _mcp_registry() -> object:
            return getattr(app.state, "registry", None) or load_registry()

        mcp_app = build_streamable_http_app(get_registry=_mcp_registry)  # type: ignore[arg-type]
        # Lifespan still drives the RAW app's session-manager (via app.state.mcp_app);
        # the auth wrapper has no lifespan of its own — it only gates requests so the
        # hosted agent surface requires an API key (Phase 3 / Workstream A).
        from strata.api.mcp_auth import McpAuthMiddleware

        app.state.mcp_app = mcp_app
        app.mount("/mcp", McpAuthMiddleware(mcp_app))
    except Exception:  # MCP is additive; never block API boot on its failure
        log.warning("strata.mcp.mount_failed", exc_info=True)

    return app


app = create_app()
