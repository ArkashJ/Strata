"""One-shot, idempotent migration: move prediction-market primitives out of the
sizing-grade tree (Wave 0 / AC0.5).

Kalshi event-contract probabilities parse as ``atomic_primitive`` YAML but are
*signals*, not sourced measurements. They must never feed a framework or be
counted as a primitive. This script ``git mv``s every ``data/primitives/`` file
carrying ``tier: prediction_market`` into ``data/signals/``.

Run from the repo root::

    python backend/scripts/quarantine_signals.py            # apply
    python backend/scripts/quarantine_signals.py --dry-run  # preview

Idempotent: re-running after a move is a no-op (the files are already gone from
``data/primitives/``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_MARKER = "tier: prediction_market"


def _repo_root() -> Path:
    # backend/scripts/quarantine_signals.py -> repo root is parents[2].
    return Path(__file__).resolve().parents[2]


def find_signal_files(primitives_dir: Path) -> list[Path]:
    return sorted(
        p for p in primitives_dir.rglob("*.yaml") if _MARKER in p.read_text(encoding="utf-8")
    )


def _git_mv(src: Path, dst: Path, *, root: Path) -> None:
    subprocess.run(
        ["git", "mv", str(src.relative_to(root)), str(dst.relative_to(root))],
        cwd=root,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = _repo_root()
    primitives = root / "data" / "primitives"
    signals = root / "data" / "signals"
    signals.mkdir(parents=True, exist_ok=True)
    keep = signals / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")

    files = find_signal_files(primitives)
    if not files:
        print("Nothing to quarantine — data/primitives/ is already signal-free.")
        return 0

    print(f"Found {len(files)} prediction_market primitive(s) to quarantine:")
    for src in files:
        dst = signals / src.name
        print(f"  {src.relative_to(root)} -> {dst.relative_to(root)}")
        if not args.dry_run:
            _git_mv(src, dst, root=root)

    if args.dry_run:
        print("\n(dry run — nothing moved)")
    else:
        print(f"\nMoved {len(files)} file(s) into data/signals/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
