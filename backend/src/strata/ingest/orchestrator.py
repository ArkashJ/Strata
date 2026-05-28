"""Connector-agnostic ingest orchestrator (Session 3 — ingest + freshness).

WHY: ingestion is driven by two declarative sources of truth — the capability
manifest (``connectors._capability.all_capabilities``, which says what each
connector *can* return and at what source tier) and the ingest manifest
(``ingest-manifest.yaml`` beside ``data/``, which says what we *want* ingested
and with which arguments). The orchestrator is the only thing that crosses
them; it holds no per-connector knowledge.

Flow::

    all_capabilities()  ─┐
                         ├─► for each (connector, method) the manifest declares:
    ingest-manifest.yaml ┘     - filter by --connector / --tier
                               - skip whole connector if its API key is unset
                               - per arg-set: call_and_convert → upsert_primitive
                               - de-dup by auto_args_hash; non-fatal per item

A missing API key skips the connector (logged, batch continues). Any other
failure (network, validation) is logged per arg-set and also non-fatal, so an
offline ``ingest run --tier regulator`` completes on the keyless connectors.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from ..connectors._capability import CapabilitySpec, all_capabilities
from ..connectors._dispatch import call_and_convert
from ..resolver.writer import AUTO_PRIMITIVES_DIR, upsert_primitive
from .manifest import IngestManifest, load_manifest

logger = logging.getLogger("strata.ingest")


def dedup_hash(connector: str, method: str, method_args: dict[str, Any]) -> str:
    """Stable dedup key for one ingest (connector + method + method args).

    WHY a local copy and not ``writer._args_hash``: the algorithm must stay
    byte-identical to the writer (sorted-key JSON → sha256[:16]) so two ingests
    of the same source collide, but reaching into the writer's private name
    couples the modules. The contract is the format, not the symbol.
    """
    payload = json.dumps(
        {"connector": connector, "method": method, "args": method_args}, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclasses.dataclass(frozen=True)
class IngestItemResult:
    connector: str
    method: str
    primitive_slug: str
    status: str  # "written" | "skipped" | "failed"
    detail: str = ""
    path: Path | None = None


@dataclasses.dataclass(frozen=True)
class IngestReport:
    results: tuple[IngestItemResult, ...]
    skipped_connectors: tuple[tuple[str, str], ...]  # (connector, reason)

    @property
    def written(self) -> int:
        return sum(1 for r in self.results if r.status == "written")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


def _capabilities_by_pair() -> dict[tuple[str, str], CapabilitySpec]:
    return {(s.connector, s.method): s for s in all_capabilities()}


def _key_present(requires_key: str | None) -> bool:
    """A connector is ingestable when it declares no key, or its key is set."""
    if not requires_key:
        return True
    return bool(os.environ.get(requires_key))


def _planned_items(
    manifest: IngestManifest,
    caps: dict[tuple[str, str], CapabilitySpec],
    connector_filter: str | None,
    tier_filter: str | None,
) -> tuple[list[tuple[str, str, dict[str, Any], CapabilitySpec]], list[tuple[str, str]]]:
    """Cross the two manifests into a flat work list, honoring the filters.

    Returns (items, skipped_connectors) where each item is
    ``(connector, method, arg_set, spec)`` and skipped_connectors is
    ``(connector, reason)`` for connectors dropped for a missing key.
    """
    items: list[tuple[str, str, dict[str, Any], CapabilitySpec]] = []
    skipped: list[tuple[str, str]] = []

    for mc in manifest.connectors:
        if connector_filter and mc.connector != connector_filter:
            continue
        if not _key_present(mc.requires_key):
            reason = f"missing API key {mc.requires_key}"
            logger.info("skipping connector %s — %s", mc.connector, reason)
            skipped.append((mc.connector, reason))
            continue
        for mm in mc.methods:
            spec = caps.get((mc.connector, mm.method))
            if spec is None:
                # WHY: a manifest entry with no capability spec is a typo or a
                # removed method; surface it but do not abort the batch.
                logger.warning(
                    "manifest %s.%s has no capability spec — skipping",
                    mc.connector,
                    mm.method,
                )
                continue
            if tier_filter and spec.source_tier != tier_filter:
                continue
            for arg_set in mm.arg_sets:
                items.append((mc.connector, mm.method, dict(arg_set), spec))

    return items, skipped


def method_only_args(connector: str, method: str, arg_set: dict[str, Any]) -> dict[str, Any]:
    """The subset of an arg-set that is a connector-method argument.

    Used for the dedup hash so the hash stays stable regardless of converter
    metadata edits (a renamed primitive must not look like a new ingest).
    """
    caps = _capabilities_by_pair()
    spec = caps.get((connector, method))
    if spec is None:
        return dict(arg_set)
    names = {a.name for a in spec.args}
    return {k: v for k, v in arg_set.items() if k in names}


def run_ingest(
    *,
    manifest_path: Path | None = None,
    connector_filter: str | None = None,
    tier_filter: str | None = None,
    out_dir: Path | None = None,
) -> IngestReport:
    """Execute the ingest plan and write auto-primitives to disk."""
    manifest = load_manifest(manifest_path)
    caps = _capabilities_by_pair()
    items, skipped = _planned_items(manifest, caps, connector_filter, tier_filter)

    results: list[IngestItemResult] = []
    for connector, method, arg_set, _spec in items:
        slug = str(arg_set.get("primitive_slug", "?"))
        method_args = method_only_args(connector, method, arg_set)
        try:
            primitive_yaml = call_and_convert(connector, method, arg_set)
            path = upsert_primitive(
                primitive_yaml=primitive_yaml,
                connector=connector,
                method=method,
                args=method_args,
                dir_override=out_dir,
            )
            logger.info("ingested %s.%s → %s", connector, method, slug)
            results.append(IngestItemResult(connector, method, slug, "written", path=path))
        # WHY broad: one bad source (network, validation) must not abort the batch.
        except Exception as exc:
            logger.warning("ingest %s.%s (%s) failed: %s", connector, method, slug, exc)
            results.append(IngestItemResult(connector, method, slug, "failed", detail=str(exc)))

    return IngestReport(results=tuple(results), skipped_connectors=tuple(skipped))


@dataclasses.dataclass(frozen=True)
class IngestStatusRow:
    slug: str
    connector: str
    method: str
    args_hash: str
    as_of: str


def ingest_status(out_dir: Path | None = None) -> list[IngestStatusRow]:
    """List every auto-primitive on disk with its ingest provenance."""
    target = out_dir if out_dir is not None else AUTO_PRIMITIVES_DIR
    rows: list[IngestStatusRow] = []
    if not target.exists():
        return rows
    for path in sorted(target.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        meta = raw.get("metadata", {}) or {}
        rows.append(
            IngestStatusRow(
                slug=str(raw.get("slug", path.stem)),
                connector=str(meta.get("auto_connector", "?")),
                method=str(meta.get("auto_method", "?")),
                args_hash=str(meta.get("auto_args_hash", "")),
                as_of=str(raw.get("as_of", "")),
            )
        )
    return rows


def _snapshot_of(primitive_yaml: dict[str, Any]) -> str:
    source = primitive_yaml.get("source", {}) or {}
    return str(source.get("snapshot_sha256", ""))


@dataclasses.dataclass(frozen=True)
class RefreshItemResult:
    connector: str
    method: str
    primitive_slug: str
    status: str  # "refreshed" | "unchanged" | "skipped" | "failed"
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class RefreshReport:
    results: tuple[RefreshItemResult, ...]

    @property
    def refreshed(self) -> int:
        return sum(1 for r in self.results if r.status == "refreshed")

    @property
    def unchanged(self) -> int:
        return sum(1 for r in self.results if r.status == "unchanged")


def refresh_ingest(
    *,
    manifest_path: Path | None = None,
    tier_filter: str | None = None,
    older_than_days: int | None = None,
    out_dir: Path | None = None,
) -> RefreshReport:
    """Re-fetch manifest primitives and rewrite ONLY when the snapshot changed.

    ``older_than_days`` limits the refresh to primitives whose on-disk
    ``as_of`` is older than the cutoff, so a daily refresh does not re-hit
    every source. A primitive whose freshly-computed ``snapshot_sha256``
    equals the stored one is left untouched (status ``unchanged``).
    """
    from datetime import date, timedelta

    manifest = load_manifest(manifest_path)
    caps = _capabilities_by_pair()
    items, _ = _planned_items(manifest, caps, None, tier_filter)
    target = out_dir if out_dir is not None else AUTO_PRIMITIVES_DIR

    cutoff: date | None = None
    if older_than_days is not None:
        cutoff = date.today() - timedelta(days=older_than_days)

    results: list[RefreshItemResult] = []
    for connector, method, arg_set, _spec in items:
        slug = str(arg_set.get("primitive_slug", "?"))
        existing_path = target / f"{slug}.yaml"

        existing_snapshot = ""
        if existing_path.exists():
            try:
                existing_raw = yaml.safe_load(existing_path.read_text())
            except yaml.YAMLError:
                existing_raw = None
            if isinstance(existing_raw, dict):
                existing_snapshot = _snapshot_of(existing_raw)
                if cutoff is not None:
                    as_of = _parse_date(str(existing_raw.get("as_of", "")))
                    if as_of is not None and as_of >= cutoff:
                        results.append(
                            RefreshItemResult(
                                connector, method, slug, "skipped", "newer than cutoff"
                            )
                        )
                        continue

        method_args = method_only_args(connector, method, arg_set)
        try:
            primitive_yaml = call_and_convert(connector, method, arg_set)
        # WHY broad: non-fatal, mirrors run_ingest — a dead source is skipped.
        except Exception as exc:
            logger.warning("refresh %s.%s (%s) failed: %s", connector, method, slug, exc)
            results.append(RefreshItemResult(connector, method, slug, "failed", str(exc)))
            continue

        new_snapshot = _snapshot_of(primitive_yaml)
        if existing_path.exists() and new_snapshot == existing_snapshot:
            results.append(RefreshItemResult(connector, method, slug, "unchanged"))
            continue

        upsert_primitive(
            primitive_yaml=primitive_yaml,
            connector=connector,
            method=method,
            args=method_args,
            dir_override=out_dir,
        )
        results.append(RefreshItemResult(connector, method, slug, "refreshed"))

    return RefreshReport(results=tuple(results))


def _parse_date(value: str) -> Any:
    from datetime import date

    parts = value.split("-")
    if len(parts) == 3:
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return None
