# Plan — frontend restructure + the personal data bank

Status: **DRAFT for approval** (plan-first; no code changed yet).
Date: 2026-06-05. Owner: Arkash. Drafted with Claude.

---

## 1. Why

Two problems, one plan.

**Usability (urgent).** The sidebar shows **16 nav items** as flat equals (26
`page.tsx` files total, ~9 of which are detail/artifact/auth pages, not nav
destinations). The core job — *market query → pin scope → size → defensible TAM*
— drowns. Several surfaces overlap or are dead:

- "Pyramid explorer" (`/graph`) vs "Build a graph" (`/build/graph`) — two graph
  things, unclear which.
- Connectors (`/connectors`) vs Integrations (`/integrations`) — both read as
  "where data comes from".
- The "TAMs" nav counter is **hardcoded to `0`** (no list-promoted-TAMs endpoint
  yet); it points at `/browse`, which itself renders the full concept grid.
  `/data` is an orphan (not in nav); the `/build` workhorse isn't in the nav at all.

**Direction (the bigger why).** Strata becomes a **two-tier data bank synced
through agents**:

```
                     bidirectional sync (CLI / MCP, every call logged)
   USER'S CRM  ◄──────────────────────────────────────────────────►  STRATA BANK
   (their own private          ▲  pull: read shared sourced primitives    (generic, shared,
    primitive table,           │  push: sync their own primitives,         sourced — the
    builds, graphs,            │        builds, TAMs, macros               global table)
    TAMs, macros)              │
                              their agent does the work → logged →
                              graphs/TAMs/macros generated for them →
                              their research compounds; aggregate
                              improves the shared bank ("we improve from that")
```

Each person has **their own table**; there is **one generic Strata table**; the
agent (CLI/MCP) is the **bidirectional, logged** interface between them. The IA
must make that duality legible: *my data* vs *the shared bank*, with agents as
the sync engine.

The backend already has the bones: `AtomicPrimitive.visibility/org_id`,
org-scoped RLS (migration 003), the `companies` table + RLS (006), `audit_events`
(migration 002), the org-private contribution path, and 12 MCP tools (2 currently
write-capable: `import_portfolio`, `size_company`). The restructure productizes
what exists rather than inventing from zero.

---

## 2. Target information architecture

From the 16 flat items to **8 items in 4 labelled groups** — grouping, not just
deletion, is what makes it scannable. Connectors and Integrations stay separate
(confirmed); dead surfaces are pruned (confirmed).

```
WORK
  Home            /                 search entry + featured
  Build           /build            the workshop — graphs → TAMs + macros
                                    ("Build a graph" /build/graph folds in as a tab)
  Portfolio       /portfolio        size my portfolio

MY DATA                             ◄── the personal tier (the new direction)
  My Bank         /bank             my synced primitives (my CRM) + my saved
                                    builds, graphs, TAMs, macros  (absorbs Dashboard)
  Agents          /agents           CLI/MCP harness = the sync engine + activity log

STRATA BANK                         ◄── the shared/generic tier
  Explore         /explore          shared registry: concepts · primitives ·
                                    frameworks · signals · pyramid · browse TAMs
                                    (absorbs /c /p /f /signals /graph /browse /data as tabs)

SOURCES
  Connectors      /connectors       public typed connectors (kept separate)
  Integrations    /integrations     private OAuth SaaS (kept separate)
```

Footer / account menu (out of primary nav): **Guides** (help), **Contribute**,
**Search** (⌘K + top-bar box), theme, account/identity.

### Old → new route map (every move keeps a redirect; nothing 404s)

| Today | Becomes | Disposition |
|---|---|---|
| `/dashboard` | `/bank` | renamed + reframed as the personal bank |
| `/c` `/p` `/f` `/signals` | `/explore/{concepts,primitives,frameworks,signals}` | tabs under Explore; redirects kept |
| `/graph` (pyramid) | `/explore/pyramid` | tab under Explore |
| `/browse` (TAMs) | `/explore/tams` | folded in; replaces the hardcoded-0 TAMs nav counter |
| `/data` (orphan) | `/explore/primitives` (or pruned) | **prune** if unused; else fold in |
| `/build/graph` | `/build` (Graph tab) | folded into the workshop |
| `/c/[slug]` `/p/[slug]` `/f/[slug]` `/tam/[hash]` `/build/[hash]` | unchanged | detail/artifact routes stay; shared links survive |

---

## 3. Data model (the two-tier bank)

