# Scope-Driven Primitive Re-Selection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/build` scope tags *drive the TAM number* — when a declared market scope is set, the evaluator picks each framework input's primitive from a candidate pool by scope-match instead of the fixed variant binding, so narrowing/widening a tag re-selects the source and recomputes.

**Architecture:** A framework *variant* hard-binds each input role to one primitive slug (`variant.default_inputs`). This plan adds a selection layer: for a role with ≥2 sourced candidates (same unit, owned by the concept), the evaluator runs the scope guard against each candidate and picks the most-benign match. It engages only when a declared scope is present and the pool has ≥2 members — so every existing concept is byte-for-byte unchanged. The declared scope is carried as a new `EvalOverrides.scope_override`, threaded through `POST /build/recompute`, and folded into the state hash so every tag edit mints a fresh `/build/<hash>`.

**Tech stack:** Python 3.12 · Pydantic v2 (frozen models) · pyright strict · ruff · pytest (run from `backend/`, data at `../data`). Web: Next.js 16 · React 19 · zod · TanStack Query · biome · vitest (run from `web/`). Builds on sub-project 1 (`strata.models.scope`, `strata.scope.guard`, `ScopeReport`), merged in PR #80. Design: `docs/superpowers/specs/2026-05-31-rigorous-market-definition-design.md` (Addendum — sub-project 1.5).

**Precedence in `_build_scenario`:** explicit `framework_assumptions` swap ▸ scope re-selection ▸ `variant.default_inputs`.

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `backend/src/strata/scope/selection.py` | candidate pool per role + scope-ranked pick | **create** |
| `backend/src/strata/scope/__init__.py` | export `candidates_for_role`, `select_primitive` | modify |
| `backend/src/strata/evaluator/engine.py` | `EvalOverrides.scope_override`; re-selection in `_build_scenario`; effective declared scope for report; hash fold | modify |
| `backend/src/strata/api/routes/build.py` | `scope` field on `RecomputeRequest` → `EvalOverrides.scope_override` | modify |
| `backend/tests/test_scope_selection.py` | candidate pool + selection ranking | **create** |
| `backend/tests/test_scope_reselection.py` | end-to-end: widen persona → acs picked → value changes; hash changes; precedence | **create** |
| `web/src/lib/schemas.ts` | `RecomputeRequest` scope field type (if typed) | modify |
| `web/src/components/build/ScopeEditor.tsx` | editable scope chips → recompute → navigate to new hash | **create** |
| `web/src/components/build/BuildWorkspace.tsx` | mount `ScopeEditor` | modify |
| `web/src/components/build/__tests__/ScopeEditor.test.tsx` | chip remove/add emits the right recompute body | **create** |

Re-selection candidates are demonstrated by `demo-ai-sales-ops-us`: the `persona_pool` role already has two sourced candidates — `demo-bls-sales-reps-us-2024` (SOC 41-4012, wholesale-only) and `demo-acs-sales-reps-us-2024` (SOC 41-3000 + 41-4000). No new data is required for the acceptance test.

---

## Task 1: Candidate pool + scope-ranked selection

