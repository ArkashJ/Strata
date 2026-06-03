"""Declarative ingest orchestrator.

Threads a static manifest through the existing connector machinery:

    data/ingest-manifest.yaml          (per-connector methods + arg-sets)
            │  load_manifest
            ▼
    [IngestTarget(connector, method, args), ...]
            │  run_ingest — filter by tier/connector, skip keyless misses
            ▼
    connectors._dispatch.call_and_convert(connector, method, args)
            │  → validated AtomicPrimitive YAML dict
            ▼
    resolver.writer.upsert_primitive(..., args=args)   (de-dup by auto_args_hash)
            ▼
    ~/.strata/auto-primitives/{slug}.yaml

The orchestrator never touches the committed ``data/`` tree — writes land in
the auto-primitives staging dir, exactly like ``strata goal`` step 3. A
connector whose ``STRATA_<X>_API_KEY`` is absent is logged and skipped; the
batch keeps going. A single dispatch failure is recorded and skipped, never
aborting the run.

``call_and_convert`` and ``all_capabilities`` are injected (defaulted) so the
whole module is unit-testable offline without network or credentials.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from ..connectors._capability import CapabilitySpec, all_capabilities
from ..connectors._dispatch import call_and_convert
from ..resolver.writer import AUTO_PRIMITIVES_DIR, upsert_primitive
from .manifest import IngestTarget, load_manifest

_log = logging.getLogger(__name__)

Dispatch = Callable[[str, str, dict[str, Any]], dict[str, Any]]

# Connectors whose clients take no credential — absence of an env var must not
# skip them. Mirrors connectors._dispatch._CREDENTIALS coverage (the inverse).
KEYLESS_CONNECTORS: frozenset[str] = frozenset(
    {
        "edgar",
        "worldbank",
        "kalshi",
        "oecd",
        "eurostat",
        "faa",
        "yfinance",
        "stack_exchange",
        # These three have credential-free ctors (verified) but were being
        # skipped offline because they weren't listed — they need no API key.
        "cms",
        "fdic",
        "openfda",
    }
)


@dataclasses.dataclass(frozen=True)
class IngestReport:
    """Outcome counts for one ``run_ingest`` / ``refresh`` invocation."""

    written: int = 0
    failed: int = 0
    refreshed: int = 0
    unchanged: int = 0
    skipped_connectors: list[str] = dataclasses.field(default_factory=list[str])
    paths: list[Path] = dataclasses.field(default_factory=list[Path])


@dataclasses.dataclass(frozen=True)
class StatusRow:
    """One previously-ingested auto-primitive, read back from disk."""

    slug: str
    connector: str
    method: str
    auto_args_hash: str
    snapshot_sha256: str
    as_of: str
    path: Path


def _args_hash(connector: str, method: str, args: dict[str, Any]) -> str:
    """Dedup hash matching ``resolver.writer`` exactly so refresh can correlate
    a manifest target with the auto-primitive the writer previously emitted.
    """
    payload = json.dumps({"connector": connector, "method": method, "args": args}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _env_var(connector: str) -> str:
    return f"STRATA_{connector.upper()}_API_KEY"


def _tiers_by_connector(capabilities: Iterable[CapabilitySpec]) -> dict[str, str]:
    """connector → source_tier. A connector reports one tier across methods."""
    out: dict[str, str] = {}
    for spec in capabilities:
        out.setdefault(spec.connector, spec.source_tier)
    return out


def _has_credentials(connector: str, keyless: frozenset[str]) -> bool:
    if connector in keyless:
        return True
    return os.getenv(_env_var(connector)) is not None


def _eligible_targets(
    targets: list[IngestTarget],
    *,
    tier: str | None,
    connector: str | None,
    keyless: frozenset[str],
    tiers: dict[str, str],
) -> tuple[list[IngestTarget], list[str]]:
    """Apply tier/connector filters + the keyless/credential skip rule.

    Returns ``(runnable_targets, skipped_connector_names)``.
    """
    skipped: list[str] = []
    runnable: list[IngestTarget] = []
    seen_skip: set[str] = set()

    for t in targets:
        if connector is not None and t.connector != connector:
            continue
        if tier is not None and tiers.get(t.connector) != tier:
            continue
        if not _has_credentials(t.connector, keyless):
            if t.connector not in seen_skip:
                seen_skip.add(t.connector)
                skipped.append(t.connector)
                _log.warning(
                    "skipping connector %r: %s is not set", t.connector, _env_var(t.connector)
                )
            continue
        runnable.append(t)

    return runnable, skipped


def run_ingest(
    *,
    manifest_path: Path,
    dir_override: Path | None = None,
    tier: str | None = None,
    connector: str | None = None,
    capabilities: list[CapabilitySpec] | None = None,
    dispatch: Dispatch = call_and_convert,
    keyless_connectors: frozenset[str] | set[str] | None = None,
) -> IngestReport:
    """Run every manifest target (subject to filters) and persist the results.

    De-dup is handled inside ``upsert_primitive`` via ``metadata.auto_args_hash``
    keyed on ``(connector, method, args)`` — re-running the same target rewrites
    its one file rather than spawning duplicates.
    """
    caps = capabilities if capabilities is not None else all_capabilities()
    keyless = (
        frozenset(keyless_connectors) if keyless_connectors is not None else KEYLESS_CONNECTORS
    )
    tiers = _tiers_by_connector(caps)
    targets = load_manifest(manifest_path)

    runnable, skipped = _eligible_targets(
        targets, tier=tier, connector=connector, keyless=keyless, tiers=tiers
    )

    written = 0
    failed = 0
    paths: list[Path] = []
    for t in runnable:
        try:
            yaml_dict = dispatch(t.connector, t.method, t.args)
            path = upsert_primitive(
                primitive_yaml=yaml_dict,
                connector=t.connector,
                method=t.method,
                args=t.args,
                dir_override=dir_override,
            )
        except Exception:
            failed += 1
            _log.warning(
                "ingest failed for connector=%r method=%r", t.connector, t.method, exc_info=True
            )
            continue
        written += 1
        paths.append(path)

    return IngestReport(written=written, failed=failed, skipped_connectors=skipped, paths=paths)


def _read_auto_primitives(dir_override: Path | None) -> list[tuple[Path, dict[str, Any]]]:
    out_dir = dir_override if dir_override is not None else AUTO_PRIMITIVES_DIR
    if not out_dir.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(out_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            _log.warning("could not parse auto-primitive %s", path, exc_info=True)
            continue
        if isinstance(raw, dict):
            records.append((path, raw))
    return records


def ingest_status(*, dir_override: Path | None = None) -> list[StatusRow]:
    """Read back every auto-primitive on disk with its ingest metadata."""
    rows: list[StatusRow] = []
    for path, raw in _read_auto_primitives(dir_override):
        meta = raw.get("metadata", {}) or {}
        source = raw.get("source", {}) or {}
        rows.append(
            StatusRow(
                slug=str(raw.get("slug", path.stem)),
                connector=str(meta.get("auto_connector", "")),
                method=str(meta.get("auto_method", "")),
                auto_args_hash=str(meta.get("auto_args_hash", "")),
                snapshot_sha256=str(source.get("snapshot_sha256", "")),
                as_of=str(raw.get("as_of", "")),
                path=path,
            )
        )
    return rows


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def refresh(
    *,
    manifest_path: Path,
    dir_override: Path | None = None,
    tier: str | None = None,
    connector: str | None = None,
    older_than: int | None = None,
    capabilities: list[CapabilitySpec] | None = None,
    dispatch: Dispatch = call_and_convert,
    keyless_connectors: frozenset[str] | set[str] | None = None,
) -> IngestReport:
    """Re-fetch manifest targets and rewrite a primitive only when its
    ``snapshot_sha256`` changed.

    A target is considered for refresh only if it already exists on disk under
    the matching ``auto_args_hash``. ``older_than`` (days) skips primitives
    whose ``as_of`` is more recent than the cutoff, so a refresh sweep can
    target stale rows. Unknown/new targets are ignored (use ``run_ingest`` to
    seed them).
    """
    caps = capabilities if capabilities is not None else all_capabilities()
    keyless = (
        frozenset(keyless_connectors) if keyless_connectors is not None else KEYLESS_CONNECTORS
    )
    tiers = _tiers_by_connector(caps)
    targets = load_manifest(manifest_path)

    runnable, skipped = _eligible_targets(
        targets, tier=tier, connector=connector, keyless=keyless, tiers=tiers
    )

    existing = {row.auto_args_hash: row for row in ingest_status(dir_override=dir_override)}
    cutoff_date = (date.today() - timedelta(days=older_than)) if older_than is not None else None

    refreshed = 0
    unchanged = 0
    paths: list[Path] = []
    for t in runnable:
        prior = existing.get(_args_hash(t.connector, t.method, t.args))
        if prior is None:
            continue  # not yet seeded; refresh does not create new rows
        if cutoff_date is not None:
            as_of = _parse_iso_date(prior.as_of)
            if as_of is not None and as_of > cutoff_date:
                unchanged += 1
                continue
        try:
            yaml_dict = dispatch(t.connector, t.method, t.args)
        except Exception:
            _log.warning(
                "refresh fetch failed for connector=%r method=%r",
                t.connector,
                t.method,
                exc_info=True,
            )
            continue

        new_sha = str((yaml_dict.get("source", {}) or {}).get("snapshot_sha256", ""))
        if new_sha == prior.snapshot_sha256:
            unchanged += 1
            continue

        path = upsert_primitive(
            primitive_yaml=yaml_dict,
            connector=t.connector,
            method=t.method,
            args=t.args,
            dir_override=dir_override,
        )
        refreshed += 1
        paths.append(path)

    return IngestReport(
        refreshed=refreshed, unchanged=unchanged, skipped_connectors=skipped, paths=paths
    )
