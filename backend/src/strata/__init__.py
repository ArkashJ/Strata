"""Strata — open-source community-curated market-sizing tool.

Source of truth: docs/07-data-layer-brainstorm.md (data layer Q1-Q40),
docs/08-product-surface-brainstorm.md (product surface U1-U12),
docs/09-expert-layer-brainstorm.md (expert layer E1-E5).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("strata")
except PackageNotFoundError:  # editable install before metadata is written
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
