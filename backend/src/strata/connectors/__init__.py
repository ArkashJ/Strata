"""Data connectors for external APIs (BLS, FRED, EDGAR, Census, etc.).

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
from .census import (
    CensusClient,
    CensusClientError,
    CensusDataset,
    CensusGeoLevel,
    CensusNAICS,
    CensusResponse,
    FirmRecord,
    IndustryRecord,
    firm_to_primitive_yaml,
    firm_to_source_yaml,
    industry_to_primitive_yaml,
    industry_to_source_yaml,
)
from .edgar import (
    CompanyConcept as EDGARCompanyConcept,
)
from .edgar import (
    CompanyInfo as EDGARCompanyInfo,
)
from .edgar import (
    EDGARClient,
    EDGARClientError,
    EDGARFormType,
    EDGARPeriodType,
    EDGARResponse,
    EDGARTaxonomy,
    concept_to_primitive_yaml,
    concept_to_source_yaml,
    frame_to_primitive_yaml,
)
from .edgar import (
    Fact as EDGARFact,
)
from .edgar import (
    Filing as EDGARFiling,
)
from .edgar import (
    FrameEntry as EDGARFrameEntry,
)
from .fred import (
    Category as FREDCategory,
)
from .fred import (
    FREDClient,
    FREDClientError,
    FREDFrequency,
    FREDOrderBy,
    FREDResponse,
    FREDSearchType,
    FREDSortOrder,
    FREDUnits,
    Observation,
    Release,
    SeriesInfo,
    observations_to_primitive_yaml,
    observations_to_source_yaml,
)
from .kalshi import (
    Event as KalshiEvent,
)
from .kalshi import (
    KalshiClient,
    KalshiClientError,
    KalshiEventCategory,
    KalshiMarketResult,
    KalshiMarketStatus,
    KalshiResponse,
    market_to_primitive_yaml,
    market_to_source_yaml,
    market_volume_to_primitive_yaml,
)
from .kalshi import (
    Market as KalshiMarket,
)
from .kalshi import (
    Orderbook as KalshiOrderbook,
)
from .kalshi import (
    Trade as KalshiTrade,
)
from .worldbank import (
    Country as WBCountry,
)
from .worldbank import (
    IndicatorInfo as WBIndicatorInfo,
)
from .worldbank import (
    IndicatorValue as WBIndicatorValue,
)
from .worldbank import (
    WBIncomeLevel,
    WBIndicatorGroup,
    WBRegion,
    WBResponse,
    WorldBankClient,
    WorldBankClientError,
    indicator_to_primitive_yaml,
    indicator_to_source_yaml,
)

__all__ = [
    # BLS
    "BLSClient",
    "BLSClientError",
    "BLSPeriodKind",
    "BLSResponse",
    "BLSStatus",
    "BLSSurvey",
    "Catalog",
    # Census
    "CensusClient",
    "CensusClientError",
    "CensusDataset",
    "CensusGeoLevel",
    "CensusNAICS",
    "CensusResponse",
    "DataPoint",
    # EDGAR
    "EDGARClient",
    "EDGARClientError",
    "EDGARCompanyConcept",
    "EDGARCompanyInfo",
    "EDGARFact",
    "EDGARFiling",
    "EDGARFormType",
    "EDGARFrameEntry",
    "EDGARPeriodType",
    "EDGARResponse",
    "EDGARTaxonomy",
    # FRED
    "FREDCategory",
    "FREDClient",
    "FREDClientError",
    "FREDFrequency",
    "FREDOrderBy",
    "FREDResponse",
    "FREDSearchType",
    "FREDSortOrder",
    "FREDUnits",
    "FirmRecord",
    "Footnote",
    "IndustryRecord",
    # Kalshi
    "KalshiClient",
    "KalshiClientError",
    "KalshiEvent",
    "KalshiEventCategory",
    "KalshiMarket",
    "KalshiMarketResult",
    "KalshiMarketStatus",
    "KalshiOrderbook",
    "KalshiResponse",
    "KalshiTrade",
    "Observation",
    "Release",
    "Series",
    "SeriesInfo",
    "SurveyInfo",
    # World Bank
    "WBCountry",
    "WBIncomeLevel",
    "WBIndicatorGroup",
    "WBIndicatorInfo",
    "WBIndicatorValue",
    "WBRegion",
    "WBResponse",
    "WorldBankClient",
    "WorldBankClientError",
    "concept_to_primitive_yaml",
    "concept_to_source_yaml",
    "firm_to_primitive_yaml",
    "firm_to_source_yaml",
    "frame_to_primitive_yaml",
    "indicator_to_primitive_yaml",
    "indicator_to_source_yaml",
    "industry_to_primitive_yaml",
    "industry_to_source_yaml",
    "market_to_primitive_yaml",
    "market_to_source_yaml",
    "market_volume_to_primitive_yaml",
    "observations_to_primitive_yaml",
    "observations_to_source_yaml",
    "series_to_primitive_yaml",
    "series_to_source_yaml",
]
