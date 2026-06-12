"""Phase 4 — soft-data fence: provenance derivation, the hand-authored
loophole validator, MODELED banners, promote/writer guards, and Exa gating."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from strata.evaluator.engine import _banners_for
from strata.loader import load_data_dir
from strata.models import BannerKind
from strata.models.primitive import AtomicPrimitive, ProvenanceClass
from strata.models.source import SourceTier
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"
_SHA = "a" * 64

_MODELED_TIERS = (
    SourceTier.COMMUNITY_MODELED,
    SourceTier.ANALYST_PARAPHRASE,
    SourceTier.ANALYST,
)


def _prim(slug: str, *, tier: SourceTier, url: str = "https://www.bls.gov/x") -> AtomicPrimitive:
    if tier is SourceTier.ANALYST_PARAPHRASE:
        source: dict[str, Any] = {
            "slug": f"{slug}-src",
            "tier": tier.value,
            "url": url,
            "accessed": "2024-01-01",
            "snapshot_sha256": _SHA,
            "original_publisher": "Some Analyst",
            "paraphrase_text": "a short paraphrase under 280 chars",
            "paraphrase_reviewer": "reviewer-x",
        }
    else:
        source = {
            "slug": f"{slug}-src",
            "tier": tier.value,
            "url": url,
            "accessed": "2024-01-01",
            "snapshot_sha256": _SHA,
        }
    return AtomicPrimitive.model_validate(
        {
            "kind": "atomic_primitive",
            "slug": slug,
            "schema_version": 1,
            "concept_slug": "test-concept",
            "name": slug,
            "description": "test",
            "value": 100.0,
            "unit": {"kind": "stock", "dimension": "people"},
            "as_of": "2024-01-01",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "demand",
            "source": source,
        }
    )


# --------------------------------------------------------------------------- #
# Provenance derivation (self-consistency)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tier", _MODELED_TIERS)
def test_soft_tiers_derive_modeled(tier: SourceTier) -> None:
    p = _prim("p", tier=tier)
    assert p.provenance_class is ProvenanceClass.MODELED
    assert p.needs_resourcing is True


@pytest.mark.parametrize(
    "tier", [SourceTier.REGULATOR, SourceTier.AGGREGATOR, SourceTier.FIRST_PARTY]
)
def test_hard_tiers_derive_sourced(tier: SourceTier) -> None:
    p = _prim("p", tier=tier)
    assert p.provenance_class is ProvenanceClass.SOURCED
    assert p.needs_resourcing is False


def test_yaml_cannot_override_derivation() -> None:
    # Even if a hand-authored YAML lies (sourced label on a modeled tier), the
    # derived value wins — the two can never disagree.
    p = AtomicPrimitive.model_validate(
        {
            "kind": "atomic_primitive",
            "slug": "liar",
            "schema_version": 1,
            "concept_slug": "test-concept",
            "name": "liar",
            "description": "test",
            "value": 1.0,
            "unit": {"kind": "stock", "dimension": "people"},
            "as_of": "2024-01-01",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "demand",
            "source": {
                "slug": "liar-src",
                "tier": "community-modeled",
                "url": "https://strata.internal/x",
                "accessed": "2024-01-01",
                "snapshot_sha256": _SHA,
            },
            "provenance_class": "sourced",  # the lie — overridden by the validator
            "needs_resourcing": False,
        }
    )
    assert p.provenance_class is ProvenanceClass.MODELED
    assert p.needs_resourcing is True


def test_committed_bank_split() -> None:
    reg = Registry.from_loaded(load_data_dir(_DATA))
    modeled = [p for p in reg.atomic.values() if p.provenance_class is ProvenanceClass.MODELED]
    # Every modeled primitive carries a soft tier and is queued for re-sourcing.
    for p in modeled:
        assert p.source.tier in _MODELED_TIERS
        assert p.needs_resourcing is True
    # PR5 added 12 community-modeled structural-default / latent-demand inputs
    # (each MODELED-bannered, ranged, with a resolvable anchor URL). Temporal-TAM
    # added 1 more community-modeled input: the ai-coding seat-spend CAGR that
    # drives the today→future projection (correctly fenced, banner-flagged).
    assert len(modeled) == 77  # 36 community-modeled + 35 analyst-paraphrase + 6 analyst


# --------------------------------------------------------------------------- #
# Loophole validator (G1)
# --------------------------------------------------------------------------- #
def _internal_finding(p: AtomicPrimitive) -> list[str]:
    from strata.validator.semantic import semantic_check

    rec = load_data_dir(_DATA)
    # swap in just our primitive for a focused check
    rec.atomic_primitives.clear()
    rec.atomic_primitives.append(p)
    return [e.code for e in semantic_check(rec)]


def test_modeled_internal_host_passes() -> None:
    p = _prim("m", tier=SourceTier.COMMUNITY_MODELED, url="https://strata.internal/models/x")
    assert "semantic.unflagged_internal_host" not in _internal_finding(p)


def test_sourced_internal_host_fails() -> None:
    # A regulator-tier (→ sourced) primitive citing the fabricated internal host
    # is the exact hand-authored loophole — must be flagged.
    p = _prim("s", tier=SourceTier.REGULATOR, url="https://strata.internal/models/x")
    assert "semantic.unflagged_internal_host" in _internal_finding(p)


def test_committed_bank_has_no_unflagged_internal_host() -> None:
    # CI-enforced loophole gate: every committed primitive citing strata.internal
    # is honestly flagged modeled. A future hand-authored sourced+internal number
    # fails this test (which runs under pytest in CI), not just `strata validate`.
    from strata.validator.semantic import semantic_check

    offenders = [
        e.slug
        for e in semantic_check(load_data_dir(_DATA))
        if e.code == "semantic.unflagged_internal_host"
    ]
    assert offenders == []


# --------------------------------------------------------------------------- #
# MODELED banners — including the previously-silent analyst tier
# --------------------------------------------------------------------------- #
def test_analyst_tier_now_banners() -> None:
    p = _prim("a", tier=SourceTier.ANALYST)
    banners = _banners_for(p)
    assert any(b.kind is BannerKind.MODELED for b in banners)


def test_sourced_has_no_modeled_banner() -> None:
    p = _prim("r", tier=SourceTier.REGULATOR)
    assert not any(b.kind is BannerKind.MODELED for b in _banners_for(p))


# --------------------------------------------------------------------------- #
# Promote / writer guards (G2)
# --------------------------------------------------------------------------- #
def test_promote_refuses_modeled(tmp_path: Path) -> None:
    import yaml

    from strata.cli import _is_modeled_candidate

    p = _prim("modeled-candidate", tier=SourceTier.COMMUNITY_MODELED)
    src = tmp_path / "modeled-candidate.yaml"
    src.write_text(yaml.safe_dump(p.model_dump(mode="json")))
    assert _is_modeled_candidate(src) is True

    sourced = _prim("sourced-candidate", tier=SourceTier.REGULATOR)
    src2 = tmp_path / "sourced-candidate.yaml"
    src2.write_text(yaml.safe_dump(sourced.model_dump(mode="json")))
    assert _is_modeled_candidate(src2) is False


def test_writer_refuses_modeled() -> None:
    from strata.resolver.writer import upsert_primitive

    p = _prim("w", tier=SourceTier.COMMUNITY_MODELED, url="https://www.bls.gov/x")
    with pytest.raises(ValueError, match="MODELED"):
        upsert_primitive(
            primitive_yaml=p.model_dump(mode="json"),
            connector="bls",
            method="get_series",
            args={},
        )


# --------------------------------------------------------------------------- #
# Exa gating
# --------------------------------------------------------------------------- #
def test_exa_fallback_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.resolver.pipeline import RunOptions, exa_fallback_enabled

    monkeypatch.delenv("STRATA_ALLOW_EXA_FALLBACK", raising=False)
    assert RunOptions().allow_fallback is False
    assert exa_fallback_enabled() is False


def test_exa_fallback_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.resolver.pipeline import exa_fallback_enabled

    monkeypatch.setenv("STRATA_ALLOW_EXA_FALLBACK", "1")
    assert exa_fallback_enabled() is True
