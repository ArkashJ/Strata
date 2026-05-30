"""Wave 1 / AC1.4 — the resolver verifier flags outliers as dark_estimate."""

from __future__ import annotations

from strata.resolver.events import PipelineStatus, ResolverResult
from strata.resolver.verify import apply_verifier, has_dark_estimate, verify

_CURRENCY = {"kind": "intensive", "dimension": "currency", "currency": "USD"}
_PEOPLE = {"kind": "stock", "dimension": "people"}


def _result(primitives: list[dict], via: str = "fallback") -> ResolverResult:
    return ResolverResult(
        status=PipelineStatus.OK,
        via=via,  # type: ignore[arg-type]
        tam_value=1.0,
        primitives_used=primitives,
        banner="synthesized via fallback",
    )


def test_clean_inputs_have_no_flags() -> None:
    r = _result(
        [
            {"slug": "pop", "value": 1_000_000, "unit": _PEOPLE},
            {"slug": "wtp", "value": 500, "unit": _CURRENCY},
        ]
    )
    assert verify(r) == []
    assert not has_dark_estimate(apply_verifier(r))


def test_verifier_flags_outlier() -> None:
    r = _result(
        [
            {"slug": "pop", "value": -5, "unit": _PEOPLE},  # non-positive
            {"slug": "wtp", "value": 500, "unit": _CURRENCY},
        ]
    )
    flags = verify(r)
    assert any(f.kind == "outlier" for f in flags)
    assert has_dark_estimate(apply_verifier(r))


def test_verifier_flags_absurd_magnitude() -> None:
    r = _result(
        [
            {"slug": "pop", "value": 1e14, "unit": _PEOPLE},  # absurd
            {"slug": "wtp", "value": 500, "unit": _CURRENCY},
        ]
    )
    assert has_dark_estimate(apply_verifier(r))


def test_registry_results_not_downgraded() -> None:
    # A concept-sourced result is trusted; the verifier never stamps it.
    r = _result([{"slug": "x", "value": -5, "unit": _PEOPLE}], via="concept")
    assert not has_dark_estimate(apply_verifier(r))
