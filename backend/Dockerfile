# Backend image. Uses the official uv distroless-ish base.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ---- deps layer ----
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ---- app layer ----
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
# Data dir is COPY'd when building from repo root context (docker build -f backend/Dockerfile .)
# For local dev, mount -v ./data:/app/data instead.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=2).status==200 else 1)"

CMD ["uvicorn", "strata.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
