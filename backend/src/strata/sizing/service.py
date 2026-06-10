"""The sizing service — company → TAM orchestration (spec §5).

Productizes ``scripts/tam_77_pipeline.py`` into a pure, importable entry point.
The headline guarantee (F3): ``size_company`` is **safe to call with no live
flags** — it then does registry-first matching only and returns ``unsizable`` on
a miss, never a live LLM/Exa call. Every demo/prod request path uses exactly
that mode, so nothing a reviewer sees ever hits Claude or Exa.

  size_company(reg, company, *, opts) -> SizeResult

Pipeline:
  0. explicit market_concept_slug on the record (the curated demo mapping) → size it
  1. registry-first match (free, no LLM) → size the shared concept
  2. OFFLINE GUARD — STRATA_OFFLINE=1 or both live flags off → unsizable (no I/O)
  3. live classify → source(connector|Exa+guard) → persist → evaluate  [flag-gated]
  6. unsizable → record a lens-gap row (§9)
"""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

from strata.evaluator.engine import EvaluatorError, size_concept
from strata.models import CompanyRecord, LensGap, TAMOutput
from strata.registry import Registry
from strata.resolver.match import match_concept


@dataclass(frozen=True, slots=True)
class SizeOptions:
    """Controls the cost surface. Demo/prod render paths pass the defaults (both
    live flags off) so sizing is registry-first only — F3-safe."""

    allow_live: bool = False  # connector (regulator) calls
    allow_exa: bool = False  # analyst fallback
    budget: float = 0.0  # max LLM/Exa spend per batch
    persist: bool = True  # dry-run when False


@dataclass(slots=True)
class SizeResult:
    company: CompanyRecord
    tam: TAMOutput | None = None
    verdict: str = "unsized"  # sized | unsizable | registry_hit
    lens_gap: LensGap | None = None
    notes: list[str] = field(default_factory=lambda: list[str]())


def _offline() -> bool:
    return os.environ.get("STRATA_OFFLINE") == "1"


def sourced_scenarios(reg: Registry, slug: str) -> tuple[float, ...]:
    """A curated concept's sourced scenario values — the comparison side of the
    sense-check cross-check, shared by the CLI and the MCP tool. Validates the
    slug via ``get_concept`` (RegistryError) before sizing (EvaluatorError) so
    each surface can map "unknown slug" and "unsizable" to its own error."""
    reg.get_concept(slug)
    return tuple(s.value for s in size_concept(reg, slug).scenarios)


def _tam_midpoint(tam: TAMOutput) -> float:
    """Representative TAM value = median of the satisfiable scenario values
    (no new number invented — pure synthesis of sourced scenarios)."""
    return statistics.median([s.value for s in tam.scenarios])


def _size_from_concept(reg: Registry, company: CompanyRecord, slug: str) -> SizeResult:
    tam = size_concept(reg, slug)
    company.market_concept_slug = slug
    company.tam_value = _tam_midpoint(tam)
    company.status = "sized"
    company.sized_at = datetime.now(UTC)
    return SizeResult(company=company, tam=tam, verdict="sized")


def _unsizable(
    company: CompanyRecord, *, reason: str, missing_role: str | None = None
) -> SizeResult:
    company.status = "unsizable"
    company.reason = reason
    gap = LensGap(
        company=company.name,
        domain=company.domain,
        proposed_lens=company.vertical,
        missing_role=missing_role,
        reason=reason,
        ts=datetime.now(UTC).isoformat(),
    )
    return SizeResult(company=company, verdict="unsizable", lens_gap=gap)


def size_company(
    reg: Registry,
    company: CompanyRecord,
    *,
    opts: SizeOptions | None = None,
) -> SizeResult:
    """Size one company. Registry-first and offline-safe by default (F3)."""
    opts = opts or SizeOptions()

    # 0. Curated explicit mapping wins (the demo subset sets this directly).
    if company.market_concept_slug and company.market_concept_slug in reg.concepts:
        try:
            return _size_from_concept(reg, company, company.market_concept_slug)
        except EvaluatorError as exc:
            return _unsizable(company, reason=f"mapped concept not evaluable: {exc}")

    # 1. Registry-first fuzzy match — free, deterministic, no LLM.
    query = f"{company.name} {company.vertical or ''}".strip()
    slug = match_concept(reg, query)
    if slug and slug in reg.concepts:
        try:
            return _size_from_concept(reg, company, slug)
        except EvaluatorError:
            slug = None  # fall through to unsizable / live

    # 2. OFFLINE GUARD — never go live on any demo/prod render path.
    if _offline() or (not opts.allow_live and not opts.allow_exa):
        return _unsizable(
            company,
            reason="no registry market match (registry-first only; live sizing disabled)",
        )

    # 3. LIVE classify → source → persist → evaluate. Flag-gated; the demo never
    #    reaches here. Productizing the full tam_77_pipeline live path is tracked
    #    as the next increment — today the live miss is honestly unsizable rather
    #    than an invented number (Q20 wall holds).
    return _unsizable(
        company,
        reason="no curated market and live sizing not yet wired into the service path",
    )
