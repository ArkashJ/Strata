"""FastAPI application factory. Exposes `create_app()` and a module-level `app`."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from strata import __version__
from strata.api.routes import build, concepts, frameworks, healthz, primitives, resolve
from strata.config import settings
from strata.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    log.info("strata.startup", env=settings.env, version=__version__)
    yield
    log.info("strata.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Strata API",
        version=__version__,
        description="Open-source community-curated market-sizing engine.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(healthz.router)
    app.include_router(concepts.router)
    app.include_router(primitives.router)
    app.include_router(frameworks.router)
    app.include_router(build.router)
    app.include_router(resolve.router)
    return app


app = create_app()
