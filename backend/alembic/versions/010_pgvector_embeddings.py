"""pgvector extension + embedding columns on concepts/primitives

Revision ID: 010
Revises: 009
Create Date: 2026-06-06

PR 5 (flow 39) — semantic-search FALLBACK for the resolver.

Adds:
- the ``vector`` extension (pgvector). ``CREATE EXTENSION IF NOT EXISTS`` is a
  no-op when a superuser already installed it, so a non-superuser app role can
  run this migration in that case. If the extension is *absent* and the role
  lacks permission to create it, this raises — that is the BLOCKED condition the
  operator must resolve out-of-band (a superuser runs ``CREATE EXTENSION
  vector;`` once). We deliberately do NOT swallow the error: a silent skip would
  leave the embedding columns un-typed and ``strata embed`` would fail opaquely.
- a nullable ``embedding vector(256)`` column on ``concepts`` and ``primitives``.
  Nullable so existing rows load unchanged and embeddings are populated
  out-of-band by ``strata embed`` (never fabricated at migration time).

The dimension (256) MUST equal ``strata.resolver.embeddings.EMBED_DIM``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in lock-step with strata.resolver.embeddings.EMBED_DIM.
_EMBED_DIM = 256


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # pgvector exposes a custom type, so we add the column via raw SQL rather
    # than a SQLAlchemy type (avoids a hard import of the pgvector dialect just
    # for DDL). ``IF NOT EXISTS`` keeps the migration idempotent on re-run.
    op.execute(f"ALTER TABLE concepts ADD COLUMN IF NOT EXISTS embedding vector({_EMBED_DIM})")
    op.execute(f"ALTER TABLE primitives ADD COLUMN IF NOT EXISTS embedding vector({_EMBED_DIM})")
    # IVFFlat/HNSW indexes need populated data + tuning; for the current bank
    # size (<1k concepts) a sequential cosine scan in ``match_concept`` is fast
    # and exact, so no ANN index yet. (Add an HNSW index here when the bank
    # grows past a few thousand concepts.)


def downgrade() -> None:
    op.execute("ALTER TABLE primitives DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE concepts DROP COLUMN IF EXISTS embedding")
    # Leave the extension installed — other objects may depend on it and a
    # superuser created it; dropping it here would overreach.
