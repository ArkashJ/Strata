---
title: "PR 0 — Trust honesty fences: fix the lie at the boundary, never fake the data"
date: 2026-06-06
type: [architecture, conventions, bug, workflow]
tags: [provenance, soft-data-fence, snapshot, citations, connectors, docs-recovery, ci-scope]
pr: feat/pr0-trust-and-docs
status: active
---

# PR 0 — Trust honesty fences + doc/architecture recovery

Load-bearing learnings from the first of the 6 stacked v1.0 PRs
(`docs/TODO_june6.md`). The theme: **honesty over a fake green check** — when a
display tells a lie, fix it at the boundary where it is rendered, never by
manufacturing data to make the lie "true."

---

## 1. The schema forces honesty to be a *display* problem, not a *data* problem

`Source` (`backend/src/strata/models/source.py`) requires:

- `url: str = Field(min_length=1)` — **non-empty, mandatory**
- `snapshot_sha256: Sha256Hex` — **mandatory, valid 64-hex**

So you **cannot** null either field on a primitive to "remove" a bad citation.
This is deliberate (Q5 content-pinning). The consequence for the trust audit:

- The 25 `demo-*` primitives' fake `d3d3…d3` snapshot is a *valid-hex* string —
  it passes `strata validate`. The lie is not a schema violation; it is the UI
  presenting a placeholder **as if** it were a real pin.
- **Fix:** detect the placeholder at the render boundary
  (`web/src/lib/format.ts` → `isPlaceholderSnapshot` / `formatSnapshot`) and
  render "not pinned (demo)" instead of `d3d3d3d3d3`. The footer
  reproducibility claim (`TamReport.tsx`) flips to its qualified form whenever
  any displayed row is a placeholder. **Data unchanged; the lie is gone.**

**Why not manufacture a real snapshot?** A demo value was typed by hand and was
never content-pinned. Hashing "bytes we fetched today" would assert a
reproducibility we do not have — *more* dishonest than admitting the gap. The
honest move is to tell the truth in the UI, not to forge a green check.

## 2. A `community-modeled` source's URL *is* the documented model

12 modeled primitives cited the non-resolvable `https://strata.internal/...`.
Since `url` must be non-empty, you can't drop it — you must point it somewhere
**real**. The genuine "source" of a community model is the model definition
itself, in the open repo:

```
https://github.com/ArkashJ/Strata/blob/main/data/primitives/<slug>.yaml
```

