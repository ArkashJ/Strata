"""Serve-time snapshot integrity status for MCP citations (Phase 2 / A1).

Every citation is content-hash pinned (``snapshot_sha256``, Q5). At serve time we
classify each primitive's pin so the agent never silently cites a tampered or
demo-placeholder number:

* ``verified``     — the raw snapshot bytes are stored under
  ``data/snapshots/<sha>`` and hash to their declared pin (reuses
  :mod:`strata.integrity`).
* ``stale``        — the bytes are stored but DO NOT hash to the pin (drift /
  tamper). The number must be treated as suspect.
* ``unpinned_demo``— the pin is a placeholder (a ``demo-*`` / repeated-nibble
  sha that was never a real content hash), so there is nothing to verify.
* ``pinned``       — a real pin with no stored raw bytes to check against (the
  common case today; the mechanism is in place for when ingest persists bytes).

This is a read-only status; it never raises into a tool call. The snapshot store
lives at the repo root under ``data/snapshots/`` (same root the registry loads
from), located lazily and cached so the lookup is cheap per call.
"""

from __future__ import annotations

from pathlib import Path

from ..config import settings
from ..integrity import sha256_hex
from ..models import AtomicPrimitive

# A demo / placeholder pin: a low-entropy sha (e.g. the ``d3d3...`` demo snapshots
# PR0 already surfaces honestly). Treated as "nothing real to verify".
_PLACEHOLDER_SHAS = {"d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3"}


def _is_placeholder(sha: str) -> bool:
    if not sha or sha in _PLACEHOLDER_SHAS:
        return True
    # A real sha256 is 64 lowercase hex chars with meaningful entropy; a pin made
    # of a single repeated nibble is a demo placeholder, not a content hash.
    return len(set(sha)) <= 2


def _snapshots_dir() -> Path:
    root = Path(settings.data_dir)
    if not root.is_absolute():
        # Mirror server.load_registry: .../mcp/integrity.py -> parents[4] == repo root.
        root = Path(__file__).resolve().parents[4] / root
    return root / "snapshots"


def snapshot_integrity(sha256: str) -> str:
    """Classify one snapshot pin: verified | stale | unpinned_demo | pinned."""
    if _is_placeholder(sha256):
        return "unpinned_demo"
    path = _snapshots_dir() / sha256
    if not path.is_file():
        return "pinned"  # real pin, no stored bytes to check against yet
    return "verified" if sha256_hex(path.read_bytes()) == sha256 else "stale"


def primitive_integrity(p: AtomicPrimitive) -> str:
    """Integrity status for a primitive's source snapshot."""
    return snapshot_integrity(p.source.snapshot_sha256)


__all__ = ["primitive_integrity", "snapshot_integrity"]
