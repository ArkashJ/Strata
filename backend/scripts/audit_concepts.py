"""One-off: audit every concept in the registry — does it build into a TAM?

Prints, per concept: PASS + tam value, or FAIL + the evaluator error. Surfaces
the "no applicable framework variants" data gap so we can remedy it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from strata.evaluator.engine import EvaluatorError, size_concept
from strata.loader import load_data_dir
from strata.registry import Registry


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../data")
    reg = Registry.from_loaded(load_data_dir(data_dir))
    slugs = sorted(reg.concepts)
    ok, bad = 0, 0
    print(f"# auditing {len(slugs)} concepts (data={data_dir})\n")
    for slug in slugs:
        try:
            out = size_concept(reg, slug)
            base = out.scenarios[0].value if out.scenarios else None
            n = len(out.scenarios)
            print(f"PASS  {slug:42s} scenarios={n} base={base}")
            ok += 1
        except EvaluatorError as exc:
            print(f"FAIL  {slug:42s} {exc}")
            bad += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERR   {slug:42s} {type(exc).__name__}: {exc}")
            bad += 1
    print(f"\n# {ok} pass / {bad} fail / {len(slugs)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
