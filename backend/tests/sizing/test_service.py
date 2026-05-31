"""Sizing service tests (spec §5 + F3 offline-safety).

The headline guarantee: ``size_company`` never goes live with the default
options — registry-first match or honest ``unsizable``, no LLM/Exa. The demo and
every prod render path rely on exactly this.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.models import CompanyRecord
from strata.registry import Registry
from strata.sizing.service import SizeOptions, size_company

_DATA = Path(__file__).resolve().parents[2].parent / "data"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


def test_explicit_mapping_sizes_from_concept(registry: Registry) -> None:
    # The curated demo mapping sets market_concept_slug directly.
    slug = next(iter(registry.concepts))
    company = CompanyRecord(name="Acme", domain="acme.com", market_concept_slug=slug)
    res = size_company(registry, company)
    assert res.verdict == "sized"
    assert res.company.status == "sized"
    assert res.company.market_concept_slug == slug
    assert res.company.tam_value and res.company.tam_value > 0
    assert res.tam is not None


def test_registry_first_fuzzy_match(registry: Registry) -> None:
    # A name close to a curated concept should match registry-first, no LLM.
    company = CompanyRecord(name="AI coding assistants US", domain="copilotx.com")
    res = size_company(registry, company)
    assert res.verdict == "sized"
    assert res.company.market_concept_slug is not None


def test_unknown_company_is_unsizable_offline(registry: Registry) -> None:
    company = CompanyRecord(name="Zzqxv Quantum Llama Foundry", domain="zzqxv.example")
    res = size_company(registry, company)
    assert res.verdict == "unsizable"
    assert res.company.status == "unsizable"
    assert res.lens_gap is not None
    assert res.lens_gap.company == "Zzqxv Quantum Llama Foundry"


def test_default_opts_never_go_live_even_with_flags_when_offline(registry: Registry) -> None:
    # STRATA_OFFLINE forces registry-first only even if allow_live is set.
    company = CompanyRecord(name="Zzqxv Quantum Llama Foundry", domain="zzqxv.example")
    prev = os.environ.get("STRATA_OFFLINE")
    os.environ["STRATA_OFFLINE"] = "1"
    try:
        res = size_company(registry, company, opts=SizeOptions(allow_live=True, allow_exa=True))
    finally:
        if prev is None:
            os.environ.pop("STRATA_OFFLINE", None)
        else:
            os.environ["STRATA_OFFLINE"] = prev
    assert res.verdict == "unsizable"
