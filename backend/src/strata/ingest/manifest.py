"""Parse the declarative ingest manifest (``data/ingest-manifest.yaml``).

WHY: the orchestrator stays connector-agnostic. The manifest is the only
place that names concrete ``(connector, method, arg-set)`` triples; the
orchestrator iterates :func:`connectors._capability.all_capabilities` and
only acts on pairs the manifest declares. An arg-set carries both the method
call arguments and the converter metadata — :func:`connectors._dispatch
.call_and_convert` splits them by signature, so the manifest does not need to
know the boundary.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml


@dataclasses.dataclass(frozen=True)
class ManifestMethod:
    """One method on a connector plus every arg-set to ingest through it."""

    method: str
    arg_sets: tuple[dict[str, Any], ...]


@dataclasses.dataclass(frozen=True)
class ManifestConnector:
    """A connector's ingest plan: optional credential gate + its methods."""

    connector: str
    requires_key: str | None
    methods: tuple[ManifestMethod, ...]


@dataclasses.dataclass(frozen=True)
class IngestManifest:
    connectors: tuple[ManifestConnector, ...]

    def get(self, connector: str) -> ManifestConnector | None:
        for c in self.connectors:
            if c.connector == connector:
                return c
        return None


# WHY a sibling of data/ and not inside it: the registry loader rglobs every
# YAML under data/ and rejects any file lacking a record `kind` (see commit
# 4e12777, which moved the portfolio YAML out for the same reason). Keeping the
# manifest beside data/ lets `strata validate ../data` stay green.
DEFAULT_MANIFEST_PATH: Path = Path("../ingest-manifest.yaml")


def load_manifest(path: Path | None = None) -> IngestManifest:
    """Read and validate the manifest YAML into typed records.

    Raises ``ValueError`` on a malformed manifest so the failure surfaces at
    the CLI boundary rather than deep inside a connector call.
    """
    target = path if path is not None else DEFAULT_MANIFEST_PATH
    raw = yaml.safe_load(target.read_text())
    if not isinstance(raw, dict) or "connectors" not in raw:
        raise ValueError(f"manifest {target} missing top-level 'connectors' key")

    connectors_raw = raw["connectors"]
    if not isinstance(connectors_raw, dict):
        raise ValueError("manifest 'connectors' must be a mapping")

    connectors: list[ManifestConnector] = []
    for name, body in connectors_raw.items():
        if not isinstance(body, dict):
            raise ValueError(f"connector {name!r} entry must be a mapping")
        methods_raw = body.get("methods", {})
        if not isinstance(methods_raw, dict):
            raise ValueError(f"connector {name!r} 'methods' must be a mapping")
        methods: list[ManifestMethod] = []
        for method, arg_sets in methods_raw.items():
            if not isinstance(arg_sets, list):
                raise ValueError(f"{name}.{method} arg-sets must be a list")
            for arg_set in arg_sets:
                if not isinstance(arg_set, dict):
                    raise ValueError(f"{name}.{method} each arg-set must be a mapping")
            methods.append(ManifestMethod(method=method, arg_sets=tuple(arg_sets)))
        connectors.append(
            ManifestConnector(
                connector=name,
                requires_key=body.get("requires_key"),
                methods=tuple(methods),
            )
        )
    return IngestManifest(connectors=tuple(connectors))
