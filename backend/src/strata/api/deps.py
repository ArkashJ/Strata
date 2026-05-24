"""Shared FastAPI dependencies — registry loader, evaluated on first request."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from strata.config import settings
from strata.loader import load_data_dir
from strata.registry import Registry


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    root = Path(settings.data_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[4] / root
    records = load_data_dir(root)
    return Registry.from_loaded(records)
