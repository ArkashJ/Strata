"""Persist auto-primitives to ``~/.strata/auto-primitives/`` (spec §8).

Step-3 connector hits are written here, NEVER to the committed
``data/primitives/`` tree. The ``strata promote`` CLI command is the
single path that moves an auto-primitive into the committed tree
(after the full validator pipeline runs).

Slugs are *human-meaningful* per audit fix I:
    {connector}-{semantic-stub}-{geo}-{period}
e.g. ``fdic-bank-count-us-2024``. Dedup hash lives in the YAML
metadata, not in the slug. Upsert is idempotent — running the same
connector+method+args twice produces a single file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter

from ..models import AtomicPrimitive

AUTO_PRIMITIVES_DIR: Path = Path.home() / ".strata" / "auto-primitives"


def _args_hash(connector: str, method: str, args: dict[str, Any]) -> str:
    payload = json.dumps({"connector": connector, "method": method, "args": args}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def upsert_primitive(
    *,
    primitive_yaml: dict[str, Any],
    connector: str,
    method: str,
    args: dict[str, Any],
    dir_override: Path | None = None,
) -> Path:
    """Validate the primitive shape, attach dedup metadata, write the YAML.

    Idempotent: same (connector, method, args) → same file on disk; we
    re-write the file even if it exists so the snapshot stays current
    when the underlying source changes.

    Raises ``ValueError`` if the dict does not validate against the
    AtomicPrimitive schema — connector bugs are caught at the writer
    boundary, not deep inside the registry loader.
    """

    # Schema validate via Pydantic at the writer chokepoint.
    TypeAdapter(AtomicPrimitive).validate_python(primitive_yaml)

    primitive_yaml = dict(primitive_yaml)
    metadata: dict[str, Any] = dict(primitive_yaml.get("metadata", {}) or {})
    metadata.setdefault("is_auto", True)
    metadata.setdefault("auto_connector", connector)
    metadata.setdefault("auto_method", method)
    metadata.setdefault("auto_args_hash", _args_hash(connector, method, args))
    primitive_yaml["metadata"] = metadata

    out_dir = dir_override if dir_override is not None else AUTO_PRIMITIVES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = primitive_yaml["slug"]
    path = out_dir / f"{slug}.yaml"
    path.write_text(yaml.safe_dump(primitive_yaml, sort_keys=False))
    return path
