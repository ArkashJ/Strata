"""Sync YAML data bank → Postgres.

Upserts all primitives, sources, concepts, and frameworks from the YAML
data directory into the database. Idempotent — safe to run repeatedly.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.engine import session_scope
from strata.db.models import ConceptRow, FrameworkRow, PrimitiveRow, SourceRow
from strata.loader import load_data_dir


def _primitive_to_row(raw: dict[str, Any]) -> dict[str, Any]:
    as_of = raw.get("as_of", "")
    if isinstance(as_of, str):
        parts = as_of.split("-")
        if len(parts) == 3:
            as_of = date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            as_of = date.today()
    return {
        "slug": raw["slug"],
        "kind": raw.get("kind", "atomic_primitive"),
        "schema_version": raw.get("schema_version", 1),
        "concept_slug": raw.get("concept_slug", ""),
        "name": raw.get("name", ""),
        "description": raw.get("description", ""),
        "value": float(raw.get("value", 0)),
        "unit": raw.get("unit", {}),
        "as_of": as_of,
        "geo": raw.get("geo", {}),
        "geo_perspective": raw.get("geo_perspective", "supply"),
        "distribution_shape": raw.get("distribution_shape", "normal"),
        "delivery_mode": raw.get("delivery_mode", "n/a"),
        "source": raw.get("source", {}),
        "scope": raw.get("scope"),
    }


def _composite_to_rows(loaded: Any) -> list[dict[str, Any]]:
    """Seed composite primitives as *resolved* primitive rows.

    The Postgres registry (``Registry.from_db``) reconstructs every primitive row
    as an ``AtomicPrimitive`` and has no composite path, so a composite that only
    lives in YAML is absent in prod — and any concept that consumes it 422s
    ("neither a known atomic nor composite primitive"). A same-unit ``union``
    composite is exactly the sum of its members (Q3), so we precompute that real
    value from the already-loaded member atomics and store it as a resolvable
    row. No figure is invented — the value is the arithmetic union of sourced
    member primitives, and provenance is carried forward from the members.
    """
    atomics = {p.slug: p for p in loaded.atomic_primitives}
    rows: list[dict[str, Any]] = []
    for comp in loaded.composite_primitives:
        members = [atomics[s] for s in comp.inputs if s in atomics]
        if len(members) != len(comp.inputs):
            continue  # missing members — leave unseeded so the gap stays visible
        if comp.set_operation.value != "union":
            continue  # evaluator only resolves union today; don't fake the rest
        # math.fsum (not sum) to bit-match the evaluator's union path
        # (evaluator/engine.py) — a plain sum would drift and trip the integrity
        # verifier comparing seeded vs freshly-derived values.
        value = math.fsum(m.value for m in members)
        snapshot = hashlib.sha256(
            "".join(sorted(m.source.snapshot_sha256 for m in members)).encode()
        ).hexdigest()
        src = members[0].source.model_dump(mode="json")
        src["snapshot_sha256"] = snapshot
        d = comp.model_dump(mode="json")
        rows.append(
            _primitive_to_row(
                {
                    "slug": d["slug"],
                    "kind": "atomic_primitive",
                    "schema_version": d.get("schema_version", 1),
                    "concept_slug": d.get("concept_slug", ""),
                    "name": d["name"],
                    "description": d["description"],
                    "value": float(value),
                    "unit": d["unit"],
                    "as_of": d.get("as_of", ""),
                    "geo": d.get("geo", {}),
                    "geo_perspective": d.get("geo_perspective", "supply"),
                    "source": src,
                }
            )
        )
    return rows


def _source_to_row(raw: dict[str, Any]) -> dict[str, Any]:
    accessed = raw.get("accessed", "")
    if isinstance(accessed, str):
        parts = accessed.split("-")
        if len(parts) == 3:
            accessed = date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            accessed = date.today()
    elif isinstance(accessed, date):
        pass
    else:
        accessed = date.today()
    return {
        "slug": raw["slug"],
        "tier": raw.get("tier", ""),
        "url": raw.get("url", ""),
        "accessed": accessed,
        "snapshot_sha256": raw.get("snapshot_sha256", ""),
        "description": raw.get("description", ""),
    }


async def _upsert_primitives(session: AsyncSession, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    stmt = pg_insert(PrimitiveRow).values(records)
    # Update EVERY non-key column on conflict. An incomplete set silently leaves
    # stale columns untouched on re-seed — the class of bug that stranded prod
    # framework `variants` at [] and broke every /build.
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={
            "kind": stmt.excluded.kind,
            "schema_version": stmt.excluded.schema_version,
            "concept_slug": stmt.excluded.concept_slug,
            "name": stmt.excluded.name,
            "description": stmt.excluded.description,
            "value": stmt.excluded.value,
            "unit": stmt.excluded.unit,
            "as_of": stmt.excluded.as_of,
            "geo": stmt.excluded.geo,
            "geo_perspective": stmt.excluded.geo_perspective,
            "distribution_shape": stmt.excluded.distribution_shape,
            "delivery_mode": stmt.excluded.delivery_mode,
            "source": stmt.excluded.source,
            "scope": stmt.excluded.scope,
        },
    )
    await session.execute(stmt)
    return len(records)


async def _upsert_sources(session: AsyncSession, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    stmt = pg_insert(SourceRow).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={
            "tier": stmt.excluded.tier,
            "url": stmt.excluded.url,
            "accessed": stmt.excluded.accessed,
            "snapshot_sha256": stmt.excluded.snapshot_sha256,
            "description": stmt.excluded.description,
        },
    )
    await session.execute(stmt)
    return len(records)


async def _upsert_concepts(session: AsyncSession, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    stmt = pg_insert(ConceptRow).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={
            "schema_version": stmt.excluded.schema_version,
            "name": stmt.excluded.name,
            "definition": stmt.excluded.definition,
            "analysis_lens": stmt.excluded.analysis_lens,
            "modifiers": stmt.excluded.modifiers,
            "measurements": stmt.excluded.measurements,
            "competing_concepts": stmt.excluded.competing_concepts,
            "scope": stmt.excluded.scope,
        },
    )
    await session.execute(stmt)
    return len(records)


async def _upsert_frameworks(session: AsyncSession, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    stmt = pg_insert(FrameworkRow).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={
            "schema_version": stmt.excluded.schema_version,
            "name": stmt.excluded.name,
            "method_family": stmt.excluded.method_family,
            "lens": stmt.excluded.lens,
            "inputs": stmt.excluded.inputs,
            "formula": stmt.excluded.formula,
            "output_unit": stmt.excluded.output_unit,
            "applicable_to": stmt.excluded.applicable_to,
            "variants": stmt.excluded.variants,
        },
    )
    await session.execute(stmt)
    return len(records)


async def sync_yaml_to_db(data_dir: Path) -> dict[str, int]:
    """Load all YAML from data_dir and upsert into Postgres. Returns counts."""
    loaded = load_data_dir(data_dir)

    prim_rows = [_primitive_to_row(p.model_dump(mode="json")) for p in loaded.atomic_primitives]
    prim_rows.extend(_composite_to_rows(loaded))
    src_rows = [_source_to_row(raw) for _, raw in loaded.source_registries]

    concept_rows = []
    for c in loaded.concepts:
        d = c.model_dump(mode="json")
        concept_rows.append(
            {
                "slug": d["slug"],
                "schema_version": d.get("schema_version", 1),
                "name": d["name"],
                "definition": d["definition"],
                "analysis_lens": d.get("analysis_lens", {}),
                "modifiers": d.get("modifiers", {}),
                "measurements": list(d.get("measurements", [])),
                "competing_concepts": list(d.get("competing_concepts", [])),
                "scope": d.get("scope"),
            }
        )

    fw_rows = []
    for f in loaded.frameworks:
        d = f.model_dump(mode="json")
        fw_rows.append(
            {
                "slug": d["slug"],
                "schema_version": d.get("schema_version", 1),
                "name": d["name"],
                "method_family": str(d.get("method_family", "")),
                "lens": str(d.get("lens", "")),
                "inputs": d.get("inputs", []),
                "formula": d.get("formula", ""),
                "output_unit": d.get("output_unit", {}),
                "applicable_to": list(d.get("applicable_to", [])),
                "variants": d.get("variants", []),
            }
        )

    async with session_scope() as session:
        p_count = await _upsert_primitives(session, prim_rows)
        s_count = await _upsert_sources(session, src_rows)
        c_count = await _upsert_concepts(session, concept_rows)
        f_count = await _upsert_frameworks(session, fw_rows)

    return {
        "primitives": p_count,
        "sources": s_count,
        "concepts": c_count,
        "frameworks": f_count,
    }


async def get_db_stats() -> dict[str, int]:
    """Return row counts for all data bank tables."""
    async with session_scope() as session:
        counts = {}
        for table, model in [
            ("primitives", PrimitiveRow),
            ("sources", SourceRow),
            ("concepts", ConceptRow),
            ("frameworks", FrameworkRow),
        ]:
            result = await session.execute(select(func.count()).select_from(model.__table__))
            counts[table] = result.scalar() or 0
    return counts
