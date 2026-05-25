"""Data connectors for external APIs (BLS, FRED, EDGAR, etc.).

Each connector provides a typed client, disk caching, and converters
that emit Strata-compatible YAML dicts for AtomicPrimitive / Source records.
"""

from __future__ import annotations

from .bls import (
    BLSClient,
    BLSClientError,
    BLSPeriodKind,
    BLSResponse,
    BLSStatus,
    BLSSurvey,
    Catalog,
    DataPoint,
    Footnote,
    Series,
    SurveyInfo,
    series_to_primitive_yaml,
    series_to_source_yaml,
)

__all__ = [
    "BLSClient",
    "BLSClientError",
    "BLSPeriodKind",
    "BLSResponse",
    "BLSStatus",
    "BLSSurvey",
    "Catalog",
    "DataPoint",
    "Footnote",
    "Series",
    "SurveyInfo",
    "series_to_primitive_yaml",
    "series_to_source_yaml",
]
