"""FastAPI application factory. Exposes `create_app()` and a module-level `app`."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from strata import __version__
from strata.api.routes import (
    audit,
    build,
    concepts,
    frameworks,
    healthz,
    primitives,
    resolve,
)
from strata.config import settings
from strata.logging import configure_logging, get_logger

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(healthz.router)
    app.include_router(concepts.router)
    app.include_router(primitives.router)
    app.include_router(frameworks.router)
    app.include_router(build.router)
    app.include_router(resolve.router)
    app.include_router(audit.router)
    return app


app = create_app()
