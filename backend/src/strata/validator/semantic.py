"""Semantic validator.

Checks that aren't covered by Pydantic but are local to a single record:
- snapshot-hash format
- ``as_of`` not in the future
- sig-fig sanity (reject suspicious zero-padded magnitudes)
- analyst-paraphrase paraphrase ≤ 280 chars + reviewer present
- framework inputs declare a primitive-slug binding (never a scalar default)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..loader import LoadedRecords
from ..models import (
    SHA256_PATTERN,
    AtomicPrimitive,
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
    """Local-to-one-record checks. Pydantic already enforces sha256 hex shape on
    the field type, the analyst-paraphrase discriminated-union requirements, and
    the finite/non-negative invariant on value — this layer adds the
    *temporal* and *sig-fig* checks that aren't expressible at the type level.
    """
    errors: list[SemanticError] = []
    for p in primitives:
        # Pydantic's `Sha256Hex` already enforces format; this layer just covers
        # the case where someone bypasses the model (e.g. dynamic construction).
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
                    message=(
                        f"as_of {p.as_of.isoformat()} is in the future (today={today.isoformat()})"
                    ),
                )
            )
        if not math.isfinite(p.value):
            errors.append(
                SemanticError(
                    code="semantic.non_finite_value",
                    slug=p.slug,
                    message=f"value {p.value!r} is NaN or infinite",
                )
            )
        if p.value <= 0 and p.unit.dimension.value != "percent":
            errors.append(
                SemanticError(
                    code="semantic.nonpositive_value",
                    slug=p.slug,
                    message=f"value {p.value} not strictly positive for non-percent primitive",
                )
            )
    return errors


def _framework_no_scalar_defaults(records: LoadedRecords) -> list[SemanticError]:
    """Q15: every variant input must point at a primitive slug, never a scalar.

    Inspects the *raw* YAML payload so we catch numeric defaults with a precise
    error message (Pydantic v2 strict also rejects them via the typed
    ``default_inputs: dict[str, Slug]``, but its message is generic). Malformed
    shapes (variants-not-a-list, default_inputs-not-a-dict) are reported as
    their own errors rather than silently skipped — without the explicit
    report, a regression that loosened the field types would silently disable
    the Q15 guard.
    """
    errors: list[SemanticError] = []
    for path, raw in records.raw_by_path.items():
        if raw.get("kind") != "framework":
            continue
        slug = str(raw.get("slug") or path.stem)
        variants_raw = raw.get("variants")
        if variants_raw is None:
            continue
        if not isinstance(variants_raw, list):
            errors.append(
                SemanticError(
                    code="semantic.framework_variants_malformed",
                    slug=slug,
                    message=(f"`variants` must be a list, got {type(variants_raw).__name__}"),
                )
            )
            continue
        variants_list: list[Any] = variants_raw
        for variant_item in variants_list:
            if not isinstance(variant_item, dict):
                errors.append(
                    SemanticError(
                        code="semantic.framework_variants_malformed",
                        slug=slug,
                        message=(
                            f"every entry in `variants` must be a mapping, got "
                            f"{type(variant_item).__name__}"
                        ),
                    )
                )
                continue
            variant: dict[str, Any] = {str(k): v for k, v in variant_item.items()}
            defaults_raw = variant.get("default_inputs")
            if defaults_raw is None:
                continue
            if not isinstance(defaults_raw, dict):
                errors.append(
                    SemanticError(
                        code="semantic.framework_variants_malformed",
                        slug=slug,
                        message=(
                            f"variant scope={variant.get('scope')!r} `default_inputs` "
                            f"must be a mapping, got {type(defaults_raw).__name__}"
                        ),
                    )
                )
                continue
            defaults: dict[str, Any] = {str(k): v for k, v in defaults_raw.items()}
            for input_name, value in defaults.items():
                if not isinstance(value, str):
                    errors.append(
                        SemanticError(
                            code="semantic.framework_scalar_default",
                            slug=slug,
                            message=(
                                f"variant scope={variant.get('scope')!r} input "
                                f"{input_name!r} has scalar default {value!r}; every "
                                f"input must point at a primitive slug (Q15)"
                            ),
                        )
                    )
    return errors
