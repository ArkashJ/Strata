"""Annotation record (E3).

Annotations are pure commentary — text-only, never auto-applied to math (E1).
Contributor tier is not stored on the annotation; it's resolved at display time.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import Slug


class AnnotationTargetType(StrEnum):
    CONCEPT = "concept"
    PRIMITIVE = "primitive"
    COMPOSITE_PRIMITIVE = "composite_primitive"
    FRAMEWORK = "framework"
    PYRAMID_NODE = "pyramid_node"
    SCENARIO = "scenario"
    TAM_OUTPUT = "tam_output"
    SOURCE = "source"


class AnnotationKindTag(StrEnum):
    CORRECTION = "correction"
    BLINDSPOT = "blindspot"
    METHODOLOGY_NOTE = "methodology_note"
    SCOPE_WARNING = "scope_warning"
    ALT_FRAMING = "alt_framing"
    OTHER = "other"


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["annotation"]
    slug: Slug
    schema_version: int = Field(ge=1)

    target_slug: Slug
    target_type: AnnotationTargetType
    author: Slug
    created_at: datetime
    body: str

    kind_tag: AnnotationKindTag
    coi_disclosure: str | None = None
