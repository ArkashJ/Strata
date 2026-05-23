# Strata — backend

FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + Alembic, managed by uv.

Top-level README in the repo root has the full project context. This file
exists so `pyproject.toml`'s `readme = "README.md"` resolves locally and so
the Docker build context can be just `backend/`.

## Quick start

```sh
cd backend
uv sync --extra dev
uv run uvicorn strata.api.app:app --reload --port 8000
```

Migrations:

```sh
uv run alembic revision --autogenerate -m "msg"
uv run alembic upgrade head
```

Checks:

```sh
uv run pytest
uv run ruff check .
uv run pyright
```

Layout:

```
backend/
├── pyproject.toml     uv-managed, pyright strict, ruff
├── uv.lock
├── alembic.ini        migration config
├── alembic/           env + versions
├── src/strata/        package
│   ├── api/           FastAPI app + routes
│   ├── config.py      pydantic-settings (STRATA_* env)
│   ├── logging.py     structlog
│   ├── db/            SQLAlchemy 2.0 async engine + Base
│   └── cli.py         `strata` Typer CLI
└── Dockerfile         uv-based, layered, healthcheck'd
```
