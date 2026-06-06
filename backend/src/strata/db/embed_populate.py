"""Populate the pgvector ``embedding`` columns from concept/primitive text.

PR5 (flow 39). Reads every concept + primitive from Postgres, computes the
deterministic feature-hashing embedding (``strata.resolver.embeddings``), and
writes it back. Idempotent: re-running recomputes the same vectors (the
embedding is a pure function of the text), so it's safe to run after any seed.

Run via ``strata embed`` (CLI). Requires migration 010 (pgvector + the
``embedding`` columns); if the extension/columns are missing it surfaces the DB
error rather than silently writing nothing.
"""

from __future__ import annotations

from sqlalchemy import select

from strata.db.embeddings import set_concept_embedding, set_primitive_embedding
from strata.db.engine import session_scope
from strata.db.models import ConceptRow, PrimitiveRow
from strata.resolver.embeddings import (
    concept_embed_text,
    embed_text,
    primitive_embed_text,
)


async def populate_embeddings() -> dict[str, int]:
    """Compute + persist embeddings for all concepts and primitives.

    Returns a per-table count of rows embedded.
    """
    counts = {"concepts": 0, "primitives": 0}
    async with session_scope() as session:
        for row in (await session.execute(select(ConceptRow))).scalars().all():
            vec = embed_text(concept_embed_text(row.name, row.definition))
            await set_concept_embedding(session, row.slug, vec)
            counts["concepts"] += 1

        for prow in (await session.execute(select(PrimitiveRow))).scalars().all():
            pvec = embed_text(primitive_embed_text(prow.name, prow.description))
            await set_primitive_embedding(session, prow.slug, pvec)
            counts["primitives"] += 1
    return counts
