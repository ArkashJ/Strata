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
from .cms import (
    CMSClient,
    CMSClientError,
    CMSDataset,
    CMSMetric,
    CMSResponse,
    CMSState,
    cms_to_source_yaml,
    enrollment_to_primitive_yaml,
    spending_to_primitive_yaml,
)
from .cms import (
    DrugSpendingRecord as CMSDrugSpendingRecord,
)
from .cms import (
    EnrollmentRecord as CMSEnrollmentRecord,
)
from .cms import (
    HospitalRecord as CMSHospitalRecord,
)
from .cms import (
    NationalHealthExpenditure as CMSNationalHealthExpenditure,
)
from .cms import (
    ProviderRecord as CMSProviderRecord,
)
from .cms import (
    SpendingRecord as CMSSpendingRecord,
)
from .comtrade import (
    ComtradeClient,
    ComtradeClientError,
    ComtradeFlowCode,
    ComtradeFrequency,
    ComtradeHSChapter,
    ComtradeReporter,
    ComtradeResponse,
    trade_to_primitive_yaml,
    trade_to_source_yaml,
)
from .comtrade import (
    TradePartnerSummary as ComtradePartnerSummary,
)
from .comtrade import (
    TradeRecord as ComtradeTradeRecord,
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
from .eia import (
    EIAClient,
    EIAClientError,
    EIADataPoint,
    EIAForecast,
    EIAFrequency,
    EIAResponse,
    EIARoute,
    EIASector,
    EIASeriesMetadata,
    EIAState,
    datapoint_to_primitive_yaml,
    datapoint_to_source_yaml,
)
from .eurostat import (
    EurostatClient,
    EurostatClientError,
    EurostatCountry,
    EurostatDataset,
    EurostatFrequency,
    EurostatResponse,
    observation_to_primitive_yaml,
    observation_to_source_yaml,
)
from .eurostat import (
    EurostatDatasetInfo as EurostatDatasetInfo,
)
from .eurostat import (
    EurostatObservation as EurostatObservation,
)
from .faa import (
    Airport as FAAairport,
)
from .faa import (
    AirportStatus as FAAAirportStatus,
)
from .faa import (
    AirportSummary as FAAAirportSummary,
)
from .faa import (
    FAAAirportType,
    FAAClient,
    FAAClientError,
    FAAOwnerType,
    FAARegion,
    FAAResponse,
    FAAState,
    airport_to_primitive_yaml,
    airport_to_source_yaml,
    passenger_count_to_primitive_yaml,
)
from .fdic import (
    BankSummary as FDICBankSummary,
)
from .fdic import (
    FailureRecord as FDICFailureRecord,
)
from .fdic import (
    FDICClient,
    FDICClientError,
    FDICFinancialField,
    FDICInstitutionField,
    FDICReportPeriod,
    FDICResponse,
    FDICSortOrder,
    FDICSpecialization,
    financial_to_primitive_yaml,
    financial_to_source_yaml,
    institution_count_to_primitive_yaml,
)
from .fdic import (
    FinancialRecord as FDICFinancialRecord,
)
from .fdic import (
    InstitutionRecord as FDICInstitutionRecord,
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
from .openfda import (
    CountResult as FDACountResult,
)
from .openfda import (
    Device510k as FDADevice510k,
)
from .openfda import (
    DeviceClassification as FDADeviceClassification,
)
from .openfda import (
    DevicePMA as FDADevicePMA,
)
from .openfda import (
    DrugEvent as FDADrugEvent,
)
from .openfda import (
    DrugLabel as FDADrugLabel,
)
from .openfda import (
    Enforcement as FDAEnforcement,
)
from .openfda import (
    FDADeviceClass,
    FDAEndpoint,
    FDARecallClass,
    FDARecallStatus,
    FDAResponse,
    OpenFDAClient,
    OpenFDAClientError,
    clearance_count_to_primitive_yaml,
    event_count_to_primitive_yaml,
    fda_to_source_yaml,
)
from .oecd import (
    OECDClient,
    OECDClientError,
    OECDCountry,
    OECDDataflow,
    OECDDataflowInfo,
    OECDFrequency,
    OECDObservation,
    OECDResponse,
    OECDSeriesInfo,
    oecd_observation_to_primitive_yaml,
    oecd_observation_to_source_yaml,
)
from .usda_nass import (
    NASSAggLevel,
    NASSClient,
    NASSClientError,
    NASSCommodity,
    NASSFrequency,
    NASSResponse,
    NASSSector,
    NASSSource,
    NASSStatistic,
)
from .usda_nass import (
    NASSParamValues as NASSParamValues,
)
from .usda_nass import (
    NASSRecord as NASSRecord,
)
from .usda_nass import (
    record_to_primitive_yaml as nass_record_to_primitive_yaml,
)
from .usda_nass import (
    record_to_source_yaml as nass_record_to_source_yaml,
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
    # CMS
    "CMSClient",
    "CMSClientError",
    "CMSDataset",
    "CMSDrugSpendingRecord",
    "CMSEnrollmentRecord",
    "CMSHospitalRecord",
    "CMSMetric",
    "CMSNationalHealthExpenditure",
    "CMSProviderRecord",
    "CMSResponse",
    "CMSSpendingRecord",
    "CMSState",
    "Catalog",
    # Census
    "CensusClient",
    "CensusClientError",
    "CensusDataset",
    "CensusGeoLevel",
    "CensusNAICS",
    "CensusResponse",
    # Comtrade
    "ComtradeClient",
    "ComtradeClientError",
    "ComtradeFlowCode",
    "ComtradeFrequency",
    "ComtradeHSChapter",
    "ComtradePartnerSummary",
    "ComtradeReporter",
    "ComtradeResponse",
    "ComtradeTradeRecord",
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
    # EIA
    "EIAClient",
    "EIAClientError",
    "EIADataPoint",
    "EIAForecast",
    "EIAFrequency",
    "EIAResponse",
    "EIARoute",
    "EIASector",
    "EIASeriesMetadata",
    "EIAState",
    # Eurostat
    "EurostatClient",
    "EurostatClientError",
    "EurostatCountry",
    "EurostatDataset",
    "EurostatDatasetInfo",
    "EurostatFrequency",
    "EurostatObservation",
    "EurostatResponse",
    # FAA
    "FAAAirportStatus",
    "FAAAirportSummary",
    "FAAAirportType",
    "FAAClient",
    "FAAClientError",
    "FAAOwnerType",
    "FAARegion",
    "FAAResponse",
    "FAAState",
    "FAAairport",
    # FDIC
    "FDICBankSummary",
    "FDICClient",
    "FDICClientError",
    "FDICFailureRecord",
    "FDICFinancialField",
    "FDICFinancialRecord",
    "FDICInstitutionField",
    "FDICInstitutionRecord",
    "FDICReportPeriod",
    "FDICResponse",
    "FDICSortOrder",
    "FDICSpecialization",
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
    # USDA NASS
    "NASSAggLevel",
    "NASSClient",
    "NASSClientError",
    "NASSCommodity",
    "NASSFrequency",
    "NASSParamValues",
    "NASSRecord",
    "NASSResponse",
    "NASSSector",
    "NASSSource",
    "NASSStatistic",
    # OECD
    "OECDClient",
    "OECDClientError",
    "OECDCountry",
    "OECDDataflow",
    "OECDDataflowInfo",
    "OECDFrequency",
    "OECDObservation",
    "OECDResponse",
    "OECDSeriesInfo",
    # openFDA
    "FDACountResult",
    "FDADevice510k",
    "FDADeviceClass",
    "FDADeviceClassification",
    "FDADevicePMA",
    "FDADrugEvent",
    "FDADrugLabel",
    "FDAEndpoint",
    "FDAEnforcement",
    "FDARecallClass",
    "FDARecallStatus",
    "FDAResponse",
    "OpenFDAClient",
    "OpenFDAClientError",
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
    "airport_to_primitive_yaml",
    "airport_to_source_yaml",
    "cms_to_source_yaml",
    "concept_to_primitive_yaml",
    "concept_to_source_yaml",
    "datapoint_to_primitive_yaml",
    "datapoint_to_source_yaml",
    "enrollment_to_primitive_yaml",
    "financial_to_primitive_yaml",
    "financial_to_source_yaml",
    "firm_to_primitive_yaml",
    "firm_to_source_yaml",
    "frame_to_primitive_yaml",
    "indicator_to_primitive_yaml",
    "indicator_to_source_yaml",
    "industry_to_primitive_yaml",
    "industry_to_source_yaml",
    "institution_count_to_primitive_yaml",
    "market_to_primitive_yaml",
    "market_to_source_yaml",
    "market_volume_to_primitive_yaml",
    "nass_record_to_primitive_yaml",
    "nass_record_to_source_yaml",
    "observation_to_primitive_yaml",
    "observation_to_source_yaml",
    "observations_to_primitive_yaml",
    "observations_to_source_yaml",
    "oecd_observation_to_primitive_yaml",
    "oecd_observation_to_source_yaml",
    "passenger_count_to_primitive_yaml",
    "series_to_primitive_yaml",
    "series_to_source_yaml",
    "spending_to_primitive_yaml",
    "trade_to_primitive_yaml",
    "trade_to_source_yaml",
    "clearance_count_to_primitive_yaml",
    "event_count_to_primitive_yaml",
    "fda_to_source_yaml",
]
