"""Feedback / assumption-flagging model (Phase F).

A ``FeedbackEvent`` is how the co-founder (and every user / agent) flags a bad
assumption, a failed query, a wrong primitive, or missing data — so dead-ends
become a triageable backlog instead of a black hole. It is **commentary on the
tool**, never an input to the math (mirrors the annotation rule, E1): a flag
records that a number looked wrong; it never silently changes one.

Stored org-scoped (RLS) in ``feedback_events`` (migration 014) and surfaced via
``GET /feedback`` + the ``/feedback`` web page + the ``list_feedback`` MCP tool.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class FeedbackKind(StrEnum):
    """Why the flag was raised."""

    BAD_ASSUMPTION = "bad_assumption"
    FAILED_QUERY = "failed_query"
    PRIMITIVE_CORRECTION = "primitive_correction"
    MISSING_DATA = "missing_data"
    GENERAL = "general"


class TargetType(StrEnum):
    """What the flag is about — the surface a triager drills into."""

    TAM = "tam"
    PRIMITIVE = "primitive"
    CONCEPT = "concept"
    FRAMEWORK = "framework"
    QUERY = "query"
    REPORT = "report"


class FeedbackStatus(StrEnum):
    """Triage lifecycle. New flags are ``open``; a maintainer moves them along."""

    OPEN = "open"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    WONTFIX = "wontfix"


class FeedbackEvent(BaseModel):
    """One persisted feedback row (read shape). ``suggested_value`` is free-form
    JSON (e.g. a corrected number + unit) the submitter proposes; it is advisory
    only and never auto-applied."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    user_id: str | None = None
    created_at: datetime
    kind: FeedbackKind
    target_type: TargetType
    target_id: str | None = None
    query_text: str | None = None
    severity: str | None = None
    body: str
    suggested_value: dict[str, Any] | None = None
    status: FeedbackStatus = FeedbackStatus.OPEN
    resolution: str | None = None
    # Set when an accepted correction was APPLIED: the id of the org-private
    # primitive the fix created (``user_primitives``). Closes the flag→fix loop.
    resolved_primitive_id: int | None = None
