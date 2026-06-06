# Strata — Expert Layer Brainstorm (partial)

> Locks the **schema shape** of the expert layer (Layer 3 in
> [`01-primer.md`](01-primer.md#layer-3--expert-layer)).
> Most operational mechanics (credentialing process, reputation algorithm,
> moderation pipeline, adversarial defenses) are **deliberately deferred**
> to v0.5, when real contributor data is available to calibrate them.

## Status

**Phase:** Expert-layer brainstorm **PARTIAL — schema locked, ops deferred.**
**Builds on:** [`docs/07-data-layer-brainstorm.md`](07-data-layer-brainstorm.md) (data layer Q1–Q38),
[`docs/08-product-surface-brainstorm.md`](08-product-surface-brainstorm.md) (product surface U1–U12),
[`docs/01-primer.md`](01-primer.md) (three-layer overview).

---

## TL;DR — decisions table

| #  | Question                              | Decision                                                                                                                                                                                                                                                       |
| -- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1 | What does an annotation *do*?         | **Pure commentary.** Text-only prose attached to an annotated item. The math layer **never** auto-applies an annotation. Sarah reads it and manually tweaks her build if she chooses to. Eliminates the COI-poisons-the-math risk before it begins.            |
| E2 | Expertise model?                      | **Three flat tiers** (per [`01-primer.md`](01-primer.md#layer-3--expert-layer)): `verified-expert` · `active-practitioner` · `community`. Single badge per contributor; same badge on every annotation they make, regardless of domain. Cross-domain over-credit accepted as known limitation. |
| E3 | Annotation record fields?             | **Minimal core + kind tag + COI field.** `target_slug` · `target_type` · `author` · `created_at` · `body` (markdown) · `kind` (informational enum) · `coi_disclosure` (optional text). No citations field (use markdown links in body), no supersedes, no expiry. |
| E4 | Annotation lifecycle?                 | **Append-only, no auto-stale.** New annotations on the same item stack; older annotations remain visible. No expiry, no supersedes link. Readers sort/judge. Editing TBD at v0.5.                                                                              |
| E5 | Tier-gating, reputation, moderation?  | **All operational mechanics deferred to v0.5.** Verification path for `verified-expert`, contributor-weight algorithm, moderation pipeline (pre vs post vs LLM-screened), and adversarial defenses all need real contributor data to calibrate. Bootstrap: Strata maintainers manually vet annotations until volume forces a pipeline. |

---

## Context

The data-layer brainstorm and the product-surface brainstorm both reference
the expert layer but punt the mechanics — for good reason. Reputation
algorithms calibrated without real contributors devolve into bikeshed; COI
disclosure rules calibrated against hypothetical contributors miss the actual
COI patterns that will emerge. This document captures the **structural
decisions** that need to be made now (so v0.2 schemas and v0.3 UX don't
foreclose options) and **explicitly defers everything else**.

The result is a thin expert layer for v0.3–v0.4 (annotations exist, they
display per `08-product-surface-brainstorm.md` §U8 with red dots, badges
display per the three tiers) and a much fuller expert layer at v0.5 when
mechanics are designed against real submission volume.

---

## Decision rationale

### E1 — Pure commentary

Calibration-style annotations ("apply ×1.25") are powerful: one click can
change a TAM. They are also the single largest attack surface in the expert
layer — a P&C exec with quietly-bad incentives can poison every P&C TAM
that uses their primitive. Pure-commentary annotations eliminate this risk
entirely. The cost is the loss of the "Sarah clicks to apply the captive-
carrier adjustment" affordance from `04-user-journey.md` — but that
affordance is replaced by Sarah *reading* the annotation and choosing to
tweak the framework's slider herself, which keeps the user in the
math-loop.

**Implication for `04-user-journey.md`:** the line _"Sarah applies the
adjustment. New range: \$11M – \$88M"_ should be revised: she reads the
annotation, decides to apply a 0.78 adjustment, drags the
`pct_addressable_by_doc_gen` slider down, and the range updates. The
annotation never reaches into the math.

### E2 — Three flat tiers

Per-domain weight (P&C: high, healthcare: low) is more honest but requires
calibration against real annotation history that doesn't exist pre-launch.
A single reputation scalar conflates domains and creates Matthew-effect
problems. No-tier-just-bio loses the ability to sort. Three flat tiers
match the existing docs, ship cheap, and are easy to upgrade later (the
tier can become an input to a future per-domain algorithm).

### E3 — Minimal + kind + COI

`citations` as a structured field was rejected — markdown links in the
`body` cover the same ground without a new schema. `supersedes` and
`expiry` were rejected because pure-commentary annotations don't break math
when stale, so the cost-benefit didn't justify the complexity. `kind` was
accepted because UI filtering benefits from it even when it carries no math
effect. `coi_disclosure` was accepted because trust signals matter even for
prose.

### E4 — Append-only

Consequence of E1 + E3: no math effect, no expiry → annotations are an
append-only audit log of context. Older annotations remain visible because
they remain potentially-useful context (and because removing them is a
moderation question, deferred per E5). Editing — whether authors can amend
their own annotations and whether edits appear as new annotations or
in-place modifications — is open.

### E5 — Defer ops to v0.5

The verification path for `verified-expert`, the weight/sort algorithm,
moderation pipeline (LLM-screened vs human-queued vs post-moderated),
adversarial defenses (sybils, brigading, paid astroturf), and contributor
profile/bio shape are all calibration problems. Designing them
pre-contributor is bikeshed. The bootstrap is intentionally manual: Strata
maintainers eyeball every annotation until submission volume forces a real
pipeline.

---

## Annotation record (canonical YAML shape)

```yaml
kind: annotation
slug: <auto-generated content-hash>
schema_version: 1

target_slug: <slug being annotated>           # E3 — required
target_type: concept | primitive | composite_primitive
           | framework | pyramid_node
           | scenario | tam_output | source   # E3 — required
author: <contributor_slug>                    # E3 — required
created_at: <ISO datetime>                    # E3 — required
body: <markdown>                              # E3 — required

kind_tag: correction                          # E3 — informational
        | blindspot
        | methodology_note
        | scope_warning
        | alt_framing
        | other

coi_disclosure: ~ | <free text>               # E3 — optional
```

Contributor tier is **not** stored on the annotation; it's a property of
the `author` resolved at display time (current tier shown, not historical).

---

## Open threads (deferred to v0.5)

- **Verification path for `verified-expert`** — LinkedIn + bio + manual review, web-of-trust vouching, hybrid, or stake-based. Decide with real demand-signal from would-be experts.
- **Bootstrap seed set** — how Strata maintainers identify and onboard the first ~20–50 verified experts at launch.
- **Reputation / weight algorithm** — how the red-dot annotation sort-order is computed beyond tier. Per Bayesian-update on acceptance history, vouching, endorsements, age. Depends on tier-gating first.
- **COI disclosure: required vs optional rule** — likely required for `verified-expert` annotations, optional below. Locks once tier-gating mechanics land.
- **Moderation pipeline** — pre-moderation queue vs LLM-screened-with-spot-check vs post-moderation-with-flagging. Choice depends on actual submission rate; default for v0.5 launch is whatever ships with the lowest false-positive rate against the first month of submissions.
- **Adversarial defenses** — sybil-attack prevention (one person, many accounts), coordinated brigading, paid astroturf, expert-impersonation. Need a real attack to design against; placeholder: rate limit + LinkedIn binding.
- **Contributor profile page shape** — name, bio, tier badge, annotation history, vouching record, endorsements. Likely `/u/<slug>` route.
- **Edit / delete / version history on annotations** — can authors amend their own? Do edits show as new annotations with `supersedes` (reversing E4 partially) or in-place? Defer.
- **Bounties / paid contributions** — direct payment to experts for valuable annotations. Post-v1.0 commercial question.
- **Contributor incentives** — what motivates the verified-expert tier to participate at all. Reputation, portfolio, self-promotion, altruism, paid bounty. Should be modeled with a few candidate personas before v0.5.

---

## What this brainstorm did NOT cover

- **Governance** — who selects Strata maintainers, how conflicts among
  maintainers are resolved, foundation vs company-backed model. Separate
  brainstorm topic.
- **Specific seed experts** — who the founding 20–50 verified experts
  actually are. Recruitment question, not schema.
- **Legal / liability** — defamation risk in annotations, takedown process.
  Legal review before v0.5 ship.

---

## Verification plan

The expert-layer schema is correct if these flows work without contortions:

1. **Annotation create:** Sarah reads `n_pc_carriers_us` on a primitive page → notices a `[ + Add annotation ]` button → opens the inline web form → picks `kind_tag: correction` → writes markdown body → optionally fills `coi_disclosure` → submits → goes into manual-review queue (v0.5 stub).

2. **Annotation display (per U8):** On the primitive page, a red dot appears next to the annotated field. Hover shows the top-displayed annotation snippet (sort rules deferred). Click expands all annotations on that primitive, each showing author + tier badge + kind_tag chip + COI disclosure (if any) + markdown body.

3. **Cross-domain over-credit (known limitation):** A verified-expert in P&C insurance writes an annotation on a healthcare TAM. The badge still says `verified-expert`. Sarah is expected to read the author bio and judge relevance. v0.5 may add a per-domain weight if this becomes a real problem.

4. **Append-only:** Author A writes an annotation in 2026; the world changes; Author B writes a contradicting annotation in 2028. Both annotations remain visible. The display sort (deferred) determines which surfaces first.

---

## Build sequence (mapped to roadmap)

| Roadmap                    | This brainstorm delivers                                                                                                                                                                                                                |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v0.2 — Seed library        | Annotation YAML schema (E3). Contributor record (slug, name, bio, tier). Three tier enums (E2).                                                                                                                                          |
| v0.3 — Graph renderer      | Annotation display per `08-product-surface-brainstorm.md` §U8 — red dots, hover preview, inline expand. Author bio + tier badge inline. COI disclosure shown verbatim.                                                                   |
| v0.4 — Calculator + export | Annotations carry into exported TAM artifact (PDF / markdown) as footnotes attached to the items they annotate.                                                                                                                          |
| v0.5 — Contribution flow   | **All deferred mechanics land here:** verification path, reputation algorithm, moderation pipeline, COI required-vs-optional rule, contributor profile pages, edit / delete / version-history, adversarial defenses, bootstrap seed set. |
