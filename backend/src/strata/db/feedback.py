"""Feedback-event writer + reader (Phase F — the improvement flywheel).

A user / agent flags a bad assumption, a failed query, a wrong primitive, or
missing data; the team triages and resolves it. Mirrors ``db/audit.py``:
``record_feedback_safe`` is fire-and-forget (a failed flag-write never breaks the
request that triggered it), while the explicit ``record_feedback`` / ``list_*`` /
``update_*`` functions take an already-org-scoped session (the route owns the
``org_session_scope`` so the strict RLS policy on ``feedback_events`` isolates).

A flag is commentary on the TOOL, never an input to the math (E1): persisting a
``suggested_value`` records a proposal, it does not change any sourced number.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import FeedbackEventRow
from strata.db.user_primitives import UserPrimitive, create_user_primitive
from strata.guards.fence import validate_and_fence_shared_primitive
from strata.models.feedback import (
    FeedbackEvent,
    FeedbackKind,
    FeedbackStatus,
    TargetType,
)

_log = logging.getLogger(__name__)

# The flag kinds that propose a corrected/new number an accepted resolution can
# turn into an org-private primitive. A bad-assumption / general / failed-query
# flag is triage commentary only — it never produces a primitive (E1, Q20).
_APPLICABLE_KINDS: frozenset[FeedbackKind] = frozenset(
    {FeedbackKind.PRIMITIVE_CORRECTION, FeedbackKind.MISSING_DATA}
)


class FeedbackNotApplicableError(ValueError):
    """The flag cannot be turned into a primitive: it is already resolved, has no
    correction payload, or its kind is commentary-only (not a correction)."""


# The anonymous tenant sentinel (mirrors ``api.auth._ANONYMOUS_ORG`` and the
# audit writer). The closed RLS policy rejects a NULL/anon-org row by design, so
# an anonymous flag is attempted best-effort and silently dropped — never a 500.
_ANONYMOUS_ORG = "public"


async def record_feedback(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str | None,
    kind: FeedbackKind,
    target_type: TargetType,
    body: str,
    target_id: str | None = None,
    query_text: str | None = None,
    severity: str | None = None,
    suggested_value: dict[str, Any] | None = None,
    status: FeedbackStatus = FeedbackStatus.OPEN,
) -> FeedbackEvent:
    """Insert one feedback row inside an already-org-scoped session. The caller
    owns the scope (so ``app.org_id`` is set and the RLS ``WITH CHECK`` passes)."""
    row = FeedbackEventRow(
        org_id=org_id,
        user_id=user_id,
        kind=kind.value,
        target_type=target_type.value,
        target_id=target_id,
        query_text=query_text,
        severity=severity,
        body=body,
        suggested_value=suggested_value,
        status=status.value,
    )
    session.add(row)
    await session.flush()
    return FeedbackEvent.model_validate(row)


async def record_feedback_safe(
    *,
    org_id: str | None,
    user_id: str | None,
    kind: FeedbackKind,
    target_type: TargetType,
    body: str,
    target_id: str | None = None,
    query_text: str | None = None,
    severity: str | None = None,
    suggested_value: dict[str, Any] | None = None,
) -> int | None:
    """Fire-and-forget flag write on its own org-scoped session. Swallows (but
    logs) any failure so a flag can never break the request that triggered it
    (used by the failed-query auto-capture). Returns the new row id, or ``None``
    when the write was dropped (anonymous org has no tenant bucket under the
    closed RLS policy, exactly like the audit writer)."""
    if not org_id or org_id == _ANONYMOUS_ORG:
        return None
    try:
        from strata.db.engine import org_session_scope

        async with org_session_scope(org_id) as session:
            event = await record_feedback(
                session,
                org_id=org_id,
                user_id=user_id,
                kind=kind,
                target_type=target_type,
                body=body,
                target_id=target_id,
                query_text=query_text,
                severity=severity,
                suggested_value=suggested_value,
            )
            # org_session_scope commits on exit (session.begin()).
            return event.id
    except Exception:
        _log.warning("feedback.write_failed kind=%s target=%s", kind.value, target_type.value)
        return None


async def list_feedback(
    session: AsyncSession,
    *,
    status: FeedbackStatus | None = None,
    target_type: TargetType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedbackEvent]:
    """Return feedback rows newest-first, optionally filtered. RLS (the scoped
    session) restricts rows to ``app.org_id``."""
    stmt = select(FeedbackEventRow)
    if status is not None:
        stmt = stmt.where(FeedbackEventRow.status == status.value)
    if target_type is not None:
        stmt = stmt.where(FeedbackEventRow.target_type == target_type.value)
    stmt = (
        stmt.order_by(FeedbackEventRow.created_at.desc(), FeedbackEventRow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [FeedbackEvent.model_validate(r) for r in rows]


async def update_feedback(
    session: AsyncSession,
    feedback_id: int,
    *,
    status: FeedbackStatus | None = None,
    resolution: str | None = None,
) -> FeedbackEvent | None:
    """Triage / resolve one row (RLS-scoped to the caller's org). Returns ``None``
    when no such row is visible to this tenant."""
    row = (
        await session.execute(select(FeedbackEventRow).where(FeedbackEventRow.id == feedback_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    if status is not None:
        row.status = status.value
    if resolution is not None:
        row.resolution = resolution
    await session.flush()
    return FeedbackEvent.model_validate(row)


async def admin_list_feedback(
    session: AsyncSession,
    *,
    status: FeedbackStatus | None = None,
    kind: FeedbackKind | None = None,
    org_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FeedbackEvent]:
    """Cross-org feedback list for an admin session (``admin_session_scope`` set
    the ``app.is_admin`` GUC, so the additive admin SELECT policy returns every
    org's rows). Optional ``org_id`` filter narrows to one tenant. Newest-first.

    This is the only reader that crosses the tenant boundary — every other reader
    is RLS-isolated to ``app.org_id``."""
    stmt = select(FeedbackEventRow)
    if status is not None:
        stmt = stmt.where(FeedbackEventRow.status == status.value)
    if kind is not None:
        stmt = stmt.where(FeedbackEventRow.kind == kind.value)
    if org_id is not None:
        stmt = stmt.where(FeedbackEventRow.org_id == org_id)
    stmt = (
        stmt.order_by(FeedbackEventRow.created_at.desc(), FeedbackEventRow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [FeedbackEvent.model_validate(r) for r in rows]


async def admin_get_feedback_row(
    session: AsyncSession, feedback_id: int
) -> FeedbackEventRow | None:
    """Read one feedback row cross-org (admin session). Returns the ORM row (not
    the read model) so the promote path can mark it resolved in the same txn."""
    return (
        await session.execute(select(FeedbackEventRow).where(FeedbackEventRow.id == feedback_id))
    ).scalar_one_or_none()


async def admin_correction_payload(
    session: AsyncSession, row: FeedbackEventRow
) -> dict[str, Any] | None:
    """The primitive payload a correction would promote: the org-private primitive
    it already created (``resolved_primitive_id``, read cross-org via the admin
    SELECT policy on ``user_primitives``) or, failing that, the flag's own
    ``suggested_value``. ``None`` when neither is present."""
    if row.resolved_primitive_id is not None:
        from strata.db.models import UserPrimitiveRow

        prim = (
            await session.execute(
                select(UserPrimitiveRow).where(UserPrimitiveRow.id == row.resolved_primitive_id)
            )
        ).scalar_one_or_none()
        if prim is not None:
            return dict(prim.payload)
    if row.suggested_value is not None:
        return dict(row.suggested_value)
    return None


async def admin_promote_payload(
    session: AsyncSession, feedback_id: int, *, resolve: bool = True
) -> tuple[dict[str, Any], str]:
    """Read a correction cross-org, fence it for the shared bank, and (when
    ``resolve``) mark the flag resolved with the promotion note. Returns the
    normalized PUBLIC payload + the originating ``org_id``.

    The single owner of the promote sequence (read → fence → resolve → note) so
    the MCP tool and the CLI can never drift on the Q20 fence or the resolution
    string — each caller keeps only its own transport concern (envelope vs
    typer.Exit; the CLI's ``validate_only`` maps to ``resolve=False``). Raises
    :class:`FeedbackNotApplicableError` (unknown row / no correction payload) and
    the fence's :class:`ModeledFenceError` / ``ValidationError`` (the callers map
    those to their surface). Runs inside the caller's ``admin_session_scope``."""
    row = await admin_get_feedback_row(session, feedback_id)
    if row is None:
        raise FeedbackNotApplicableError(f"no feedback {feedback_id}")
    payload = await admin_correction_payload(session, row)
    if payload is None:
        raise FeedbackNotApplicableError(
            f"feedback {feedback_id} has no correction to promote "
            "(no applied primitive and no suggested_value)"
        )
    shared = validate_and_fence_shared_primitive(payload)
    from_org = row.org_id
    if resolve:
        note = f"promoted to shared bank → data/primitives/{shared['slug']}.yaml"
        row.resolution = f"{row.resolution} · {note}" if row.resolution else note
        row.status = FeedbackStatus.RESOLVED.value
        await session.flush()
    return shared, from_org


async def apply_feedback_correction(
    session: AsyncSession,
    feedback_id: int,
    *,
    org_id: str,
    created_by: str | None = None,
    primitive_payload: dict[str, Any] | None = None,
) -> tuple[FeedbackEvent, UserPrimitive]:
    """Close the loop: turn an accepted ``primitive_correction`` / ``missing_data``
    flag into an org-private primitive, then mark the flag resolved and link the
    new row's id.

    The correction is taken from ``primitive_payload`` (an explicit override) or,
    failing that, the row's own ``suggested_value`` — whichever is present is run
    through the SAME validator + MODELED fence that backs ``POST /me/primitives``
    (``create_user_primitive`` → ``_validate_and_fence``): visibility/org_id are
    forced, and a modeled / analyst-tier number is refused (``ModeledFenceError``)
    so a soft-data estimate can never enter the bank as sourced (Q20). The flag is
    still commentary (E1) — applying it does not mutate any existing sourced
    number; it CREATES a new org-private one the team chose to accept.

    Both writes share one already-org-scoped session so the RLS policies on
    ``feedback_events`` and ``user_primitives`` isolate the tenant, and the commit
    is atomic (the caller owns ``org_session_scope``). Raises
    ``FeedbackNotApplicableError`` when the flag can't be applied (unknown/invisible
    row, already-resolved, wrong kind, or no correction payload); the primitive
    fences raise their own ``ValueError`` subclasses, which the caller maps to 422.
    """
    row = (
        await session.execute(select(FeedbackEventRow).where(FeedbackEventRow.id == feedback_id))
    ).scalar_one_or_none()
    if row is None:
        raise FeedbackNotApplicableError(f"no feedback {feedback_id} visible to this org")
    if row.status == FeedbackStatus.RESOLVED.value:
        raise FeedbackNotApplicableError(f"feedback {feedback_id} is already resolved")
    if FeedbackKind(row.kind) not in _APPLICABLE_KINDS:
        raise FeedbackNotApplicableError(
            f"feedback kind {row.kind!r} is commentary only; only "
            f"primitive_correction / missing_data can apply a correction"
        )

    payload = primitive_payload if primitive_payload else row.suggested_value
    if not payload:
        raise FeedbackNotApplicableError(
            f"feedback {feedback_id} has no correction payload to apply "
            "(pass primitive_payload or set suggested_value)"
        )

    # The fence lives here — a modeled-tier correction raises ModeledFenceError and
    # the whole apply rolls back (no primitive, flag stays open). A correction whose
    # slug already exists in the org bank trips the (org_id, slug) unique constraint
    # at flush; translate that to an applicable-error (422) instead of a raw 500.
    # ``payload`` is a non-empty dict here (the ``if not payload`` guard above
    # rejected None / empty), so the slug lookup is safe without an isinstance.
    slug = str(payload.get("slug", ""))
    try:
        prim = await create_user_primitive(
            session, org_id=org_id, created_by=created_by, payload=payload
        )
    except IntegrityError as exc:
        raise FeedbackNotApplicableError(
            f"a primitive with slug {slug!r} already exists in this org's bank; "
            "edit that primitive or use a distinct slug for the correction"
        ) from exc

    row.status = FeedbackStatus.RESOLVED.value
    row.resolved_primitive_id = prim.id
    if not row.resolution:
        row.resolution = f"applied correction → org-private primitive {prim.slug!r} (id={prim.id})"
    await session.flush()
    return FeedbackEvent.model_validate(row), prim
