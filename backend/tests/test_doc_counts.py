"""Wave 4 / AC4.4 — VERSION and pyproject agree (release consistency)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "backend" / "scripts"))

from check_doc_counts import check, pyproject_version, version_file  # noqa: E402


def test_version_matches_pyproject() -> None:
    assert version_file(_REPO) == pyproject_version(_REPO)


def test_docs_counts_match() -> None:
    assert check(_REPO) == []
