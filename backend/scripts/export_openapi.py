"""Export the FastAPI app's OpenAPI spec to a committed JSON snapshot.

The live spec is always served at ``/openapi.json``, but a committed snapshot
lets the frontend regenerate its typed client (``web/src/lib/api-schema.d.ts``)
and lets CI diff the surface without booting the server.

Run from ``backend/``::

    uv run python scripts/export_openapi.py            # writes backend/openapi.json
    uv run python scripts/export_openapi.py --check     # exit 1 if the snapshot is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from strata.api.app import app

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export/check the OpenAPI snapshot.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the on-disk snapshot differs from the live spec",
    )
    args = parser.parse_args()

    spec = render()
    if args.check:
        if not args.out.exists() or args.out.read_text() != spec:
            print(f"OpenAPI snapshot is stale: {args.out}", file=sys.stderr)
            print("Regenerate with: uv run python scripts/export_openapi.py", file=sys.stderr)
            return 1
        print(f"OpenAPI snapshot up to date: {args.out}")
        return 0

    args.out.write_text(spec)
    paths = app.openapi().get("paths", {})
    print(f"Wrote {args.out} ({len(paths)} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
