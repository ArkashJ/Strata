"""Content-hash utilities (Q5, Q38).

A TAM URL is a sha256 over a canonicalized build state. Same state → same hash.
Reordered keys → same hash. One field change → different hash.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_dumps(payload: Any) -> str:
    """Stable JSON serialization for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mint_state_hash(payload: dict[str, Any]) -> str:
    """sha256 of a canonicalized build-state mapping."""
    return sha256_hex(canonical_dumps(payload))
