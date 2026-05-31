# 23 — Feature Value Notes (PR #77)

> Business-value record for the `feat/signals-surface-and-tam-suite` work. Each
> feature was picked by a VC-vs-product / engineer-vs-user **feature tournament**
> (prelims → quarterfinals → semis → final), then built, reviewed adversarially,
> and verified live with the Playwright CLI. Companion to
> [`21-teardown-remediation.md`](21-teardown-remediation.md) (the plan) and
> [`22-handoff.md`](22-handoff.md) (the engineering state).

---

## The throughline

Strata sells a **defensible, reproducible, forwardable artifact** — not an answer.
Every feature below exists to make that claim survive a partner's scrutiny in the
first 60 seconds.

```
connectors → sourced primitives → frameworks → TAM ──┬─→ /tam/<hash>          (interactive, cross-check)
   (why each number is defensible)                    ├─→ /tam/<hash>/report   (forwardable one-page PDF)
                                                       └─→ downloadable charts  (drop into a deck)
 prediction_market signals ──quarantined──→ /signals   (live, walled off from TAM math)
```

---

## What shipped, and why it matters

| Feature | What a partner sees | Business value | Proof to a skeptic |
|---|---|---|---|
| **Convergence cross-check** (champion) | "bottoms-up $155M · top-down $470M · spread 3.0×" banner on the TAM | The triangulation a VC spends days assembling by hand, and the #1 reason they distrust a lone LLM number. Answers "why trust this." | Two independently-sourced method families, both shown; `null` when only one method exists (no fabricated agreement) |
| **Forwardable report** (`/tam/<hash>/report`) | A clean one-page PDF: headline, the math per method, what moves the answer, a sources table | The document a partner forwards to the fund. Turns a tool into a deliverable. | Every input row carries its tier + SHA-256 snapshot; honest footnotes for modeled/paraphrase inputs |
| **Connector explorer** (`/connectors`) | "5 connectors · 124 primitives" + the pipeline `API → primitive → framework → TAM` | Shows *why* the numbers are defensible — they trace to BLS/Census/FRED/EDGAR/World Bank, not a model. Onboards a buyer to the moat. | Live count per connector from the real bank; capability-only connectors shown as 0, no fabricated sample |
| **Signals surface** (`/signals`) | 202 live Kalshi market probabilities, read-only | A differentiator a general LLM can't give: live prediction-market signal next to a sized market. | Quarantined from all TAM math (Q20); registry-level disjointness test enforces it |
| **Downloadable graphs** | PNG / SVG on every result chart | The chart drops straight into a slide or memo — no screenshots. | Client-side only, theme-aware; honesty banners carry into exports |

---

## How the two recurring questions are answered

**"How do the connectors come into play?"**

```
22 typed connectors (BLS · FRED · Census · EDGAR · World Bank · Kalshi · OECD ·
Eurostat · Comtrade · FDIC · CMS · EIA · NASS · FAA · openFDA · …)
   │  typed client → disk cache → SHA-256 snapshot → YAML/DB converter
   ▼
Atomic primitive   (one source, one number, value + unit + source_url + sha256;
   │                 tier derived from the host class, never the LLM)
   ▼  consumed-by
Framework          (unit-crossing recipe; primitive slugs only, no scalar defaults)
   ▼  emits
TAM Output         (scenario tree at /tam/<hash>)
```

Connectors are the **ingest layer that manufactures sourced primitives**. They are
the reason every number is defensible. `/connectors` makes this visible: 5
connectors have produced 124 primitives in the current bank (census 38 · bls 27 ·
fred 22 · worldbank 21 · edgar 16); the other 17 are typed and wired but not yet
ingested (shown honestly as zero).

**"Can people make their own primitives and macros?"**

Partly today, and it is the next wedge:
- **Primitives** — the validator-gated contribution path exists in the backend
  (`POST /contribute`, `connectors/saas/` for OAuth-connected private data). A user
  can already bring a cited number; the **guided web form is the next build** (MV-tier
  in [`22-handoff.md`](22-handoff.md)). The hard rule: a contributed primitive needs
  a real `source_url` + tier + `snapshot_sha256`, defaults to `needs_review`, and
  never auto-promotes — faking "sourced" is the exact dishonesty we refuse.
- **Macros** — the live edit→recompute loop on `/build` already lets a user swap a
  primitive or set a what-if value and re-size in place; saving those as **named,
  reusable macros** is the natural follow-on. What-if values never persist as
  primitives (Q20) and carry a `user_override` banner.

---

## Verification (be skeptical — here is the evidence)

- **Backend:** `542 pytest passed`, `pyright src 0 errors`, `ruff check src` clean,
  `ruff format --check src` clean. (Run: `STRATA_OFFLINE=1 uv run pytest` from `backend/`.)
- **Web:** `bun run typecheck` clean. New components/pages pass `biome check`.
- **End-to-end (Playwright CLI, against a live stack):** all 13 new specs pass —
  signals (4), report + convergence (4), connectors (3), plus convergence API
  assertions. Each feature was also screenshot-verified in a real browser.
- **Known pre-existing e2e failures (NOT introduced here):** 20 specs in
  `landing/interpretation/resolve/tam/contribute/concept/framework/build` fail on
  stale copy/nav expectations, the missing LLM backend (resolve), and the absence
  of a persisted demo TAM (tam known-hash). Verified identical on a stashed
  (pre-change) tree — these are repo debt, tracked, not a regression.
- **Adversarial review:** each batch was reviewed by a code-reviewer subagent;
  every high-confidence finding was fixed (convergence unit-mismatch guard +
  honest position labels + deferred object-URL revoke; connector dead-host-map
  entry + deterministic sample).

---

## Brainstorm — next value, ranked (from the tournament + this session)

1. **User-authored primitive form** — the contribution wedge; backend endpoint
   exists, needs the guided web form (source + tier + snapshot required).
2. **Named macros** — save a what-if/override set on `/build` as a reusable,
   shareable macro; the "play with the assumptions" ask.
3. **Compare tray** — pit 2–4 TAMs/scenarios side by side.
4. **Signals → concept linkage** — surface related market signals on a concept/TAM
   page (read-only, never in math).
5. **Projected TAM** — forward a TAM by a user-set growth macro, behind a loud
   modeled-input banner (Q20 synthetic guard). Deferred until the banner is airtight.
6. **Niche value chain** (e.g. AI-inference compute) — **blocked on real external
   sourcing we must not fake**; earns the right to size a niche an analyst signs.
```
