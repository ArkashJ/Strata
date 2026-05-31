"""Doc-count consistency check (Wave 4 / AC4.4).

Fails CI when the version is internally inconsistent — the single most common
release footgun. Checks:

  1. ``VERSION`` file == ``pyproject.toml`` version (HARD — they must agree).
  2. The latest git tag is not AHEAD of ``VERSION`` (a tag newer than the file
     means an un-bumped release; dev being ahead of the last tag is fine).

Run from repo root::

    python backend/scripts/check_doc_counts.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def version_file(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def pyproject_version(root: Path) -> str:
    text = (root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("could not find version in pyproject.toml")
    return m.group(1)


def _to_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3])


def latest_tag(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    tags = [t for t in out.splitlines() if t.startswith("v")]
    return tags[0] if tags else None


def check(root: Path) -> list[str]:
    problems: list[str] = []
    vf = version_file(root)
    pp = pyproject_version(root)
    if vf != pp:
        problems.append(f"VERSION ({vf}) != pyproject version ({pp})")

    tag = latest_tag(root)
    if tag is not None and _to_tuple(tag) > _to_tuple(vf):
        problems.append(f"latest tag {tag} is ahead of VERSION {vf} (un-bumped release?)")
    return problems


def main() -> int:
    root = _repo_root()
    problems = check(root)
    if problems:
        for p in problems:
            print(f"DOC-COUNT FAILURE: {p}", file=sys.stderr)
        return 1
    print(f"Doc counts consistent (VERSION == pyproject == {version_file(root)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
