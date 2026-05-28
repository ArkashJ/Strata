"""Connector-agnostic ingest + freshness orchestration (Session 3).

Public surface used by the ``strata ingest`` CLI sub-app and tests.
"""

from __future__ import annotations

from .manifest import (
    IngestManifest,
    ManifestConnector,
    ManifestMethod,
    load_manifest,
)
from .orchestrator import (
    IngestItemResult,
    IngestReport,
    IngestStatusRow,
    RefreshItemResult,
    RefreshReport,
    ingest_status,
    refresh_ingest,
    run_ingest,
)

__all__ = [
    "IngestItemResult",
    "IngestManifest",
    "IngestReport",
    "IngestStatusRow",
    "ManifestConnector",
    "ManifestMethod",
    "RefreshItemResult",
    "RefreshReport",
    "ingest_status",
    "load_manifest",
    "refresh_ingest",
    "run_ingest",
]
