---
title: "Adding a field to a Postgres-backed Pydantic model: three traps that make it inert in prod"
date: 2026-06-07
type: [bug, architecture, conventions]
tags: [pydantic, postgres, alembic, migration, upsert, registry, validation, framework-taxonomy]
pr: feat/frameworks-taxonomy (#121)
status: active
---

# Adding a field to a Postgres-backed model — three traps

When a new field is added to a Pydantic model that is ALSO persisted in Postgres
(Strata's `Registry` loads from YAML in dev/CI but from `Registry.from_db()` in
prod), the field can pass every YAML/test check and still be **silently inert in
prod**. The framework-taxonomy PR (#121) added `Framework.parent_lens_shape` +
`realism_modifiers` and hit all three of the traps below; a code reviewer caught
trap 1 before merge.

```
YAML path (dev/CI):  data/*.yaml ─▶ load_data_dir ─▶ model_validate ─▶ Registry   ✅ field present
Prod path:           Postgres rows ─▶ Registry.from_db ─▶ model_validate ─▶ Registry
                                   ▲ if the column/sync/query layer is incomplete,
                                     the field defaults away here — field is INERT
```

## Trap 1 — the DB layer drops the field (the field is invisible in prod)

A new model field needs **four** edits to round-trip through Postgres, not one:

1. `db/models.py` — add the column to the SQLAlchemy row (`Mapped[...] =
   mapped_column(...)`).
2. `db/sync.py` — add the key to the **row-builder dict** (`sync_yaml_to_db`).
3. `db/sync.py` — add it to the **`on_conflict_do_update` `set_`** (the upsert).
4. `db/queries.py` — add it to the `raw` dict that `model_validate` reconstructs.
5. an Alembic migration adding the column.

Miss any of 1/2/4 and `Registry.from_db()` rebuilds every row with the field at
its **default** — so a taxonomy/flag/scope the model "has" is uniformly absent in
prod. The validator/gate then runs on wrong data, or the feature simply does
nothing. **It passes all YAML-only tests**, because those never touch Postgres.

**Guard:** write a DB round-trip test — seed YAML → `Registry.from_db()` → assert
the field survives — gated `skipif(not pg_reachable)` so CI (which has Postgres)
runs it (`backend/tests/test_framework_taxonomy_db.py`).

## Trap 2 — incomplete upsert `set_` strands columns on re-seed

`insert(...).on_conflict_do_update(set_={...})` only updates the columns named in
`set_`. If a new column is added everywhere EXCEPT the `set_`, the first seed
INSERTs it correctly, but every **re-seed** (the common case — `strata db seed` /
`STRATA_SEED_ON_BOOT` on each deploy) leaves the existing rows' column untouched
at its old/default value. The sync.py comment in this repo records a prior
incident where exactly this stranded `framework.variants` at `[]` and broke
`/build`. Add the column to BOTH the row dict and the `set_`.

## Trap 3 — local invariants belong on the model, not (only) the cross-record validator

A validator that only runs under `strata validate` does NOT protect a record
built from a stale Postgres row, an MCP path, or a unit test. Split the rules:

- **Local invariants** (relate only one record's own fields — e.g. "a canonical
  framework has no realism_modifiers; a subframework has ≥1") → a
  `@model_validator(mode="after")` on the model, so they fire at **every**
  construction (YAML, DB, MCP, test). Mirror the existing precedent
  (`Framework._formula_parses`).
- **Cross-record invariants** (need other records — e.g. "exactly one canonical
  per lens", "parent slug exists") → stay in the cross-record validator.

Putting a local invariant only in the cross-record layer leaves a drift window:
`Framework.model_copy(update=...)` **bypasses validation** in Pydantic v2, and a
hand-edited DB row reconstructs without the check. (Tests that want to exercise
the model validator must use `model_validate`, not `model_copy`.)

## Checklist when adding a field to a persisted model

- [ ] model field (with a backward-compatible default so old YAML/rows load)
- [ ] SQLAlchemy column in `db/models.py`
- [ ] row-builder dict in `db/sync.py`
- [ ] `on_conflict_do_update` `set_` in `db/sync.py`
- [ ] reconstruct dict in `db/queries.py`
- [ ] Alembic migration (nullable / server_default so existing rows are valid)
- [ ] DB round-trip test (`skipif(not pg_reachable)`)
- [ ] local invariants on a `@model_validator`, cross-record ones in the validator
- [ ] deploy note: `alembic upgrade head` + re-seed, else prod reads the default
