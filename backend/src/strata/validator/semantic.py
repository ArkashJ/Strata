"""Semantic validator.

Checks that aren't covered by Pydantic but are local to a single record:
- snapshot-hash format
- ``as_of`` not in the future
- sig-fig sanity (reject suspicious zero-padded magnitudes)
- analyst-paraphrase paraphrase ≤ 280 chars + reviewer present
- framework inputs declare a primitive-slug binding (never a scalar default)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..loader import LoadedRecords
from ..models import (
    PARAPHRASE_MAX_CHARS,
    SHA256_PATTERN,
    AtomicPrimitive,
    SourceTier,
)

_HASH_RE = re.compile(SHA256_PATTERN)


@dataclass(frozen=True, slots=True)
class SemanticError:
    code: str
    slug: str
    message: str


def semantic_check(records: LoadedRecords, *, today: date | None = None) -> list[SemanticError]:
    today = today or date.today()
    errors: list[SemanticError] = []
    errors.extend(_atomic_primitive_checks(records.atomic_primitives, today))
    errors.extend(_framework_no_scalar_defaults(records))
    return errors


def _atomic_primitive_checks(primitives: list[AtomicPrimitive], today: date) -> list[SemanticError]:
    errors: list[SemanticError] = []
    for p in primitives:
        if not _HASH_RE.fullmatch(p.source.snapshot_sha256):
            errors.append(
                SemanticError(
                    code="semantic.bad_snapshot_hash",
                    slug=p.slug,
                    message=f"source.snapshot_sha256 does not match {SHA256_PATTERN}",
                )
            )
        if p.as_of > today:
            errors.append(
                SemanticError(
                    code="semantic.as_of_in_future",
                    slug=p.slug,
                    message=f"as_of {p.as_of.isoformat()} is in the future (today={today.isoformat()})",
                )
            )
        if p.source.tier == SourceTier.ANALYST_PARAPHRASE:
            errors.extend(_paraphrase_checks(p))
        errors.extend(_sig_fig_check(p))
    return errors


def _paraphrase_checks(p: AtomicPrimitive) -> list[SemanticError]:
    errors: list[SemanticError] = []
    src = p.source
    if src.paraphrase_text is None or not src.paraphrase_text.strip():
        errors.append(
            SemanticError(
                code="semantic.paraphrase_missing_text",
                slug=p.slug,
                message="analyst-paraphrase source requires paraphrase_text",
            )
        )
    elif len(src.paraphrase_text) > PARAPHRASE_MAX_CHARS:
        errors.append(
            SemanticError(
                code="semantic.paraphrase_too_long",
                slug=p.slug,
                message=(
                    f"paraphrase_text {len(src.paraphrase_text)} chars exceeds "
                    f"{PARAPHRASE_MAX_CHARS}"
                ),
            )
        )
    if not src.paraphrase_reviewer:
        errors.append(
            SemanticError(
                code="semantic.paraphrase_missing_reviewer",
                slug=p.slug,
                message="analyst-paraphrase source requires paraphrase_reviewer",
            )
        )
    if not src.original_publisher:
        errors.append(
            SemanticError(
                code="semantic.paraphrase_missing_publisher",
                slug=p.slug,
                message="analyst-paraphrase source requires original_publisher",
            )
        )
    return errors


def _sig_fig_check(p: AtomicPrimitive) -> list[SemanticError]:
    # Sanity envelope. Reject obvious placeholder values (0 or NaN-ish).
    if p.value <= 0 and p.unit.dimension.value != "percent":
        return [
            SemanticError(
                code="semantic.nonpositive_value",
                slug=p.slug,
                message=f"value {p.value} not strictly positive for non-percent primitive",
            )
        ]
    return []


def _framework_no_scalar_defaults(records: LoadedRecords) -> list[SemanticError]:
    """Q15: every variant input must point at a primitive slug, never a scalar.

    Inspect the *raw* YAML payload so we catch numeric defaults *before*
    Pydantic coerces them to strings (Pydantic v2 strict will reject anyway,
    but the error message is generic — this gives a precise message).
    """
    errors: list[SemanticError] = []
    for path, raw in records.raw_by_path.items():
        if raw.get("kind") != "framework":
            continue
        slug = str(raw.get("slug") or path.stem)
        variants_raw = raw.get("variants") or []
        if not isinstance(variants_raw, list):
            continue
        variants_list: list[Any] = variants_raw
        for variant_item in variants_list:
            if not isinstance(variant_item, dict):
                continue
            variant: dict[str, Any] = {str(k): v for k, v in variant_item.items()}
            defaults_raw = variant.get("default_inputs") or {}
            if not isinstance(defaults_raw, dict):
                continue
            defaults: dict[str, Any] = {str(k): v for k, v in defaults_raw.items()}
            for input_name, value in defaults.items():
                if not isinstance(value, str):
                    errors.append(
                        SemanticError(
                            code="semantic.framework_scalar_default",
                            slug=slug,
                            message=(
                                f"variant scope={variant.get('scope')!r} input {input_name!r} "
                                f"has scalar default {value!r}; every input must point at a "
                                f"primitive slug (Q15)"
                            ),
                        )
                    )
    return errors
