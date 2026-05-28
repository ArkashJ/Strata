# Backend image. Build context is always the REPO ROOT.
#   docker compose up          (context: . in docker-compose.yml)
#   railway up                 (context: repo root by default)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ---- deps layer ----
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# ---- app layer ----
COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
RUN uv sync --frozen --no-dev

# ---- data layer (YAML seed files) ----
COPY data/ ./data/

# ---- start script ----
COPY backend/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=2).status==200 else 1)"

# entrypoint.sh runs migrations, optionally seeds, then execs uvicorn.
CMD ["./entrypoint.sh"]
