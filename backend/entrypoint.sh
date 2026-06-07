#!/usr/bin/env bash
# Container start sequence for the Strata API.
#
# Boot flow:
#
#   alembic upgrade head        (bring the schema up to date)
#         │
#         ▼
#   strata db seed              (only if STRATA_SEED_ON_BOOT=1 — load YAML → Postgres)
#         │
#         ▼
#   exec uvicorn ...            (hand off PID 1 to the web server)
#
# Migrations always run: they are idempotent and cheap.
# Seeding is opt-in because Postgres is the production source of truth once
# loaded — you only want a re-seed on a fresh database or after adding data.
set -euo pipefail

# Where the baked-in YAML seed files live inside the image (see Dockerfile).
DATA_DIR="${STRATA_DATA_DIR:-/app/data}"

echo "[entrypoint] running migrations: alembic upgrade head"
alembic upgrade head

if [ "${STRATA_SEED_ON_BOOT:-0}" = "1" ]; then
  echo "[entrypoint] STRATA_SEED_ON_BOOT=1 → seeding YAML from ${DATA_DIR}"
  strata db seed -d "${DATA_DIR}"
else
  echo "[entrypoint] STRATA_SEED_ON_BOOT not set → skipping seed"
fi

# Railway and most PaaS inject a PORT; default to 8000 for local compose.
PORT="${PORT:-8000}"

echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT}"
# --proxy-headers + --forwarded-allow-ips='*': behind Railway's TLS-terminating
# edge the container speaks plain http, so without trusting X-Forwarded-Proto a
# trailing-slash redirect (e.g. POST /mcp -> /mcp/) is emitted with an http://
# Location. That scheme downgrade makes HTTP clients (httpx, the MCP transport)
# DROP the Authorization header across the redirect -> the hosted /mcp connector
# 401s a valid key. Trusting the proxy headers keeps the redirect on https.
exec uvicorn strata.api.app:app --host 0.0.0.0 --port "${PORT}" \
  --proxy-headers --forwarded-allow-ips='*'
