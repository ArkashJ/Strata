"""Validator unit tests.

Covers the four error paths called out in the v0.2 lens-aware concept slice:
  - paraphrase source missing ``original_publisher``
  - primitive ``as_of`` in the future
  - framework variant carrying a scalar default (Q15 violation)
  - framework lens tag disagreeing with the consuming concept's lens
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from strata.validator import validate

# Hashes are valid 64-char hex digests, content-independent for fixtures.
H_NAIC = "1a2b3c4d" * 8
H_BLS = "2b3c4d5e" * 8
H_GARTNER = "3c4d5e6f" * 8
H_BLS_W = "4d5e6f70" * 8


def _write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _seed_minimal(root: Path, *, secondary: str | None = "revenue_generation") -> None:
    """Write a minimal coherent dataset (concept + 4 primitives + 2 frameworks).

    Callers mutate one file per test to exercise the failure mode under test.
    """
    _write_yaml(
        root / "concepts" / "doc-gen-pc-insurance.yaml",
        {
            "kind": "concept",
            "slug": "doc-gen-pc-insurance",
            "schema_version": 1,
            "name": "Doc-gen P&C",
            "definition": "test fixture",
            "analysis_lens": {
                "primary": "cost_efficiency",
                "secondary": secondary,
            },
            "modifiers": {},
            "measurements": [
                "bls-pc-claims-adjusters-headcount",
                "naic-active-pc-carriers-2024",
                "pc-saas-spend-per-carrier-2024",
                "pc-claims-adjuster-cost-per-seat",
            ],
            "competing_concepts": [],
            "requires_clearance": [],
        },
    )
    _write_yaml(
        root / "primitives" / "naic-active-pc-carriers-2024.yaml",
        {
            "kind": "atomic_primitive",
            "slug": "naic-active-pc-carriers-2024",
            "schema_version": 1,
            "concept_slug": "doc-gen-pc-insurance",
            "name": "NAIC carriers",
            "description": "fixture",
            "value": 2541,
            "unit": {"kind": "stock", "dimension": "organizations"},
            "as_of": "2024-12-31",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "supply",
            "distribution_shape": "uniform",
            "delivery_mode": "n/a",
            "source": {
                "slug": "naic-2024",
                "tier": "regulator",
                "url": "https://example.com/naic",
                "accessed": "2026-05-22",
                "snapshot_sha256": H_NAIC,
            },
        },
    )
    _write_yaml(
        root / "primitives" / "bls-pc-claims-adjusters-headcount.yaml",
        {
            "kind": "atomic_primitive",
            "slug": "bls-pc-claims-adjusters-headcount",
            "schema_version": 1,
            "concept_slug": "doc-gen-pc-insurance",
            "name": "BLS headcount",
            "description": "fixture",
            "value": 322500,
            "unit": {"kind": "stock", "dimension": "people"},
            "as_of": "2024-05-31",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "supply",
            "distribution_shape": "normal",
            "delivery_mode": "n/a",
            "source": {
                "slug": "bls-2024",
                "tier": "regulator",
                "url": "https://example.com/bls",
                "accessed": "2026-05-22",
                "snapshot_sha256": H_BLS,
            },
        },
    )
    _write_yaml(
        root / "primitives" / "pc-saas-spend-per-carrier-2024.yaml",
        {
            "kind": "atomic_primitive",
            "slug": "pc-saas-spend-per-carrier-2024",
            "schema_version": 1,
            "concept_slug": "doc-gen-pc-insurance",
            "name": "PC SaaS spend",
            "description": "fixture",
            "value": 185000,
            "unit": {
                "kind": "intensive",
                "dimension": "currency",
                "currency": "USD",
                "denominator": "per-carrier-per-year",
            },
            "as_of": "2024-12-31",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "demand",
            "distribution_shape": "power_law",
            "delivery_mode": "direct",
            "source": {
                "slug": "gartner-2024",
                "tier": "analyst-paraphrase",
                "url": "https://example.com/gartner",
                "accessed": "2026-05-22",
                "snapshot_sha256": H_GARTNER,
                "original_publisher": "Gartner",
                "paraphrase_reviewer": "arkash",
                "paraphrase_text": "Gartner sizes 2024 US P&C SaaS spend at ~$185K per carrier.",
            },
        },
    )
    _write_yaml(
        root / "primitives" / "pc-claims-adjuster-cost-per-seat.yaml",
        {
            "kind": "atomic_primitive",
            "slug": "pc-claims-adjuster-cost-per-seat",
            "schema_version": 1,
            "concept_slug": "doc-gen-pc-insurance",
            "name": "Cost per seat",
            "description": "fixture",
            "value": 480,
            "unit": {
                "kind": "intensive",
                "dimension": "currency",
                "currency": "USD",
                "denominator": "per-seat-per-year",
            },
            "as_of": "2024-12-31",
            "geo": {"level": "country", "codes": ["US"]},
            "geo_perspective": "demand",
            "distribution_shape": "normal",
            "delivery_mode": "direct",
            "source": {
                "slug": "bls-wages-2024",
                "tier": "regulator",
                "url": "https://example.com/bls-wages",
                "accessed": "2026-05-22",
                "snapshot_sha256": H_BLS_W,
            },
        },
    )
    _write_yaml(
        root / "frameworks" / "bottoms-up-cost-efficiency.yaml",
        {
            "kind": "framework",
            "slug": "bottoms-up-cost-efficiency",
            "schema_version": 1,
            "name": "Bottoms-up cost efficiency",
            "method_family": "bottoms_up_seats",
            "lens": "cost_efficiency",
            "inputs": [
                {
                    "name": "persona_pool",
                    "role": "base_value",
                    "unit_signature": {"kind": "stock", "dimension": "people"},
                    "required": True,
                },
                {
                    "name": "cost_per_persona",
                    "role": "base_value",
                    "unit_signature": {
                        "kind": "intensive",
                        "dimension": "currency",
                        "currency": "USD",
                    },
                    "required": True,
                },
            ],
            "formula": "persona_pool * cost_per_persona",
            "output_unit": {
                "kind": "flow",
                "dimension": "currency",
                "currency": "USD",
                "denominator": "per-year",
            },
            "applicable_to": ["doc-gen-pc-insurance"],
            "variants": [
                {
                    "scope": "doc-gen-pc-insurance",
                    "default_inputs": {
                        "persona_pool": "bls-pc-claims-adjusters-headcount",
                        "cost_per_persona": "pc-claims-adjuster-cost-per-seat",
                    },
                }
            ],
            "expansion_stage_parameter": False,
            "horizon_class": "snapshot",
        },
    )
    _write_yaml(
        root / "frameworks" / "top-down-revenue-capture.yaml",
        {
            "kind": "framework",
            "slug": "top-down-revenue-capture",
            "schema_version": 1,
            "name": "Top-down revenue capture",
            "method_family": "top_down_spend",
            "lens": "revenue_generation",
            "inputs": [
                {
                    "name": "target_segment_count",
                    "role": "base_value",
                    "unit_signature": {"kind": "stock", "dimension": "organizations"},
                    "required": True,
                },
                {
                    "name": "spend_per_target",
                    "role": "base_value",
                    "unit_signature": {
                        "kind": "intensive",
                        "dimension": "currency",
                        "currency": "USD",
                    },
                    "required": True,
                },
            ],
            "formula": "target_segment_count * spend_per_target",
            "output_unit": {
                "kind": "flow",
                "dimension": "currency",
                "currency": "USD",
                "denominator": "per-year",
            },
            "applicable_to": ["doc-gen-pc-insurance"],
            "variants": [
                {
                    "scope": "doc-gen-pc-insurance",
                    "default_inputs": {
                        "target_segment_count": "naic-active-pc-carriers-2024",
                        "spend_per_target": "pc-saas-spend-per-carrier-2024",
                    },
                }
            ],
            "expansion_stage_parameter": False,
            "horizon_class": "snapshot",
        },
    )


def test_minimal_fixture_passes(tmp_path: Path) -> None:
    _seed_minimal(tmp_path)
    report = validate(tmp_path)
    assert report.ok, [(f.code, f.message) for f in report.errors]


def test_paraphrase_missing_original_publisher_rejected(tmp_path: Path) -> None:
    _seed_minimal(tmp_path)
    # Strip `original_publisher` from the paraphrase primitive. Pydantic's
    # model_validator on Source surfaces the breakage at parse time, which the
    # loader bubbles up as a structural/loader error.
    path = tmp_path / "primitives" / "pc-saas-spend-per-carrier-2024.yaml"
    payload = yaml.safe_load(path.read_text())
    del payload["source"]["original_publisher"]
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = validate(tmp_path)
    assert not report.ok
    assert any("original_publisher" in f.message for f in report.errors), report.errors


def test_as_of_in_future_rejected(tmp_path: Path) -> None:
    _seed_minimal(tmp_path)
    path = tmp_path / "primitives" / "naic-active-pc-carriers-2024.yaml"
    payload = yaml.safe_load(path.read_text())
    payload["as_of"] = "2999-01-01"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = validate(tmp_path)
    assert not report.ok
    codes = [f.code for f in report.errors]
    assert "semantic.as_of_in_future" in codes, codes


def test_framework_scalar_default_rejected(tmp_path: Path) -> None:
    """Q15: every framework input binding is a primitive slug, never a scalar."""
    _seed_minimal(tmp_path)
    # Hand-write a YAML where one variant binds a number directly. Pydantic
    # would also reject this; the semantic layer catches it first with a
    # precise error message.
    (tmp_path / "frameworks" / "bottoms-up-cost-efficiency.yaml").write_text(
        dedent(
            """\
            kind: framework
            slug: bottoms-up-cost-efficiency
            schema_version: 1
            name: Bottoms-up cost efficiency
            method_family: bottoms_up_seats
            lens: cost_efficiency
            inputs:
              - name: persona_pool
                role: base_value
                unit_signature: { kind: stock, dimension: people }
                required: true
              - name: cost_per_persona
                role: base_value
                unit_signature: { kind: intensive, dimension: currency, currency: USD }
                required: true
            formula: persona_pool * cost_per_persona
            output_unit: { kind: flow, dimension: currency, currency: USD, denominator: per-year }
            applicable_to: [doc-gen-pc-insurance]
            variants:
              - scope: doc-gen-pc-insurance
                default_inputs:
                  persona_pool: bls-pc-claims-adjusters-headcount
                  cost_per_persona: 480      # Q15 violation: scalar not a slug
            expansion_stage_parameter: false
            horizon_class: snapshot
            """
        ),
        encoding="utf-8",
    )
    report = validate(tmp_path)
    assert not report.ok
    codes = [f.code for f in report.errors]
    assert any("scalar_default" in c or "loader" in c for c in codes), codes


def test_lens_tag_mismatch_rejected(tmp_path: Path) -> None:
    _seed_minimal(tmp_path, secondary=None)
    # Concept has only cost_efficiency as primary; the revenue_generation
    # framework still scopes a variant at the concept → lens tag mismatches.
    report = validate(tmp_path)
    assert not report.ok
    codes = [f.code for f in report.errors]
    assert "cross.lens_tag_mismatch" in codes, codes


def test_secondary_lens_30pct_overlap_warning(tmp_path: Path) -> None:
    """When two scenarios land within 30%, warn that the secondary lens is
    not doing strategic work.
    """
    _seed_minimal(tmp_path)
    # Push the cost-efficiency primitive value high so scenarios overlap.
    # naic x spend = 2541 x 185_000 = 470,085,000. Match within 30%.
    path = tmp_path / "primitives" / "pc-claims-adjuster-cost-per-seat.yaml"
    payload = yaml.safe_load(path.read_text())
    payload["value"] = 1300  # 322,500 x 1,300 = 419,250,000 → 11% off
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = validate(tmp_path)
    assert report.ok, [(f.code, f.message) for f in report.errors]
    codes = [f.code for f in report.warnings]
    assert "cross.secondary_lens_low_strategic_work" in codes, codes


@pytest.mark.parametrize("missing_field", ["paraphrase_reviewer", "paraphrase_text"])
def test_paraphrase_missing_required_field_rejected(tmp_path: Path, missing_field: str) -> None:
    _seed_minimal(tmp_path)
    path = tmp_path / "primitives" / "pc-saas-spend-per-carrier-2024.yaml"
    payload = yaml.safe_load(path.read_text())
    del payload["source"][missing_field]
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = validate(tmp_path)
    assert not report.ok
    assert any(missing_field in f.message for f in report.errors), report.errors
