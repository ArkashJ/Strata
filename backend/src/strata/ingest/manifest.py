"""Declarative ingest manifest (``data/ingest-manifest.yaml``).

The manifest is the static counterpart to the LLM router: instead of asking
Claude which connector method to call, it lists them by hand. Each connector
maps to a list of methods; each method to a list of *arg-sets*. One arg-set is
a flat dict carrying **both** the connector method arguments (e.g. ``series_id``)
**and** the converter metadata (``primitive_slug``, ``concept_slug``, ``name``,
...). ``connectors._dispatch.call_and_convert`` splits the two by signature, so
the orchestrator stays oblivious to which keys go where.

Shape::

    connectors:
      bls:
        - method: get_series
          arg_sets:
            - series_id: CUUR0000SA0
              primitive_slug: bls-cpi-us-2024
              concept_slug: us-inflation
              name: ...
              ...

The flattened unit of work is one :class:`IngestTarget` per arg-set.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml


@dataclasses.dataclass(frozen=True)
class IngestTarget:
    """One connector call: a method plus the merged method-args + metadata."""

    connector: str
    method: str
    args: dict[str, Any]


def load_manifest(path: Path) -> list[IngestTarget]:
    """Parse the manifest YAML into a flat list of :class:`IngestTarget`.

    Raises ``FileNotFoundError`` if the file is missing and ``ValueError`` if
    the structure is malformed — the orchestrator should fail loudly on a bad
    manifest rather than silently ingesting nothing.
    """
    if not path.exists():
        raise FileNotFoundError(f"ingest manifest not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"manifest root must be a mapping, got {type(raw).__name__}")

    connectors = raw.get("connectors")
    if not isinstance(connectors, dict):
        raise ValueError("manifest must have a 'connectors' mapping")

    targets: list[IngestTarget] = []
    for connector, entries in connectors.items():
        if not isinstance(entries, list):
            raise ValueError(f"connector {connector!r} must map to a list of method entries")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"connector {connector!r} entry must be a mapping")
            method = entry.get("method")
            if not isinstance(method, str) or not method:
                raise ValueError(f"connector {connector!r} entry missing a 'method' string")
            arg_sets = entry.get("arg_sets", [])
            if not isinstance(arg_sets, list):
                raise ValueError(f"{connector}.{method} 'arg_sets' must be a list")
            for arg_set in arg_sets:
                if not isinstance(arg_set, dict):
                    raise ValueError(f"{connector}.{method} arg_set must be a mapping")
                targets.append(IngestTarget(connector=connector, method=method, args=dict(arg_set)))
    return targets
