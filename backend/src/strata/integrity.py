"""Snapshot integrity verification (Wave 1 / AC1.3).

Every citation is content-hash pinned (`snapshot_sha256`, Q5). When the raw
source snapshot bytes are available, loading must verify
``sha256(snapshot_bytes) == snapshot_sha256`` and raise ``IntegrityError`` on a
mismatch — a tampered or drifted snapshot can never silently back a number.

Snapshots, when stored, live under ``data/snapshots/<sha256>`` (the file name IS
the expected hash). ``verify_snapshot_store`` walks that tree; with no snapshots
stored yet it passes vacuously and reports zero verified — the mechanism is in
place for when ingest starts persisting raw bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class IntegrityError(RuntimeError):
    """A stored snapshot's bytes do not hash to its declared ``snapshot_sha256``."""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def verify_snapshot(content: bytes, expected_sha256: str) -> None:
    """Raise ``IntegrityError`` if ``content`` does not hash to ``expected``."""
    actual = sha256_hex(content)
    if actual != expected_sha256:
        raise IntegrityError(
            f"snapshot integrity failure: expected {expected_sha256}, got {actual}"
        )


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    verified: int
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def verify_snapshot_store(snapshots_dir: Path) -> IntegrityReport:
    """Verify every ``data/snapshots/<sha256>`` file hashes to its filename.

    Returns a report; raises nothing (the CLI decides the exit code) so a caller
    can surface every failure at once.
    """
    if not snapshots_dir.exists():
        return IntegrityReport(verified=0, failures=())
    failures: list[str] = []
    verified = 0
    for path in sorted(snapshots_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        expected = path.stem  # filename without extension == the expected hash
        actual = sha256_hex(path.read_bytes())
        if actual != expected:
            failures.append(f"{path.name}: expected {expected}, got {actual}")
        else:
            verified += 1
    return IntegrityReport(verified=verified, failures=tuple(failures))
