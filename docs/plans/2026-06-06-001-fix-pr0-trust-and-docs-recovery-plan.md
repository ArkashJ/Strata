---
title: "fix: PR 0 — Trust quick-wins + doc/architecture recovery"
status: active
date: 2026-06-06
type: fix
branch: feat/pr0-trust-and-docs
origin: docs/TODO_june6.md (PR 0 section)
---

# PR 0 — Trust quick-wins + doc/architecture recovery

## Summary

PR 0 is the cheapest way to stop "fake sources / garbage export" on first
contact, plus restore the ground-truth docs deleted in `0e2787b` and land the
architecture diagrams. It is the first of the 6 stacked v1.0 PRs.

**Much of PR 0 is already done in the working tree** (branch
`feat/pr0-trust-and-docs`): `usda_nass` host-map entry added; `github`
deliberately *not* mapped (honest-zero, with an explanatory comment); the two
dead charts (`ScenarioBarChart`, `WaterfallChart`) staged for deletion; the
`TamReport` footer reproducibility claim made conditional on modeled inputs; a
`TODO(PR3)` marker on `ResolveResultChart`'s hardcoded hex. This plan finishes
the **remaining** gaps:

1. Kill the 12 `strata.internal` placeholder URLs on community-modeled primitives.
2. Stop displaying the 25 fake `d3d3…d3` demo snapshots as if real (UI honesty).
3. Make the 3 homepage-featured concepts deterministic + sourced-forward.
4. Restore the deleted ground-truth docs from git history; finalize `docs/architecture/`.
5. Fix stale "load-bearing" doc references in `CLAUDE.md` / `README`.
6. Verify: `strata validate` green, `strata verify-integrity` passes, `/connectors` correct.

**Do NOT merge. Do NOT push to main.** Open a PR against `main` and stop.

---

## Problem Frame

Trust collapses on first contact. Three concrete lies the UI tells today:

- **Placeholder provenance:** 12 community-modeled primitives carry
  `source.url: https://strata.internal/models/...` — a non-resolvable host
  presented as a citation.
- **Fake content pins:** 25 `demo-*` primitives carry
  `snapshot_sha256: d3d3d3d3…d3` (the all-`d3` sentinel) under a UI that claims
  "SHA-256 pinned · reproducible." On `/tam/<hash>/report` the SOURCES table
  prints `d3d3d3d3d3` on **every** row.
- **Doc rot:** the docs `CLAUDE.md` calls "load-bearing"
  (`00-vision`, `05-roadmap`, `07-data-layer`, `08-product-surface`, `10-…`)
  were deleted in `0e2787b` and survive only in git history.

The governing principle (project prime directive): **honesty over a fake green
check.** We never fabricate a URL or a snapshot to manufacture trust. The
schema forces this to be a *display* problem, not a *data-faking* problem:
`Source.url` is `Field(min_length=1)` (required, non-empty) and
`snapshot_sha256` is `Sha256Hex` (required, valid 64-hex) — so neither can be
nulled on the primitive. We fix the lie at the boundary where it is told.

---

## Key Technical Decisions

### KTD-1 — Never fabricate; fix the lie where it is rendered

The schema requires a non-empty `url` and a valid-hex `snapshot_sha256` on every
primitive. We do **not** invent values to satisfy that. Instead:

- **Modeled URLs** → replace `strata.internal` with the **genuine public anchor**
  each primitive's own `description`/`uncertainty.basis` already names (e.g. the
  GitHub Copilot / Cursor pricing pages the ACV model is anchored to). These are
  real, resolvable pages documenting the *basis* of a `community-modeled`
  figure — not a fabricated citation. The existing soft-data fence
  (`modeledInputNotes`, `InputUsed.source_url=None`, MODELED banner) already
  renders these honestly downstream.
- **Demo snapshots** → adopt the spec's sanctioned alternative: **stop
  presenting the `d3d3` sentinel as a real content pin.** A modeled value typed
  by hand was never content-pinned; manufacturing a sha256 of "bytes we fetched
  today" would fake a reproducibility we do not have — *more* dishonest than
  admitting it. So the demo YAML keeps its real regulator URLs and the `d3d3`
  sentinel, and the **UI** detects the sentinel and renders "sourced · not
  content-pinned (demo)" instead of a fake hash.

