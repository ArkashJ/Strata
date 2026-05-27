"""Unit tests for the Pydantic models — Source paraphrase rules, Unit
compatibility, hashing determinism.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from strata.hashing import mint_state_hash
from strata.models import (
    PARAPHRASE_MAX_CHARS,
    Source,
    SourceTier,
    Unit,
    UnitDimension,
    UnitKind,
)

_SOURCE = TypeAdapter(Source)


def _src(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "slug": "src",
        "tier": SourceTier.ANALYST_PARAPHRASE,
        "url": "https://example.com",
        "accessed": date(2026, 5, 22),
        "snapshot_sha256": "a" * 64,
        "original_publisher": "Gartner",
        "paraphrase_reviewer": "arkash",
        "paraphrase_text": "fixture",
    }
    base.update(overrides)
    return base


def test_analyst_paraphrase_requires_all_paraphrase_fields() -> None:
    _SOURCE.validate_python(_src())  # ok
    for missing in ("original_publisher", "paraphrase_reviewer", "paraphrase_text"):
        bad = _src()
        bad[missing] = None
        with pytest.raises(ValidationError):
            _SOURCE.validate_python(bad)


def test_non_paraphrase_source_rejects_paraphrase_fields() -> None:
    payload = _src(tier=SourceTier.REGULATOR)
    with pytest.raises(ValidationError):
        _SOURCE.validate_python(payload)


def test_paraphrase_text_max_length_enforced() -> None:
    payload = _src(paraphrase_text="x" * (PARAPHRASE_MAX_CHARS + 1))
    with pytest.raises(ValidationError):
        _SOURCE.validate_python(payload)


def test_unit_compatibility_loose() -> None:
    concrete = Unit(
        kind=UnitKind.INTENSIVE,
        dimension=UnitDimension.CURRENCY,
        currency="USD",
        denominator="per-seat-per-year",
    )
    signature = Unit(
        kind=UnitKind.INTENSIVE,
        dimension=UnitDimension.CURRENCY,
        currency=None,
        denominator=None,
    )
    assert concrete.is_compatible_with(signature)


def test_unit_compatibility_rejects_dimension_mismatch() -> None:
    a = Unit(kind=UnitKind.STOCK, dimension=UnitDimension.PEOPLE)
    b = Unit(kind=UnitKind.STOCK, dimension=UnitDimension.CURRENCY)
    assert not a.is_compatible_with(b)


def test_state_hash_stable_and_key_independent() -> None:
    a = mint_state_hash({"concept": "x", "value": 1, "inputs": ["a", "b"]})
    b = mint_state_hash({"inputs": ["a", "b"], "value": 1, "concept": "x"})
    assert a == b
    different = mint_state_hash({"concept": "x", "value": 2, "inputs": ["a", "b"]})
    assert a != different
