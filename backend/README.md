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

## MCP server (Strata in Claude)

Strata exposes its curated data bank + evaluator as a **read-only** MCP server,
so any MCP client (Claude Desktop, IDE agents) gets **sourced, hash-pinned**
market numbers. Five tools: `search_concepts`, `get_primitive`,
`list_frameworks`, `size_tam`, `resolve_market`. Every numeric payload carries
its `source_url`, `source_tier`, and `snapshot_sha256`; nothing mutates the
registry.

Local (stdio) — add to Claude:

```sh
claude mcp add strata -- uv run --directory /ABSOLUTE/PATH/to/backend strata-mcp --stdio
```

Hosted (streamable HTTP) is mounted on the API at `/mcp` (local-trust today;
gated by the Wave-3 API key in prod):

```sh
claude mcp add --transport http strata https://<your-strata-host>/mcp
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