This resolves (once pushed), fabricates no external authority, and matches the
**pre-existing convention** — other `community-modeled` primitives already cite a
repo doc. Apply it **uniformly to all 12** (no per-row special-casing): the
description still names each one's real-world anchor (Copilot pricing, SaaS
precedents) for the reader, and the URL ↔ snapshot stay internally consistent
(both refer to the model definition, which is what `community-modeled`'s
methodology-text snapshot hashes). An earlier draft pointed the coding-ACV row at
`github.com/features/copilot/plans`; code review flagged the inconsistency (and
that the snapshot doesn't hash that external page), so it was unified to the
repo-file link like the other 11.

The downstream soft-data fence is **tier-keyed, not URL-keyed**: changing the
URL does not weaken it. `community-modeled` still fires the MODELED banner and
still nulls `InputUsed.source_url` in the TAM display. Confirmed by
`tests/test_softdata_fence.py` staying green.

> **Latent bug found, not yet fixed:** the two existing `community-modeled`
> citations point at `github.com/anthropics/strata/...` (wrong org — the repo is
> `ArkashJ/Strata`) **and** at a methodology doc deleted in `0e2787b`. Both are
> broken links today. Out of PR 0's stated 12; flagged for a follow-up.

## 3. `github` stays an honest-zero connector (divergence from the spec, on purpose)

The spec's PR 0 text said "add a `github` host entry → `/connectors` shows
github=3." The working tree chose the **more honest** path and we kept it
(`backend/src/strata/api/routes/connectors.py:_CONNECTOR_HOSTS`):

- `usda_nass` **is** host-mapped — it is a real ingest; 8 primitives cite
  `nass.usda.gov`, so `/connectors` now shows `usda_nass = 8`.
- `github` is **deliberately not** mapped. The only primitives citing
  `github.com` are hand-authored analyst/community citations, **not**
  github-connector ingests. Mapping it would print "github · N primitives" in a
  *connector catalog* and imply an ingest that never happened — a provenance lie.
  `github` still appears in the catalog (it is a typed connector) with
  `primitives_in_bank = 0` (honest-zero, capability-only).

The `/connectors` `primitives_in_bank` count is **host-attribution**, not catalog
membership — a connector is listed regardless; the host-map only governs how many
sourced primitives are attributed to it.

## 4. Doc recovery: faithful restore from history, fix every dangling reference

`00/05/07/08/10` plus 13 more docs referenced by `CLAUDE.md`/`README.md` were
deleted in `0e2787b` and survive only in git history. Restore byte-faithfully:

```
git show 0e2787b^:docs/<file> > docs/<file>
```

Rather than delete references to real institutional knowledge, we **restored
every referenced-but-missing doc that exists in history** (18 files total),
making every `docs/*.md` reference in `CLAUDE.md`/`README.md` resolve. Zero
fabrication — they are real docs, just un-deleted. Added `docs/architecture/`
and `docs/questions/` to the CLAUDE.md docs index.

---

## Issues that showed up during execution (environment + process)

1. **The running `:8000` backend is a stale Docker container.** It serves the
   *committed* tree (baked image), not working-tree changes, and is unrelated to
   the frontend. Verifying working-tree data against it shows old results
   (`usda_nass=0`). **Fix:** run a local dev backend
   (`STRATA_ENV=dev uvicorn strata.api.app:app`) — in dev mode the registry is
   lazily loaded from working-tree YAML (`api/deps.py`, no DB needed for reads).

2. **The web dev server's `.env.local` points `NEXT_PUBLIC_API_URL` at the
   Railway prod backend**, not localhost. A browser smoke against the default
   dev server tests *prod* data. **Fix:** restart the dev server with
   `NEXT_PUBLIC_API_URL=http://localhost:<port>` pointed at a local working-tree
   backend before any meaningful live verification.

3. **CI gates the backend only.** `.github/workflows/ci.yml` has no web job — no
   `tsc`, `biome`, or `vitest`. The web checks are *local* quality bars. Bare
   `biome check` is already red on `main` (pre-existing format/organize debt in
   ~10 unmodified tracked files). The correct standard for a PR: **your changed
   files are clean; you do not fix unrelated pre-existing debt** (especially not
   files like `ResolveResultChart`/`PyramidOverlays` that are explicit PR 2/PR 3
   targets — touching them now causes stacked-PR merge conflicts).

4. **Lint/type scope is `src`, not the repo.** CI runs `ruff check src`,
   `ruff format --check src`, `pyright src`. `ruff check .` / `pyright` (whole
   repo) report pre-existing `scripts/`/`tests/`/`alembic/` debt that is **not**
   gated (documented in CLAUDE.md). Match the CI scope when judging green.

5. **`strata verify-integrity` takes `-d/--data-dir`, not a positional arg.** It
   verifies only *stored* snapshots; demo placeholders have no stored bytes, so
   it passes honestly ("Verified 0 snapshots") rather than falsely validating a
   `d3d3` pin.

6. **`Registry` has no `from_records`** — use `Registry.from_loaded(load_data_dir(path))`.

7. **fish word-splitting:** `refs=$(...)` + `for p in $refs` does **not**
   iterate per line under the tool's shell — the whole blob becomes one token.
   Use a Python one-liner for multi-file mechanical edits/restores instead of a
   shell loop over a command-substituted variable.

8. **Many ports were already occupied** (8000 Docker, 8001/8009 other services).
   Bind to port 0 to get a guaranteed-free port:
   `python -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1])"`.

---

## The reusable rule

When an audit finds a "fake source," ask first: *is the data wrong, or is the
display lying about the data?* The schema usually forces the latter. Fix the
boundary (a render helper + a tier-keyed fence), keep the data honest, and never
forge a citation or a hash to manufacture trust.
