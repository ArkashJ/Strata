"""Load Pydantic models from Postgres ORM rows.

Used by ``Registry.from_db()`` to populate the in-memory registry from
Postgres instead of YAML. Each function queries all rows from the relevant
table, converts the JSONB columns (already deserialized to dicts by asyncpg),
and returns fully-validated Pydantic models.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import ConceptRow, FrameworkRow, PrimitiveRow
from strata.models import AtomicPrimitive, Concept, Framework


async def load_primitives_from_db(session: AsyncSession) -> list[AtomicPrimitive]:
    """SELECT all primitives and reconstruct ``AtomicPrimitive`` Pydantic models."""
    result = await session.execute(select(PrimitiveRow))
    rows = result.scalars().all()
    primitives: list[AtomicPrimitive] = []
    for row in rows:
        raw: dict[str, Any] = {
            "kind": row.kind,
            "slug": row.slug,
            "schema_version": row.schema_version,
            "concept_slug": row.concept_slug,
            "name": row.name,
            "description": row.description,
            "value": row.value,
            "unit": row.unit,
            "as_of": row.as_of,
            "geo": row.geo,
            "geo_perspective": row.geo_perspective,
            "distribution_shape": row.distribution_shape,
            "delivery_mode": row.delivery_mode,
            "source": row.source,
        }
        primitives.append(AtomicPrimitive.model_validate(raw))
    return primitives


async def load_concepts_from_db(session: AsyncSession) -> list[Concept]:
    """SELECT all concepts and reconstruct ``Concept`` Pydantic models."""
    result = await session.execute(select(ConceptRow))
    rows = result.scalars().all()
    concepts: list[Concept] = []
    for row in rows:
        raw: dict[str, Any] = {
            "kind": "concept",
            "slug": row.slug,
            "schema_version": row.schema_version,
            "name": row.name,
            "definition": row.definition,
            "analysis_lens": row.analysis_lens,
            "modifiers": row.modifiers,
            "measurements": row.measurements,
            "competing_concepts": row.competing_concepts,
        }
        concepts.append(Concept.model_validate(raw))
    return concepts


async def load_frameworks_from_db(session: AsyncSession) -> list[Framework]:
    """SELECT all frameworks and reconstruct ``Framework`` Pydantic models."""
    result = await session.execute(select(FrameworkRow))
    rows = result.scalars().all()
    frameworks: list[Framework] = []
    for row in rows:
        raw: dict[str, Any] = {
            "kind": "framework",
            "slug": row.slug,
            "schema_version": row.schema_version,
            "name": row.name,
            "method_family": row.method_family,
            "lens": row.lens,
            "inputs": row.inputs,
            "formula": row.formula,
            "output_unit": row.output_unit,
            "applicable_to": row.applicable_to,
            "variants": row.variants,
        }
        frameworks.append(Framework.model_validate(raw))
    return frameworks
