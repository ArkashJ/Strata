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
    portfolio,
    primitives,
    resolve,
    signals,
    usage,
)
from strata.config import settings
from strata.logging import configure_logging, get_logger

load_dotenv()

log = get_logger(__name__)


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
    )

    # AC3.4: CORS must not be wildcard in prod. A "*" origin list in prod is a
    # misconfiguration — narrow to the explicit regex (Vercel previews) only, so
    # an unconfigured prod deploy fails closed rather than open.
    cors_origins = settings.cors_origins
    cors_origin_regex = settings.cors_origin_regex
    if settings.env == "prod" and cors_origins == ["*"]:
        log.warning("strata.cors.wildcard_blocked_in_prod")
        cors_origins = []
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
        app.state.mcp_app = mcp_app
        app.mount("/mcp", mcp_app)
    except Exception:  # MCP is additive; never block API boot on its failure
        log.warning("strata.mcp.mount_failed", exc_info=True)

    return app


app = create_app()
