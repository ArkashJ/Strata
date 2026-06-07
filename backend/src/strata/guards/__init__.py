"""Cross-cutting guards reused by multiple write doors (one fence, every door)."""

from __future__ import annotations

from .fence import (
    ModeledFenceError,
    validate_and_fence_primitive,
    validate_and_fence_shared_primitive,
)

__all__ = [
    "ModeledFenceError",
    "validate_and_fence_primitive",
    "validate_and_fence_shared_primitive",
]
