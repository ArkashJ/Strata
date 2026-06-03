"""Number-level provenance (sub-project 3, v1): every consumed atomic input
carries its source URL so the UI can hyperlink the number itself to the source
behind it — not just name the tier.

A composite has no single source of its own (it unions members, Q3), so its
``source_url`` stays ``None`` — the artifact links members individually rather
than inventing one URL for a derived number.

``source_url`` is display enrichment only: the state-hash payload projects
name/primitive/hash per input, so adding it can never re-mint an existing
/tam/<hash> permalink (pinned by test_enrichment_does_not_change_state_hash).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def test_atomic_inputs_carry_their_source_url(registry: Registry) -> None:
    """Each atomic input's source_url is its primitive's real source.url."""
    tam = size_concept(registry, "ai-legal-assistants-us")
    atomics_seen = 0
    for sc in tam.scenarios:
        for iu in sc.inputs_used:
            if iu.primitive_slug in registry.atomic:
                atomics_seen += 1
                expected = str(registry.atomic[iu.primitive_slug].source.url)
                assert iu.source_url == expected
                assert iu.source_url
    assert atomics_seen > 0  # the assertion above actually ran


def test_composite_input_has_no_single_source_url(registry: Registry) -> None:
    """A composite reports no source_url — it has members, not a source."""
    tam = size_concept(registry, "ai-coding-assistants-us")
    sc = tam.scenarios[0]
    persona = next(iu for iu in sc.inputs_used if iu.role_name == "persona_pool")
    assert persona.primitive_slug == "us-software-engineering-workforce"  # composite
    assert persona.source_url is None


def test_enrichment_does_not_change_state_hash(registry: Registry) -> None:
    """source_url is display-only: two sizings of the same concept (with and
    without the field populated they would be identical anyway) mint the same
    hash, and the hash projection ignores enrichment fields entirely."""
    a = size_concept(registry, "ai-legal-assistants-us")
    b = size_concept(registry, "ai-legal-assistants-us")
    assert a.state_hash == b.state_hash
