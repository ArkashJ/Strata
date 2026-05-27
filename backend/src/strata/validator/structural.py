"""Structural validator: YAML parse + slug uniqueness + required `kind`.

Most of the structural work is done by the loader + Pydantic; this module
exists so the three-layer pipeline has a callable stage and so we can emit
slug-uniqueness errors that span the whole dataset.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ..loader import LoadedRecords


@dataclass(frozen=True, slots=True)
class StructuralError:
    code: str
    message: str


def structural_check(records: LoadedRecords) -> list[StructuralError]:
    errors: list[StructuralError] = []
    errors.extend(_uniqueness(records.atomic_primitives, "atomic_primitive"))
    errors.extend(_uniqueness(records.composite_primitives, "composite_primitive"))
    errors.extend(_uniqueness(records.concepts, "concept"))
    errors.extend(_uniqueness(records.frameworks, "framework"))
    errors.extend(_uniqueness(records.annotations, "annotation"))
    errors.extend(_uniqueness(records.tam_outputs, "tam_output"))
    # Atomic and composite primitives share a slug namespace.
    atomic_slugs = {r.slug for r in records.atomic_primitives}
    composite_slugs = {r.slug for r in records.composite_primitives}
    cross_dups = atomic_slugs & composite_slugs
    for slug in sorted(cross_dups):
        errors.append(
            StructuralError(
                code="structural.duplicate_primitive_slug",
                message=f"slug {slug!r} used by both atomic and composite primitives",
            )
        )
    return errors


def _uniqueness(records: Iterable[object], kind: str) -> list[StructuralError]:
    buckets: dict[str, int] = defaultdict(int)
    for r in records:
        slug = getattr(r, "slug", None)
        if isinstance(slug, str):
            buckets[slug] += 1
    return [
        StructuralError(
            code="structural.duplicate_slug",
            message=f"{kind} slug {slug!r} appears {count} times",
        )
        for slug, count in sorted(buckets.items())
        if count > 1
    ]
