#!/usr/bin/env bash
# Container entrypoint: migrate → (optional) seed → serve.
#
#   1. alembic upgrade head        — bring Postgres schema to latest revision.
#   2. STRATA_SEED_ON_BOOT=1       — upsert baked-in YAML into Postgres
#                                    (idempotent; off by default so restarts
#                                    don't re-seed on every boot).
#   3. exec uvicorn                — replace shell with the server so signals
#                                    (SIGTERM from the platform) reach uvicorn.
set -euo pipefail

PORT="${PORT:-8000}"
DATA_DIR="${STRATA_DATA_DIR:-/app/data}"

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

if [ "${STRATA_SEED_ON_BOOT:-0}" = "1" ]; then
  echo "[entrypoint] STRATA_SEED_ON_BOOT=1 → strata db seed -d ${DATA_DIR}"
  strata db seed -d "${DATA_DIR}"
else
  echo "[entrypoint] STRATA_SEED_ON_BOOT unset → skipping seed"
fi

echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn strata.api.app:app --host 0.0.0.0 --port "${PORT}"