**Files:**
- Create: `backend/src/strata/scope/selection.py`
- Modify: `backend/src/strata/scope/__init__.py`
- Test: `backend/tests/test_scope_selection.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_scope_selection.py
"""Scope-ranked primitive re-selection (sub-project 1.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.models import MarketScope
from strata.registry import Registry
from strata.scope.selection import candidates_for_role, select_primitive

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_CONCEPT = "demo-ai-sales-ops-us"
_FW = "bottoms-up-cost-efficiency"
_PERSONA_ROLE = "persona_pool"
_BLS = "demo-bls-sales-reps-us-2024"  # SOC 41-4012 (wholesale only)
_ACS = "demo-acs-sales-reps-us-2024"  # SOC 41-3000 + 41-4000


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def _input_def(registry: Registry, fw_slug: str, role: str):
    fw = next(f for f in registry.iter_frameworks() if f.slug == fw_slug)
    return next(i for i in fw.inputs if i.name == role)


def test_candidate_pool_is_unit_matched_and_concept_owned(registry: Registry):
    concept = registry.get_concept(_CONCEPT)
    pool = candidates_for_role(registry, concept, _input_def(registry, _FW, _PERSONA_ROLE))
    slugs = {p.slug for p in pool}
    assert _BLS in slugs and _ACS in slugs  # both people-stock headcounts
    # the per-seat price ($/seat) has a different unit → not a persona candidate
    assert "demo-ai-sales-ops-acv-per-seat-2024" not in slugs


def test_select_picks_exact_scope_match_over_narrower(registry: Registry):
    concept = registry.get_concept(_CONCEPT)
    pool = candidates_for_role(registry, concept, _input_def(registry, _FW, _PERSONA_ROLE))
    # declared = all B2B reps (41-3000 + 41-4000) → acs is EXACT, bls is NARROWER
    chosen = select_primitive(concept.scope, pool, default_slug=_BLS)
    assert chosen == _ACS


def test_select_narrow_declared_picks_the_narrow_source(registry: Registry):
    from strata.models import CodedTag, CodeSystem

    concept = registry.get_concept(_CONCEPT)
    pool = candidates_for_role(registry, concept, _input_def(registry, _FW, _PERSONA_ROLE))
    narrow = MarketScope(
        persona=(CodedTag(system=CodeSystem.SOC, code="41-4012", label="wholesale/mfg"),)
    )
    # bls is EXACT here, acs is BROADER → pick bls
    assert select_primitive(narrow, pool, default_slug=_ACS) == _BLS


def test_empty_declared_scope_keeps_the_default(registry: Registry):
    concept = registry.get_concept(_CONCEPT)
    pool = candidates_for_role(registry, concept, _input_def(registry, _FW, _PERSONA_ROLE))
    assert select_primitive(MarketScope(), pool, default_slug=_BLS) == _BLS


def test_single_candidate_keeps_the_default(registry: Registry):
    concept = registry.get_concept(_CONCEPT)
    one = [registry.get_atomic(_BLS)]
    assert select_primitive(concept.scope, one, default_slug=_BLS) == _BLS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_scope_selection.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'strata.scope.selection'`.

- [ ] **Step 3: Write the selection module**

```python
# backend/src/strata/scope/selection.py
"""Scope-ranked primitive re-selection (sub-project 1.5).

For a framework input role, the candidate pool is every primitive that matches
the input's unit signature AND belongs to the concept. When a declared scope is
present and the pool has >=2 members, the evaluator picks the candidate whose
true scope best matches the declared market (via the scope guard) instead of the
fixed variant binding. Pure and deterministic — no network, no LLM.
"""

from __future__ import annotations

from strata.models import AtomicPrimitive, Concept, MarketScope
from strata.models.framework import FrameworkInput
from strata.registry import Registry
from strata.scope.guard import Relationship, classify_scope

# Per-warning penalty when ranking a candidate against the declared scope. Lower
# total = better fit. DISJOINT excludes a candidate entirely (wrong market).
_PENALTY: dict[Relationship, int] = {
    Relationship.NARROWER: 1,
    Relationship.BROADER: 1,
    Relationship.PARTIAL: 2,
}


def candidates_for_role(
    registry: Registry, concept: Concept, input_def: FrameworkInput
) -> list[AtomicPrimitive]:
    """Primitives eligible to fill ``input_def`` for ``concept``: unit-matched and
    concept-owned (``concept_slug`` match or listed in ``concept.measurements``).
    Sorted by slug for deterministic tie-breaks."""
    owned = {
        slug
        for slug, p in registry.atomic.items()
        if p.concept_slug == concept.slug or slug in concept.measurements
    }
    return [
        registry.atomic[slug]
        for slug in sorted(owned)
        if registry.atomic[slug].unit == input_def.unit_signature
    ]


def _score(declared: MarketScope, scope: MarketScope) -> int | None:
    """Fit score of a candidate's ``scope`` against the ``declared`` market.
    ``None`` means excluded (a disjoint dimension = wrong market). 0 = exact."""
    match = classify_scope(declared, scope)
    total = 0
    for w in match.warnings:
        if w.relationship is Relationship.DISJOINT:
            return None
        total += _PENALTY.get(w.relationship, 0)
    return total


def select_primitive(
    declared: MarketScope, candidates: list[AtomicPrimitive], default_slug: str
) -> str:
    """Pick the best-scope-match candidate for the declared market. Falls back to
    ``default_slug`` when scope is unconstrained, the pool has <2 members, or no
    candidate is a non-disjoint match. The default wins ties (stable hash)."""
    if declared.is_empty or len(candidates) < 2:
        return default_slug
    by_slug = {c.slug: c for c in candidates}
    best_slug = default_slug
    # Seed with the default's own score so an equal-scoring alternative can NOT
    # displace it (default wins ties). Only a strictly-lower score replaces it;
    # among non-default candidates the slug-sorted order breaks remaining ties.
    best_score = _score(declared, by_slug[default_slug].scope) if default_slug in by_slug else None
    for cand in candidates:
        if cand.slug == default_slug:
            continue
        score = _score(declared, cand.scope)
        if score is None:
            continue
        if best_score is None or score < best_score:
            best_slug, best_score = cand.slug, score
    return best_slug
```