```
AtomicPrimitive.visibility ∈ { "public", "private" }   (exists — primitive.py)
              .org_id : str | None                      (exists, RLS-scoped)

STRATA BANK  = visibility="public"                   (the generic table, sourced)
MY BANK      = visibility="private", org_id=mine      (the personal table/CRM)

sync (CLI/MCP, bidirectional, logged):
  pull   shared public primitives into a build           (read)
  push   my primitives / builds / TAMs / macros          (write, org-scoped)
  log    every agent call → audit_events (who/what/when)  (exists; surface it)
  learn  org_private → (validator-gated) → public          (contribution path exists)
```

New concepts to add later (not Phase 1): a first-class **macro** record
(parameterized reusable recipe a user saves to their bank), and a **sync log**
view over `audit_events` on `/agents`.

---

## 3.5 Design methodology — three skills, composed (no overlap)

Execution is governed by three design skills with a clean division of labour by
surface, so they reinforce instead of fighting:

```
SURFACE                                     GOVERNED BY
───────                                     ──────────
app / product UI  (build · portfolio ·      impeccable  (product register — already this
 explore · bank · agents · sources · the      repo's contract via PRODUCT.md / DESIGN.md;
 sidebar shell, tables, forms, graph)         the taste-skill explicitly excludes dense
                                              product UI, §13, so impeccable owns these)
marketing / landing  (signed-out / ,        design-taste-frontend  (anti-slop discipline,
 about, /sign-in /sign-up night-canvas)       hero/IA/motion for the persuasion surfaces)
every existing surface, before any change   redesign-existing-projects  (Scan → Diagnose →
                                              Fix: work within the stack, no rewrites,
                                              fix-priority order, full state coverage)
```

Per-phase loop (every phase below runs this):

```
1. SCAN/DIAGNOSE  redesign-existing-projects audit of the surfaces in scope
2. BUILD          impeccable (product) or design-taste-frontend (marketing),
                  on the EXISTING stack (Next 16 · Tailwind v4 · Motion · Geist) — no rewrites
3. VERIFY         /impeccable critique + audit on the changed surface; headed Playwright;
                  tsc + biome clean; e2e updated
```

Hard constraints carried from all three: keep the existing stack (no framework
swap), AA contrast, reduced-motion honoured, the source-tier color contract
(Provenance-Color Rule) intact, no AI-slop tells, every interactive state
(loading/empty/error) present.

## 4. Execution — phased, plan-first, each phase its own PR

Frontend IA first (the urgent pain). Personal-bank/sync depth follows once the
shell is clean.

```
Phase 0  Shells + redirects        new /explore + /bank route shells; redirects
                                   for every moved path. No removals. Fully reversible.
Phase 1  Slim the Sidebar          16 → 8 items in 4 groups (WORK / MY DATA /
                                   STRATA BANK / SOURCES). Guides+Contribute → footer.
Phase 2  Explore hub               move /c /p /f /signals /graph /browse into
                                   /explore tabs; prune /data + the count-0 TAMs placeholder.
Phase 3  My Bank                   rename /dashboard → /bank; add the "my primitives"
                                   table (visibility=org_private) alongside saved builds.
Phase 4  Build consolidation       fold /build/graph into /build as a tab.
Phase 5  Agents = sync surface     /agents gains the activity/sync log over audit_events.
Phase 6  Verify                    re-run /impeccable critique on the new IA; fix fallout;
                                   update e2e specs + nav tests; CHANGELOG.

— deeper direction tracks (separate, after the shell is clean) —
Phase 7  MCP/CLI bidirectional push of primitives/builds/macros to My Bank.
Phase 8  Macro record + save-to-bank.
Phase 9  Aggregate learning (org_private → validator-gated → public).
```

Repo/monorepo + backend module restructure (the other boxes you checked) are
**deferred**: they don't serve the "make it usable" goal and add risk now. Tracked
as a later track once the IA + personal-bank land.

---

## 5. Risks & open decisions

- **My Bank vs Explore framing.** Two nav items (recommended — expresses the
  duality) vs one "Bank" entry with a Mine/Strata toggle. *Decision needed.*
- **Portfolio placement.** Top-level WORK (recommended, it's a headline wedge) vs
  nested under My Bank. *Decision needed.*
- **Redirect debt.** Keeping every old route as a redirect forever is clutter;
  propose a removal date (e.g. 1 release) for the redirect shims.
- **e2e churn.** ~10 specs reference old paths (`/c`, `/graph`, `/connectors`…);
  Phase 6 updates them. Expect a red suite mid-restructure until then.
- **Auth/CORS for local dev** (already hit this session): prod backend blocks
  `localhost`; document the local-backend workflow so contributors can run the UI.

---

## 6. What I need to start

Approve the IA shape (§2) and the two open decisions (§5). On green light I begin
**Phase 0** (shells + redirects — zero removals, fully reversible) and open it as
the first PR.
