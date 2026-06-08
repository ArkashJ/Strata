"""One modeled/quarantine + tier fence, for every primitive-write door (#102).

A private-bank primitive can be written through two doors today: the REST route
``POST /me/primitives`` (a signed-in user) and the MCP tool ``save_primitive``
(an authenticated agent). Both must apply the *same* server-authoritative fence,
or a number the web app rejects could slip in through the agent (or vice-versa).

This module is the single chokepoint:

1. force ``visibility=private`` + the caller's ``org_id`` (never trust the body);
2. validate the :class:`AtomicPrimitive` schema;
3. enforce the **MODELED fence** — a community-modeled / analyst / paraphrase
   tier derives ``provenance_class=modeled`` and is refused, so a soft-data
   estimate can never be stored as a sourced number (Q20, KTD-5).

Returns the normalized payload to persist. Both ``db/user_primitives`` and the
MCP write tool call this, so the parity is enforced, not promised.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from ..models import AtomicPrimitive, ProvenanceClass


class ModeledFenceError(ValueError):
    """A primitive claims a sourced number that is actually modeled (soft data)."""


def validate_and_fence_primitive(payload: dict[str, Any], *, org_id: str) -> dict[str, Any]:
    """Force private+org, validate the shape, enforce the MODELED fence.

    Raises :class:`pydantic.ValidationError` / ``ValueError`` on a schema
    violation and :class:`ModeledFenceError` on a soft-data claim. Returns the
    re-serialized payload (coerced enums, forced visibility/org_id) so what is
    stored matches what loads."""
    normalized = dict(payload)
    normalized["visibility"] = "private"
    normalized["org_id"] = org_id
    normalized.setdefault("kind", "atomic_primitive")

    prim = TypeAdapter(AtomicPrimitive).validate_python(normalized)

    # provenance_class is DERIVED from the source tier, so a modeled estimate
    # cannot be relabelled as sourced by the caller.
    if prim.provenance_class is ProvenanceClass.MODELED:
        raise ModeledFenceError(
            f"primitive {prim.slug!r} (tier={prim.source.tier.value}) is modeled, not "
            f"sourced; the private bank stores sourced output only (Q20)"
        )

    return prim.model_dump(mode="json")


def validate_and_fence_shared_primitive(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate + fence a primitive being PROMOTED into the shared bank.

    The shared-bank twin of :func:`validate_and_fence_primitive`: instead of
    forcing private+org, it forces ``visibility=public`` and strips ``org_id``
    (a shared number belongs to no tenant), then runs the SAME schema validation
    and MODELED fence. So an admin promoting an org-private correction can never
    push a soft-data estimate into the bank everyone reads (Q20 holds at the
    shared door exactly as it does at the private one). Returns the normalized
    public payload ready to serialize to ``data/primitives/<slug>.yaml`` or seed
    into the shared registry."""
    normalized = dict(payload)
    normalized["visibility"] = "public"
    normalized.pop("org_id", None)
    normalized.setdefault("kind", "atomic_primitive")

    prim = TypeAdapter(AtomicPrimitive).validate_python(normalized)

    if prim.provenance_class is ProvenanceClass.MODELED:
        raise ModeledFenceError(
            f"primitive {prim.slug!r} (tier={prim.source.tier.value}) is modeled, not "
            f"sourced; the shared bank promotes sourced output only (Q20)"
        )

    return prim.model_dump(mode="json")


__all__ = [
    "ModeledFenceError",
    "validate_and_fence_primitive",
    "validate_and_fence_shared_primitive",
]