### KTD-2 — `github` stays unmapped (diverges from the spec's verify line)

The spec's PR 0 text says "add `github` … `/connectors` shows github=3." The
working tree already chose the **more honest** path: `github` primitives are
hand-authored analyst/community citations, **not** github-connector ingests;
listing "github · 3 primitives" in a *connector catalog* implies an ingest that
never happened — a provenance lie. We keep `github` unmapped (honest-zero) with
the explanatory comment, and map only `usda_nass` (a real ingest, 8 primitives).
**This divergence is called out in the PR body** so the reviewer sees the
honesty trade deliberately. `/connectors` verify target becomes: `usda_nass=8`,
`github` absent-by-design.

### KTD-3 — Featured concepts: deterministic + sourced-forward, never fake-sourced

`web/src/app/page.tsx` features `concepts.slice(0, 3)` — order-dependent and
likely surfacing AI concepts whose differentiating inputs are modeled. Replace
the blind slice with an explicit curated allowlist of 3 concepts chosen for the
**strongest sourced grounding** (highest regulator/aggregator input ratio in
their TAM). Where a featured concept's AI-specific inputs are inherently modeled
(the audit confirmed many have no sourced equivalent), we do **not** fake-source
them — they render with MODELED honesty. The goal is first-contact numbers that
lean on real sources, not a fabricated all-green.

### KTD-4 — Doc recovery is a faithful restore, not a rewrite

Restore `00-vision`, `05-roadmap`, `07-data-layer-brainstorm`,
`08-product-surface-brainstorm`, `10-v0.2-backend-spec` verbatim from
`0e2787b^` via `git show`. Do not paraphrase or "improve" — these are decision
records. `docs/architecture/` (ARCHITECTURE.md + charts-and-dashboards.md) and
`docs/questions/README.md` already exist untracked; include them as-is.

---

## Scope Boundaries

**In scope:** the 6 items in the Summary.

### Deferred to Follow-Up Work

- **`ResolveResultChart` hex → CSS-var tokenization** — PR 3 (chart system). A
  `TODO(PR3)` marker is already in place; leave it.
- **The untracked PR3-scope chart components** (`DonutChart`, `RadarChart`,
  `RadialChart`, `ChartGallery.stories.tsx`) and `web/scripts/` — **must NOT be
  staged in PR 0.** Leave them untracked.
- Real content-pinning of demo data (fetch+store snapshots) — not pursued;
  KTD-1 makes UI honesty the correct fix, not data manufacture.

### Out of scope

