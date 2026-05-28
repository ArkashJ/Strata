"""Declarative ingest orchestrator package.

Drives the data bank from a static manifest (``data/ingest-manifest.yaml``)
through the existing connector → dispatch → writer machinery, the batch
counterpart to the per-query ``strata goal`` resolver.
"""

from __future__ import annotations

from .manifest import IngestTarget, load_manifest
from .orchestrator import (
    KEYLESS_CONNECTORS,
    IngestReport,
    StatusRow,
    ingest_status,
    refresh,
    run_ingest,
)

__all__ = [
    "KEYLESS_CONNECTORS",
    "IngestReport",
    "IngestTarget",
    "StatusRow",
    "ingest_status",
    "load_manifest",
    "refresh",
    "run_ingest",
]
