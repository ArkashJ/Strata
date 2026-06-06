"""Persist + query concept/primitive embeddings in the pgvector column.

PR5 (flow 39). Kept separate from ``db/queries.py`` because the ``embedding``
column is a pgvector type the ORM models don't declare (to avoid a hard
``pgvector`` dependency just for one column). We read/write it via parameterized
raw SQL, encoding the vector as the pgvector text literal ``[v0,v1,...]``.

``match_concept_semantic`` runs a cosine-distance (``<=>``) nearest-neighbour
scan and returns the best concept slug above a similarity floor — the resolver's
FALLBACK after registry-first exact/fuzzy matching misses.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from strata.resolver.embeddings import EMBED_DIM


def _to_pgvector(vec: list[float]) -> str:
    """Encode a Python float list as a pgvector text literal: ``[1,2,3]``."""
    if len(vec) != EMBED_DIM:
        raise ValueError(f"expected {EMBED_DIM}-dim vector, got {len(vec)}")
    return "[" + ",".join(repr(float(v)) for v in vec) + "]"


async def set_concept_embedding(session: AsyncSession, slug: str, vec: list[float]) -> None:
    await session.execute(
        text("UPDATE concepts SET embedding = CAST(:v AS vector) WHERE slug = :slug"),
        {"v": _to_pgvector(vec), "slug": slug},
    )


async def set_primitive_embedding(session: AsyncSession, slug: str, vec: list[float]) -> None:
    await session.execute(
        text("UPDATE primitives SET embedding = CAST(:v AS vector) WHERE slug = :slug"),
        {"v": _to_pgvector(vec), "slug": slug},
    )


async def match_concept_semantic(
    session: AsyncSession, query_vec: list[float], *, min_similarity: float = 0.5
) -> str | None:
    """Return the nearest concept slug by cosine similarity, or ``None``.

    Uses pgvector's ``<=>`` cosine-distance operator (``similarity = 1 -
    distance``). Only concepts with a populated embedding are considered. Returns
    ``None`` when the best match falls below ``min_similarity`` so a weak lexical
    overlap never produces a false concept hit (the caller then falls through to
    the novel-synthesis path).

    The floor (0.5) is deliberately strict for the feature-hashing embedding: a
    genuine multi-term overlap ("AI legal research lawyers" → the legal-research
    concept) scores ~0.6+, while a single ambiguous token or unrelated text
    scores well below. This is the FALLBACK after literal exact/fuzzy matching —
    it only needs to recover strong term-overlap queries the fuzzy ratio misses,
    not to be a precise semantic engine. Downstream the resolver still validates
    the concept yields real sourced primitives, so a marginal hit can't fabricate
    a TAM. The caller additionally gates on a minimum query token count (a
    one-word query is too collision-prone to match on).
    """
    row = (
        await session.execute(
            text(
                """
                SELECT slug, 1 - (embedding <=> CAST(:v AS vector)) AS similarity
                FROM concepts
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:v AS vector)
                LIMIT 1
                """
            ),
            {"v": _to_pgvector(query_vec)},
        )
    ).first()
    if row is None:
        return None
    slug, similarity = row[0], float(row[1])
    return slug if similarity >= min_similarity else None
