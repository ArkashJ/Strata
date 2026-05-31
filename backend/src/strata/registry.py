"""In-memory registry keyed by ``(record_type, slug)``.

The registry is rebuilt every CLI invocation — YAML on disk is the source of
truth for dev/test; Postgres is the source of truth in prod.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from .loader import LoadedRecords
from .models import (
    Annotation,
    AtomicPrimitive,
    CompositePrimitive,
    Concept,
    Framework,
    SourceTier,
    TAMOutput,
)


class RegistryError(KeyError):
    pass


# FIFO bound on ephemeral build/recompute TAM outputs kept in-memory so their
# permalinks resolve within a session. Large enough for a demo, small enough to
# bound a long-lived process.
_TAM_CACHE_CAP = 512


@dataclass(slots=True)
class Registry:
    atomic: dict[str, AtomicPrimitive]
    composite: dict[str, CompositePrimitive]
    concepts: dict[str, Concept]
    frameworks: dict[str, Framework]
    annotations: dict[str, Annotation]
    tam_outputs: dict[str, TAMOutput]
    # Read-only prediction-market / non-sizing signals (Q20). Never consumed by
    # the evaluator or any framework — exposed for display only.
    signals: dict[str, AtomicPrimitive] = field(default_factory=dict[str, AtomicPrimitive])

    @classmethod
    async def from_db(cls) -> Registry:
        """Build the registry from Postgres. Used in prod."""
        from .db.engine import SessionLocal
        from .db.queries import (
            load_concepts_from_db,
            load_frameworks_from_db,
            load_primitives_from_db,
        )
        from .db.tams import load_promoted_tams_from_db

        async with SessionLocal() as session:
            primitives = await load_primitives_from_db(session)
            concepts = await load_concepts_from_db(session)
            frameworks = await load_frameworks_from_db(session)
            promoted_tams = await load_promoted_tams_from_db(session)

        # Mirror the YAML loader's signal quarantine on the prod path: a
        # prediction-market primitive seeded into the DB must NOT reach the
        # evaluator (Q20). Split by source tier before indexing.
        sizing = [p for p in primitives if p.source.tier is not SourceTier.PREDICTION_MARKET]
        signals = [p for p in primitives if p.source.tier is SourceTier.PREDICTION_MARKET]
        return cls(
            atomic=_index(sizing, lambda r: r.slug, "atomic_primitive"),
            composite={},
            concepts=_index(concepts, lambda r: r.slug, "concept"),
            frameworks=_index(frameworks, lambda r: r.slug, "framework"),
            annotations={},
            tam_outputs=_index(promoted_tams, lambda r: r.state_hash, "tam_output"),
            signals=_index(signals, lambda r: r.slug, "signal"),
        )

    @classmethod
    def from_loaded(cls, records: LoadedRecords) -> Registry:
        return cls(
            atomic=_index(records.atomic_primitives, lambda r: r.slug, "atomic_primitive"),
            composite=_index(records.composite_primitives, lambda r: r.slug, "composite_primitive"),
            concepts=_index(records.concepts, lambda r: r.slug, "concept"),
            frameworks=_index(records.frameworks, lambda r: r.slug, "framework"),
            annotations=_index(records.annotations, lambda r: r.slug, "annotation"),
            tam_outputs=_index(records.tam_outputs, lambda r: r.state_hash, "tam_output"),
            signals=_index(records.signals, lambda r: r.slug, "signal"),
        )

    def primitive(self, slug: str) -> AtomicPrimitive | CompositePrimitive:
        if slug in self.atomic:
            return self.atomic[slug]
        if slug in self.composite:
            return self.composite[slug]
        raise RegistryError(f"primitive {slug!r} not found")

    def get_atomic(self, slug: str) -> AtomicPrimitive:
        try:
            return self.atomic[slug]
        except KeyError as exc:
            raise RegistryError(f"atomic_primitive {slug!r} not found") from exc

    def get_concept(self, slug: str) -> Concept:
        try:
            return self.concepts[slug]
        except KeyError as exc:
            raise RegistryError(f"concept {slug!r} not found") from exc

    def get_framework(self, slug: str) -> Framework:
        try:
            return self.frameworks[slug]
        except KeyError as exc:
            raise RegistryError(f"framework {slug!r} not found") from exc

    def iter_frameworks(self) -> Iterator[Framework]:
        yield from self.frameworks.values()

    def remember_tam(self, tam: TAMOutput, *, cap: int = _TAM_CACHE_CAP) -> None:
        """Persist an evaluated TAM so ``GET /tam/<hash>`` resolves (AC0.1).

        Curated TAMs loaded from ``data/tams/`` and freshly-minted ones share
        the same dict; equivalent states collide on ``state_hash`` (Q38) so a
        re-build is idempotent. The cache is FIFO-capped to bound memory on a
        long-lived process — only ephemeral build/recompute outputs are evicted
        (curated YAML TAMs are re-seeded from disk on registry rebuild)."""
        # Overwrite in place: a re-build is idempotent on content, but a later
        # call may carry new flags (e.g. is_promoted) for the same state_hash —
        # updating an existing key preserves its FIFO position.
        self.tam_outputs[tam.state_hash] = tam
        # Evict the oldest NON-promoted output first; promoted TAMs are durable
        # public endpoints (/browse + sitemap) and must not be FIFO-evicted.
        while len(self.tam_outputs) > cap:
            oldest = next((k for k, v in self.tam_outputs.items() if not v.is_promoted), None)
            if oldest is None:
                break  # everything left is promoted — keep it
            del self.tam_outputs[oldest]


def _index[T](records: Iterable[T], slug_of: Callable[[T], str], kind: str) -> dict[str, T]:
    out: dict[str, T] = {}
    for record in records:
        slug = slug_of(record)
        if slug in out:
            raise RegistryError(f"duplicate {kind} slug: {slug!r}")
        out[slug] = record
    return out