- Any backend auth / RLS / persistence work (that is PR 1).
- The full 28-diagram architecture set beyond what already exists untracked
  (the existing ARCHITECTURE.md carries the load-bearing subset; expanding to 28
  is not gating for PR 0's trust goal).

---

## Implementation Units

### U1. Replace the 12 `strata.internal` modeled-primitive URLs

**Goal:** No primitive cites the non-resolvable `strata.internal` host.

**Files:**
- `data/primitives/ai-coding-assistant-acv-per-engineer-2024.yaml`
- `data/primitives/ai-recruiting-agent-capture-rate-2024.yaml`
- `data/primitives/ai-brand-design-agent-capture-rate-2024.yaml`
- `data/primitives/ai-voice-survey-realistic-capture-rate-2024.yaml`
- `data/primitives/ai-native-tax-share-shift-capture-rate-2024.yaml`
- `data/primitives/ai-legal-assistant-acv-per-seat-2024.yaml`
- `data/primitives/playerzero-ai-debug-capture-rate-2024.yaml`
- `data/primitives/ai-canvas-capture-rate-of-stock-and-agency-production-2027.yaml`
- `data/primitives/multimodal-ai-infra-share-of-app-stack-2024.yaml`
- `data/primitives/numeral-realistic-share-shift-capture-2024.yaml`
- `data/primitives/ai-native-itsm-share-shift-rate-2024.yaml`
- `data/primitives/ai-native-cpa-firm-realistic-capture-rate-2024.yaml`

**Approach:** For each, read its `description` + `uncertainty.basis` and set
`source.url` to the genuine public anchor named there (pricing page, benchmark
report, regulator series the model is anchored to). Keep `tier:
community-modeled` and the existing methodology-text snapshot (that hash is over
the stated methodology — legitimate). If a row names no resolvable public
anchor, use the publisher's relevant index page — **never** invent a deep link,
never leave `strata.internal`. Verify each new URL resolves (HTTP 200/redirect)
where the sandbox allows; if a host is unreachable in-sandbox, pick a
known-stable canonical page and note it.

**Patterns to follow:** existing sourced primitives' `source` blocks; the
citation-allowlist hosts in `resolver/citations.py` (stay within allowed hosts).

**Test scenarios:**
- `grep -r "strata.internal" data/` returns zero matches.
- `uv run strata validate ../data` → 0 errors (URLs still valid, tier unchanged).
- Each modeled primitive still loads and still classifies as `community-modeled`
  (provenance class unchanged → soft-data fence still fires).
- Citation-allowlist test (`resolver/citations`) still passes for the new hosts.

**Verification:** no `strata.internal` anywhere in `data/`; validate green.

---

### U2. Render demo `d3d3` snapshots honestly in the UI

**Goal:** The `/tam/<hash>/report` SOURCES table (and any other snapshot display)
never presents the all-`d3` sentinel as a real content pin.

**Files:**
- `web/src/components/tam/TamReport.tsx` (provenance/sources rendering)
- the component that renders the provenance/sources table rows (locate the
  `ProvenanceTable` symbol imported by `TamReport`; likely under
  `web/src/components/` — confirm at implementation)
- `web/src/lib/format.ts` (add a small `isPlaceholderSnapshot` / `formatSnapshot`
  helper — single source of truth)
- test: `web/src/lib/__tests__/format.test.ts` (or the existing format test file)

**Approach:** Add a pure helper `isPlaceholderSnapshot(sha)` that detects the
all-`d3` sentinel (and any obviously-degenerate constant hash). Where a row's
snapshot is a placeholder, render "not content-pinned (demo)" (muted, not a fake
hash) instead of `d3d3d3d3d3`. The footer claim is already conditional on
`leansOnModeled`; extend that signal so demo-placeholder rows also flip it (the
report must not assert "snapshot-pinned" when any displayed row is unpinned).

**Patterns to follow:** the existing `leansOnModeled` conditional in
`TamReport.tsx`; `SourcedNumber` / `tierLabel` display helpers.

**Test scenarios:**
- `isPlaceholderSnapshot("d3".repeat(32))` → true; a real 64-hex → false; empty
  → true.
- A TAM whose inputs include a `d3d3` demo primitive renders "not
  content-pinned" text, **not** the literal `d3d3d3d3d3`, in the sources table.
- The footer renders the qualified (non-absolute) reproducibility sentence when
  any displayed row is a placeholder.
- A fully-sourced TAM (no placeholders, no modeled) still renders the absolute
  "Every sourced figure is snapshot-pinned" sentence.

**Verification:** `bunx tsc --noEmit && bunx biome check` clean; Playwright on
`/tam/<hash>/report` for a demo TAM shows no `d3d3d3d3d3` literal.

---

### U3. Make homepage featured concepts deterministic + sourced-forward

**Goal:** First-contact numbers lean on regulator/aggregator sources, not a
blind alphabetical slice.

**Files:**
- `web/src/app/page.tsx` (replace `concepts.slice(0, 3)`)
- (optional) `web/src/lib/featured.ts` for the curated allowlist constant
- test: co-located unit test for the selection helper if one is extracted

**Approach:** Replace `slice(0, 3)` with an explicit `FEATURED_CONCEPT_SLUGS`
allowlist (3 concepts with the strongest sourced grounding), filtered against the
live concept list with graceful fallback to the first available if an allowlisted
slug is missing. Determine the 3 by sourced-input ratio at implementation time
(inspect each concept's TAM inputs; prefer concepts whose apex/headline rests on
regulator/aggregator primitives). Do **not** fake-source modeled inputs — they
render MODELED. Keep the existing slug-correlation safety (find by slug, not
index).

**Patterns to follow:** existing `featuredSlugs` / `useQueries` block;
`buildQuery` / `tamRange`.

**Test scenarios:**
- Selection returns exactly the allowlisted slugs that exist in the concept list.
- Missing allowlisted slug falls back without crashing (graceful degrade).
- No console errors on `/` (Playwright); featured cards render real ranges with
  permalinks to `/tam/<hash>`.

**Verification:** `/` shows 3 featured TAMs whose headline numbers are
sourced-forward; no invented figures; tsc/biome clean.

---

### U4. Restore deleted ground-truth docs + finalize architecture/questions docs

**Goal:** The docs `CLAUDE.md` calls "load-bearing" exist again; architecture +
questions docs are tracked.

**Files (restore from `0e2787b^`):**
- `docs/00-vision.md`
- `docs/05-roadmap.md`
- `docs/07-data-layer-brainstorm.md`
- `docs/08-product-surface-brainstorm.md`
- `docs/10-v0.2-backend-spec.md`

**Files (already untracked — include as-is):**
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/charts-and-dashboards.md`
- `docs/questions/README.md`

**Approach:** `git show 0e2787b^:docs/<file> > docs/<file>` for each deleted doc
— a faithful restore, no edits (KTD-4). Stage the untracked architecture and
questions docs. Do not stage the PR3-scope chart components or `web/scripts/`.

**Test scenarios:** `Test expectation: none — documentation restore.` Confirm
each restored file is non-empty and byte-faithful to the git-history version
(`git show 0e2787b^:docs/07-data-layer-brainstorm.md | diff - docs/07-data-layer-brainstorm.md`).

**Verification:** all 5 docs present + tracked; architecture/questions docs
tracked; nothing PR3-scope staged.

---

### U5. Fix stale "load-bearing" doc references in CLAUDE.md / README

**Goal:** No doc points at a now-restored (previously dangling) path with stale
framing, and the architecture/questions docs are discoverable.

**Files:**
- `CLAUDE.md` (root) — the docs index / "load-bearing" references
- `README.md` (if it references the deleted docs)
- (the repo also has `docs/`-level references — fix any that name the restored files)

**Approach:** Re-point the "load-bearing" list to the restored files; add
`docs/architecture/` and `docs/questions/` to the docs index. Keep edits
minimal and factual.

**Test scenarios:** `Test expectation: none — docs.` Grep that no doc reference
points at a path that does not exist on disk.

**Verification:** referenced paths all resolve; docs index mentions
architecture + questions.

---

### U6. Final verification gate

**Goal:** All gates green before the PR opens.

**Approach / Verification (outcomes):**
- `cd backend && uv run pytest` → green.
- `cd backend && uv run pyright` → 0 errors.
- `cd backend && uv run ruff check . && uv run ruff format --check .` → clean.
- `cd backend && uv run strata validate ../data` → 0 errors.
- `cd backend && uv run strata verify-integrity ../data` → passes (no stored
  snapshot is claimed-but-mismatched; placeholder demo rows have no stored bytes
  so are not falsely verified).
- `cd web && bunx tsc --noEmit && bunx biome check` → clean.
- `/connectors` shows `usda_nass=8`; `github` absent-by-design (KTD-2).
- Playwright walkthrough: `/`, `/tam/<hash>/report` — no `strata.internal`, no
  `d3d3d3d3d3` literal, no console errors.

**Test scenarios:** `Test expectation: none — verification gate.`

---

## System-Wide Impact

- **Data layer:** 12 primitive `source.url` values change (tier/value/snapshot
  unchanged) — no schema change, no migration. Validation and the citation
  allowlist must stay green.
- **Frontend:** snapshot display becomes honesty-aware (new pure helper);
  featured-concept selection becomes deterministic. No API contract change.
- **Docs:** 5 files restored, 3 tracked, index references corrected.
- **Honesty fences:** strengthened, never weakened — the soft-data fence,
  citation allowlist, and Q20 no-LLM-number rule are all untouched or reinforced.

---

## Risks & Mitigations

- **A new modeled-source URL is unreachable in-sandbox** → pick a known-stable
  canonical publisher page; never revert to `strata.internal`; note any
  uncertain ones in the PR body. Mitigated by U1 verify step.
- **`ProvenanceTable` symbol location unknown** → locate by following the import
  in `TamReport.tsx` before editing (U2 file list flags this).
- **Featured-concept reseed surfaces a concept with mostly-modeled inputs** →
  acceptable and honest (MODELED renders); pick the *best available* sourced
  grounding, do not fabricate. Spec explicitly anticipates this.
- **`github` divergence from the spec's verify line** → deliberate (KTD-2),
  documented in the PR body so the reviewer ratifies the honesty trade.
