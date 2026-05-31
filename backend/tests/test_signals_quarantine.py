"""Wave 0 / AC0.5 — prediction-market primitives are quarantined as signals.

Kalshi event-contract probabilities are *signals*, not sizing-grade sourced
measurements: they must never feed a framework or be counted as a primitive.
They live under ``data/signals/`` and load into ``registry.signals`` (read-only),
not ``registry.atomic``. ``strata stats`` reports the two counts separately.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from strata.loader import load_data_dir
from strata.models import SourceTier
from strata.registry import Registry

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "data"


def _atomic_source_tier(prim: object) -> SourceTier:
    return prim.source.tier  # type: ignore[attr-defined]


def test_signals_dir_exists() -> None:
    assert (_DATA / "signals").is_dir()


def test_no_prediction_market_in_primitives() -> None:
    # No committed YAML under data/primitives/ may carry the prediction_market tier.
    offenders = [
        p
        for p in (_DATA / "primitives").rglob("*.yaml")
        if "tier: prediction_market" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"prediction_market primitives still in data/primitives/: {offenders}"


def test_registry_excludes_signals_from_atomic() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    pm = [
        slug
        for slug, prim in reg.atomic.items()
        if _atomic_source_tier(prim) is SourceTier.PREDICTION_MARKET
    ]
    assert pm == [], f"prediction_market primitives leaked into registry.atomic: {pm}"


def test_signals_loaded_separately() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    assert len(reg.signals) > 0
    for prim in reg.signals.values():
        assert _atomic_source_tier(prim) is SourceTier.PREDICTION_MARKET


def test_signals_are_valid_yaml_atomic_kind() -> None:
    for p in (_DATA / "signals").rglob("*.yaml"):
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert raw.get("kind") == "atomic_primitive"
