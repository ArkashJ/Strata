"""Org-scoped private-primitive store + evaluator overlay (Wave 5B / AC5B.2-4).

Private primitives are keyed by ``org_id`` so one tenant can never read another's
(the in-process analogue of the Postgres RLS from Wave 3). ``org_scoped_registry``
overlays an org's private primitives onto the public registry so the *same*
evaluator sizes a TAM with them; disconnecting a provider purges (tombstones) its
private primitives.
"""

from __future__ import annotations

import dataclasses
from threading import Lock

from ...models import AtomicPrimitive
from ...registry import Registry


class PrivatePrimitiveStore:
    def __init__(self) -> None:
        # org_id -> provider -> {slug: primitive}
        self._by_org: dict[str, dict[str, dict[str, AtomicPrimitive]]] = {}
        self._lock = Lock()

    def add(self, org_id: str, provider: str, primitives: list[AtomicPrimitive]) -> None:
        with self._lock:
            bucket = self._by_org.setdefault(org_id, {}).setdefault(provider, {})
            for p in primitives:
                bucket[p.slug] = p

    def for_org(self, org_id: str) -> list[AtomicPrimitive]:
        """Every private primitive for one org — and NEVER any other org's."""
        with self._lock:
            providers = self._by_org.get(org_id, {})
            return [p for prov in providers.values() for p in prov.values()]

    def purge(self, org_id: str, provider: str) -> int:
        """Tombstone an org's primitives for a provider (disconnect). Returns the
        count removed."""
        with self._lock:
            removed = self._by_org.get(org_id, {}).pop(provider, {})
            return len(removed)

    def reset(self) -> None:
        with self._lock:
            self._by_org.clear()


_store = PrivatePrimitiveStore()


def get_store() -> PrivatePrimitiveStore:
    return _store


def org_scoped_registry(reg: Registry, org_id: str, store: PrivatePrimitiveStore) -> Registry:
    """A registry view = public atomic primitives overlaid with this org's
    private ones. Private slugs are org-namespaced so they can't shadow public
    slugs; the public ``reg`` is never mutated."""
    private = {p.slug: p for p in store.for_org(org_id)}
    if not private:
        return reg
    merged_atomic = {**reg.atomic, **private}
    return dataclasses.replace(reg, atomic=merged_atomic)