- [ ] **Step 4: Export from the package**

In `backend/src/strata/scope/__init__.py`, add to the imports and `__all__`:

```python
from .selection import candidates_for_role, select_primitive
```

```python
__all__ = [
    "Relationship",
    "ScopeMatch",
    "ScopeWarning",
    "build_scope_report",
    "candidates_for_role",
    "classify_scope",
    "select_primitive",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_scope_selection.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Lint + typecheck, then commit**

```bash
cd backend && uv run ruff check src/strata/scope tests/test_scope_selection.py \
  && uv run ruff format src/strata/scope/selection.py tests/test_scope_selection.py \
  && uv run pyright src/strata/scope/selection.py
git add src/strata/scope/selection.py src/strata/scope/__init__.py tests/test_scope_selection.py
git commit -m "feat(scope): scope-ranked primitive selection (candidate pool + guard ranking)"
```

---

## Task 2: Wire re-selection into the evaluator + state hash

**Files:**
- Modify: `backend/src/strata/evaluator/engine.py` (`EvalOverrides` ~line 63; `_build_scenario` ~line 286; `size_concept` payload ~line 142 and report call ~line 165)
- Test: `backend/tests/test_scope_reselection.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_scope_reselection.py
"""Scope override re-selects primitives and recomputes the TAM (sub-project 1.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.evaluator.engine import EvalOverrides
from strata.loader import load_data_dir
from strata.models import CodedTag, CodeSystem, MarketScope
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_CONCEPT = "demo-ai-sales-ops-us"
_BU = "bottoms-up-cost-efficiency"  # the persona_pool x cost_per_persona method
_BLS = "demo-bls-sales-reps-us-2024"  # 1.46M (wholesale only)
_ACS = "demo-acs-sales-reps-us-2024"  # 1.90M (all B2B)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def _bottoms_up(tam):
    return next(s for s in tam.scenarios if s.framework == _BU)


def _persona_slug(scenario) -> str:
    return next(iu.primitive_slug for iu in scenario.inputs_used if iu.role_name == "persona_pool")


_ALL_B2B = MarketScope(
    persona=(
        CodedTag(system=CodeSystem.SOC, code="41-3000", label="services"),
        CodedTag(system=CodeSystem.SOC, code="41-4000", label="wholesale/mfg"),
    )
)


def test_baseline_keeps_the_authored_variant_binding(registry: Registry):
    # No scope_override → re-selection does NOT engage; the curated variant default
    # (wholesale-only bls) stands, so the /tam default still surfaces the mismatch.
    tam = size_concept(registry, _CONCEPT)
    bu = _bottoms_up(tam)
    assert _persona_slug(bu) == _BLS
    assert abs(bu.value - 1_460_000 * 1_400) < 1.0  # $2.044B


def test_widen_scope_override_reselects_the_broad_source(registry: Registry):
    # User edits the declared market to all B2B reps → re-selection picks the EXACT
    # acs over the NARROWER bls → bottoms-up recomputes upward.
    tam = size_concept(registry, _CONCEPT, EvalOverrides(scope_override=_ALL_B2B))
    bu = _bottoms_up(tam)
    assert _persona_slug(bu) == _ACS
    assert abs(bu.value - 1_900_000 * 1_400) < 1.0  # $2.66B


def test_scope_override_changes_the_state_hash(registry: Registry):
    base = size_concept(registry, _CONCEPT)
    overridden = size_concept(registry, _CONCEPT, EvalOverrides(scope_override=_ALL_B2B))
    assert base.state_hash != overridden.state_hash


def test_scope_report_reflects_the_overridden_declared_market(registry: Registry):
    tam = size_concept(registry, _CONCEPT, EvalOverrides(scope_override=_ALL_B2B))
    assert tam.scope is not None
    assert [t.code for t in tam.scope.declared.persona] == ["41-3000", "41-4000"]
    # acs (now selected) is EXACT against the declared market → no persona warning
    acs = next(i for i in tam.scope.inputs if i.primitive_slug == _ACS)
    assert not [w for w in acs.warnings if w.dimension.value == "persona"]


def test_explicit_assumption_swap_beats_reselection(registry: Registry):
    # framework_assumptions must still win over scope re-selection.
    ov = EvalOverrides(
        scope_override=_ALL_B2B,
        framework_assumptions={_BU: {"persona_pool": _BLS}},
    )
    tam = size_concept(registry, _CONCEPT, ov)
    assert _persona_slug(_bottoms_up(tam)) == _BLS  # explicit swap wins over re-selection
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_scope_reselection.py -q`
Expected: FAIL — `EvalOverrides.__init__() got an unexpected keyword argument 'scope_override'`.

- [ ] **Step 3: Add `scope_override` to `EvalOverrides`**

In `backend/src/strata/evaluator/engine.py`, add the import to the existing `from ..models import (...)` block:

```python
    MarketScope,
```

Then extend the dataclass (`EvalOverrides`, ~line 63):

```python
@dataclass(frozen=True, slots=True)
class EvalOverrides:
    """Override-aware evaluation inputs (Strata Live Track A).

    - ``primitive_overrides`` substitutes a primitive's sourced value with a
      user what-if scalar at evaluation time → ``user_override`` banner +
      ``uses_synthetic_primitives``. The registry is NEVER mutated.
    - ``framework_assumptions`` re-points a named framework input to a
      different *existing* primitive slug before evaluation (schema-pure, no
      banner).
    - ``scope_override`` redefines the declared market (sub-project 1.5). It
      replaces ``concept.scope`` for both primitive re-selection and the scope
      report; folded into the state hash so every edit mints a fresh /build.
    """

    primitive_overrides: dict[str, OverrideValue] = field(default_factory=dict)
    framework_assumptions: dict[str, dict[str, str]] = field(default_factory=dict)
    scope_override: MarketScope | None = None
```

- [ ] **Step 4: Re-select inside `_build_scenario`**

In `backend/src/strata/evaluator/engine.py`, add the import near the other intra-package imports (below `from ..scope import build_scope_report`):

```python
from ..scope import build_scope_report, candidates_for_role, select_primitive
```

Then, in `_build_scenario` (~line 286), replace the binding line:

```python
    for input_def in fw.inputs:
        primitive_slug = assumptions.get(input_def.name) or variant.default_inputs.get(
            input_def.name
        )
```

with scope-aware re-selection (explicit assumption ▸ re-selection ▸ default). **Re-selection engages only on an explicit `scope_override`** — never the concept's baseline scope — so the default `/tam` view keeps the authored binding and still surfaces mismatches honestly (no merged behavior or golden hashes change):

```python
    concept = registry.get_concept(variant.scope)
    scope_override = overrides.scope_override if overrides is not None else None
    reselect = scope_override is not None and not scope_override.is_empty

    for input_def in fw.inputs:
        primitive_slug = assumptions.get(input_def.name)
        if primitive_slug is None and reselect:
            default = variant.default_inputs.get(input_def.name)
            if default is not None:
                pool = candidates_for_role(registry, concept, input_def)
                if len(pool) >= 2:
                    primitive_slug = select_primitive(scope_override, pool, default)
        if primitive_slug is None:
            primitive_slug = variant.default_inputs.get(input_def.name)
```

(Leave the `if primitive_slug is None: raise EvaluatorError(...)` block that follows unchanged. The narrowest `scope_override` test gates here; the baseline path is untouched.)

- [ ] **Step 5: Fold the override into the hash + use it for the report**

In `size_concept` (~line 139), extend the `payload["overrides"]` block so a scope edit mints a new hash:

```python
        payload["overrides"] = {
            "primitive_overrides": {
                slug: {"value": ov.value, "unit": ov.unit.model_dump(mode="json")}
                for slug, ov in sorted(overrides.primitive_overrides.items())
            },
            "framework_assumptions": {
                fw: dict(sorted(binds.items()))
                for fw, binds in sorted(overrides.framework_assumptions.items())
            },
            "scope_override": (
                overrides.scope_override.model_dump(mode="json")
                if overrides.scope_override is not None
                else None
            ),
        }
```

Then change the `scope=build_scope_report(...)` argument (~line 165) to use the effective declared scope:

```python
        scope=build_scope_report(
            registry,
            overrides.scope_override
            if overrides is not None and overrides.scope_override is not None
            else concept.scope,
            scenarios,
        ),
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_scope_reselection.py -q`
Expected: PASS (5 passed).

- [ ] **Step 7: Full regression + lint + typecheck**

Run: `cd backend && uv run pytest -q && uv run pyright src/strata/evaluator/engine.py && uv run ruff check src tests && uv run ruff format --check src/strata/evaluator/engine.py`
Expected: full suite green (no regression — re-selection is inert for single-candidate roles and empty scope), pyright/ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/strata/evaluator/engine.py tests/test_scope_reselection.py
git commit -m "feat(scope): scope_override re-selects primitives + recomputes (evaluator + hash)"
```

---

## Task 3: Accept a scope override on the recompute endpoint

**Files:**
- Modify: `backend/src/strata/api/routes/build.py` (`RecomputeRequest` ~line 34; `recompute_tam` handler ~line 96)
- Test: add to `backend/tests/test_build_recompute.py` (or create if absent)

- [ ] **Step 1: Write the failing API test**

```python
# append to backend/tests/test_build_recompute.py (create with the standard
# FastAPI TestClient fixture if the file does not exist; mirror an existing
# api test e.g. tests/test_resolve.py for the client fixture)
def test_recompute_with_scope_override_reselects(client):
    body = {
        "concept_slug": "demo-ai-sales-ops-us",
        "scope": {
            "vertical": [],
            "persona": [{"system": "SOC", "code": "41-4012", "label": "wholesale/mfg"}],
            "segment": None,
            "geo_supply": [],
            "geo_demand": [],
            "product": [],
            "include": [],
            "exclude": [],
        },
    }
    resp = client.post("/build/recompute", json=body)
    assert resp.status_code == 200
    tam = resp.json()
    bu = next(s for s in tam["scenarios"] if s["framework"] == "bottoms-up-cost-efficiency")
    persona = next(iu["primitive_slug"] for iu in bu["inputs_used"] if iu["role_name"] == "persona_pool")
    assert persona == "demo-bls-sales-reps-us-2024"
    assert tam["scope"]["declared"]["persona"][0]["code"] == "41-4012"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/test_build_recompute.py -q -k scope_override`
Expected: FAIL (422 — `scope` is an unexpected field, or persona is still the default).

- [ ] **Step 3: Add `scope` to `RecomputeRequest` and thread it**

In `backend/src/strata/api/routes/build.py`, add the model import:

```python
from strata.models import MarketScope
```

Extend `RecomputeRequest` (~line 34):

```python
class RecomputeRequest(BaseModel):
    concept_slug: str
    primitive_overrides: dict[str, OverrideValueIn] = {}
    framework_assumptions: dict[str, dict[str, str]] = {}
    scope: MarketScope | None = None
```

In `recompute_tam` where it constructs `EvalOverrides(...)`, pass the scope through:

```python
    overrides = EvalOverrides(
        primitive_overrides={...},          # unchanged
        framework_assumptions=req.framework_assumptions,
        scope_override=req.scope,
    )
```

(Keep the existing `_validate_override_units(reg, req)` call and the rest of the handler unchanged.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_build_recompute.py -q -k scope_override`
Expected: PASS.

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run pyright src/strata/api/routes/build.py && uv run ruff check src/strata/api tests/test_build_recompute.py
git add src/strata/api/routes/build.py tests/test_build_recompute.py
git commit -m "feat(scope): accept scope override on POST /build/recompute"
```

---

## Task 4: Editable scope chips on `/build`

**Files:**
- Modify: `web/src/lib/schemas.ts` (recompute request type, if one is exported)
- Create: `web/src/components/build/ScopeEditor.tsx`
- Modify: `web/src/components/build/BuildWorkspace.tsx` (mount the editor)
- Test: `web/src/components/build/__tests__/ScopeEditor.test.tsx`

First read `web/src/components/build/BuildWorkspace.tsx` and `web/src/lib/queries.ts` to find the existing recompute mutation (it already POSTs `primitive_overrides`/`framework_assumptions` to `/build/recompute` and navigates to the returned `state_hash`). The editor reuses that mutation, adding `scope` to the body.

- [ ] **Step 1: Write the failing component test**

```tsx
// web/src/components/build/__tests__/ScopeEditor.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MarketScope } from "@/lib/schemas";
import { ScopeEditor } from "../ScopeEditor";

const SCOPE: MarketScope = {
  vertical: [],
  persona: [
    { system: "SOC", code: "41-3000", label: "services" },
    { system: "SOC", code: "41-4000", label: "wholesale/mfg" },
  ],
  segment: { min_emp: null, max_emp: null, label: "All employer firms" },
  geo_supply: [],
  geo_demand: ["US"],
  product: [],
  include: [],
  exclude: [],
};

describe("ScopeEditor", () => {
  it("removing a persona chip emits the narrowed scope", () => {
    const onChange = vi.fn();
    render(<ScopeEditor scope={SCOPE} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /remove SOC 41-3000/i }));
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as MarketScope;
    expect(next.persona.map((p) => p.code)).toEqual(["41-4000"]);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web && bunx vitest run src/components/build/__tests__/ScopeEditor.test.tsx`
Expected: FAIL — cannot resolve `../ScopeEditor`.

- [ ] **Step 3: Write `ScopeEditor`**

```tsx
// web/src/components/build/ScopeEditor.tsx
"use client";

import type { MarketScope } from "@/lib/schemas";

// Editable declared-market chips on /build. Removing a chip emits a narrowed
// MarketScope via onChange; the parent POSTs it as `scope` to /build/recompute,
// which re-selects primitives and navigates to the new /build/<hash>.
export function ScopeEditor({
  scope,
  onChange,
}: {
  scope: MarketScope;
  onChange: (next: MarketScope) => void;
}) {
  const removePersona = (code: string) =>
    onChange({ ...scope, persona: scope.persona.filter((p) => p.code !== code) });

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="scope-editor">
      <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Market</span>
      {scope.persona.map((p) => (
        <span
          key={p.code}
          className="inline-flex items-center gap-1 rounded-[var(--r-round)] bg-[var(--bg-2)] px-2.5 py-1 text-[11px] text-[var(--fg-1)]"
        >
          {p.system} {p.code} · {p.label}
          <button
            type="button"
            aria-label={`remove ${p.system} ${p.code}`}
            className="ml-0.5 text-[var(--fg-3)] hover:text-[var(--danger)]"
            onClick={() => removePersona(p.code)}
          >
            ×
          </button>
        </span>
      ))}
      {scope.segment ? (
        <span className="inline-flex items-center rounded-[var(--r-round)] bg-[var(--bg-2)] px-2.5 py-1 text-[11px] text-[var(--fg-1)]">
          {scope.segment.label}
        </span>
      ) : null}
      {scope.geo_demand.map((g) => (
        <span
          key={g}
          className="inline-flex items-center rounded-[var(--r-round)] bg-[var(--bg-2)] px-2.5 py-1 text-[11px] text-[var(--fg-1)]"
        >
          {g}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd web && bunx vitest run src/components/build/__tests__/ScopeEditor.test.tsx`
Expected: PASS.

- [ ] **Step 5: Mount it in `BuildWorkspace` and wire the recompute mutation**

In `web/src/components/build/BuildWorkspace.tsx`, render `<ScopeEditor scope={tam.scope.declared} onChange={handleScopeChange} />` near the top of the result (guarded on `tam.scope`). `handleScopeChange` calls the existing recompute mutation with the new `scope` in the body, then routes to the returned `state_hash` (mirror how the override panel already triggers recompute + navigation). Add `scope?: MarketScope` to the recompute request body type/builder in `web/src/lib/queries.ts` (or wherever the mutation body is assembled).

- [ ] **Step 6: Typecheck + biome + commit**

```bash
cd web && bun run typecheck \
  && bunx biome check --write src/components/build/ScopeEditor.tsx src/components/build/BuildWorkspace.tsx src/components/build/__tests__/ScopeEditor.test.tsx src/lib/schemas.ts src/lib/queries.ts \
  && bunx vitest run src/components/build/__tests__/ScopeEditor.test.tsx
git add web/src/components/build/ScopeEditor.tsx web/src/components/build/BuildWorkspace.tsx web/src/components/build/__tests__/ScopeEditor.test.tsx web/src/lib/schemas.ts web/src/lib/queries.ts
git commit -m "feat(scope): editable market-scope chips on /build (recompute on edit)"
```

---

## Final verification

- [ ] **Backend suite + gate:** `cd backend && uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .` — all green.
- [ ] **Web:** `cd web && bun run typecheck && bunx vitest run` — green; biome clean on changed files.
- [ ] **Acceptance (live, optional):** rebuild the docker stack, then
  `curl -s -X POST localhost:8000/build/recompute -H 'content-type: application/json' -d '{"concept_slug":"demo-ai-sales-ops-us","scope":{"vertical":[],"persona":[{"system":"SOC","code":"41-4012","label":"w/mfg"}],"segment":null,"geo_supply":[],"geo_demand":[],"product":[],"include":[],"exclude":[]}}'`
  → the `bottoms-up-cost-efficiency` scenario uses `demo-bls-sales-reps-us-2024` and `value ≈ 2.044e9`; the unconstrained baseline uses `demo-acs-sales-reps-us-2024`.
  (Local-docker SSR can't render `/tam` via `localhost` — verify by API JSON or host `bun dev`; see the `local-docker-and-ports` note.)
- [ ] **Open PR** off `main` (branch `feat/scope-driven-reselection`); CI runs `alembic upgrade head` + the suite. No migration is needed (no new columns — `scope_override` is request-only).

## Acceptance criteria

1. `size_concept(reg, "demo-ai-sales-ops-us")` (no override) picks `demo-acs-sales-reps-us-2024` for `persona_pool` (EXACT match to the all-B2B declared scope).
2. A `scope_override` narrowing persona to SOC `41-4012` re-selects `demo-bls-sales-reps-us-2024` and recomputes the bottoms-up value to ≈ $2.044B.
3. A scope override changes the `state_hash`; an explicit `framework_assumptions` swap still beats re-selection.
4. Concepts whose roles have a single sourced candidate are byte-for-byte unchanged (no silent swaps, nothing invented).
5. Full backend suite + web typecheck/vitest green; pyright + ruff + biome clean.
