"""FastAPI app factory. Product-surface routes per docs/08 land at v0.3
alongside the graph renderer; v0.2 mounts liveness only.
"""

from __future__ import annotations

from strata.api.app import create_app

__all__ = ["create_app"]
