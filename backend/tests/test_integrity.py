"""Wave 1 / AC1.3 — snapshot integrity is enforced.

A snapshot whose bytes don't hash to its declared sha256 raises IntegrityError;
the store walker reports per-file failures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.integrity import (
    IntegrityError,
    sha256_hex,
    verify_snapshot,
    verify_snapshot_store,
)


def test_matching_snapshot_passes() -> None:
    content = b"BLS OES 15-1252 employment = 1692100"
    verify_snapshot(content, sha256_hex(content))  # no raise


def test_tampered_snapshot_raises() -> None:
    content = b"original source bytes"
    expected = sha256_hex(content)
    with pytest.raises(IntegrityError):
        verify_snapshot(b"TAMPERED bytes", expected)


def test_snapshot_store_reports_failures(tmp_path: Path) -> None:
    good = b"good snapshot"
    (tmp_path / sha256_hex(good)).write_bytes(good)
    # A file named by a hash its bytes don't match = tampered.
    (tmp_path / sha256_hex(b"claimed")).write_bytes(b"actually different")

    report = verify_snapshot_store(tmp_path)
    assert report.verified == 1
    assert len(report.failures) == 1
    assert not report.ok


def test_missing_store_is_vacuously_ok(tmp_path: Path) -> None:
    report = verify_snapshot_store(tmp_path / "does-not-exist")
    assert report.ok
    assert report.verified == 0
