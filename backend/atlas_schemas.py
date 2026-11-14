"""Strict Pydantic v2 contracts for the four-element illustrated atlas artifacts.

All models inherit from ``ContractModel`` (``strict=True``, ``allow_inf_nan=False``,
``extra="allow"``) so non-finite floats, string-encoded numbers, boolean/int
confusions, and invalid percentage changes are rejected at server startup rather
than forwarded to clients.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import Field, StrictBool, model_validator

from backend.schemas import ContractModel

AtlasMonthStr = Field(pattern=r"^\d{4}-\d{2}$")
NonNegInt = Field(ge=0)


class BaselineSupportEntry(ContractModel):
    baseline_id: str
    label: str
    years: List[int] = Field(min_length=1)
    supported: StrictBool
    role: str
    status: str
    unsupported_reason: Optional[str] = None

    @model_validator(mode="after")
    def _unsupported_has_reason(self) -> "BaselineSupportEntry":
        if not self.supported and not self.unsupported_reason:
            raise ValueError("unsupported baseline entries require an explicit unsupported_reason")
        return self


class VariableDates(ContractModel):
    start: str = AtlasMonthStr
    end: str = AtlasMonthStr
    seasonal_window: str
    monthly_granularity: str
    n_years_available: int = Field(ge=1)


class VariableSpatialSupport(ContractModel):
    presentation_type: str
    resolution: str
    sampling_method: str
    supports_fine_heatmap: StrictBool
    supports_spatial_cells: StrictBool
    ukraine_region_ids: List[str]
    external_weather_region_ids: List[str]


class VariableUncertaintyStatus(ContractModel):
    claim_status: str
    is_interval_scale: StrictBool
    pct_change_allowed: StrictBool
    pct_change_withheld_reason: Optional[str] = None
    statistical_significance_assessed: StrictBool


class CatalogVariableContract(ContractModel):
    metric_id: str
    element_id: Literal["air", "fire", "land", "water"]
    element_label: Literal["Air", "Fire", "Earth", "Water"]
    label: str
    short_label: str
    units: str
    is_interval_scale: StrictBool
    is_primary_indicator: StrictBool
    display_order: int = Field(ge=1)
    dates: VariableDates
    supported_baselines: List[BaselineSupportEntry] = Field(min_length=1)
    spatial_support: VariableSpatialSupport
    method_id: str
    uncertainty_and_status: VariableUncertaintyStatus
    sources: List[str] = Field(min_length=1)
    limitations: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _fire_2015_2019_disabled(self) -> "CatalogVariableContract":
        if self.metric_id.startswith("fire_"):
            b15 = next((b for b in self.supported_baselines if b.baseline_id == "2015-2019"), None)
            if b15 is None or b15.supported or b15.status != "withheld_insufficient_baseline":
                raise ValueError("Fire metrics must keep 2015-2019 baseline disabled/withheld")
        return self


class GeoPolygonGeometry(ContractModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]


class GeoBoxFeature(ContractModel):
    type: Literal["Feature"]
    geometry: GeoPolygonGeometry
    properties: Dict[str, Any]


class GeoBoxCollection(ContractModel):
    type: Literal["FeatureCollection"]
    features: List[GeoBoxFeature] = Field(min_length=1)


class AtlasCatalogContract(ContractModel):
    schema_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    generated_at_utc: str
    case_id: str
    conflict_start: str
    metric_count: int = Field(ge=25, le=25)
    primary_indicators_by_element: Dict[str, str]
    variable_ids_by_element: Dict[str, List[str]]
    variables: List[CatalogVariableContract] = Field(min_length=25, max_length=25)
    study_regions: GeoBoxCollection
    global_limitations: List[str] = Field(min_length=1)


class MetricChangeContract(ContractModel):
    abs_diff: Optional[float]
    pct_change: Optional[float]
    pct_change_status: str

    @model_validator(mode="after")
    def _withheld_status_matches_null_pct(self) -> "MetricChangeContract":
        if self.pct_change_status.startswith("withheld_") and self.pct_change is not None:
            raise ValueError(f"withheld pct_change_status '{self.pct_change_status}' requires null pct_change")
        if self.pct_change_status == "computed" and self.pct_change is None:
            raise ValueError("computed pct_change_status requires non-null pct_change")
        return self


class BaselineWindowSummary(ContractModel):
    mean: Optional[float]
    min: Optional[float]
    max: Optional[float]
    sd: Optional[float]
    available_years: List[int]
    status: str


class PowerSeasonalSummary(ContractModel):
    window_label: str
    baseline_2015_2019: BaselineWindowSummary
    baseline_2019_2021: BaselineWindowSummary
    target_2022: Dict[str, Any]
    vs_2015_2019: MetricChangeContract
    vs_2019_2021: MetricChangeContract


class PowerMatchedMonth(ContractModel):
    calendar_month: int = Field(ge=3, le=8)
    month_name: str
    baseline_2015_2019: BaselineWindowSummary
    baseline_2019_2021: BaselineWindowSummary
    target_2022: Dict[str, Optional[float]]
    vs_2015_2019: MetricChangeContract
    vs_2019_2021: MetricChangeContract


class PowerMonthlyPoint(ContractModel):
    month: str = AtlasMonthStr
    year: int = Field(ge=2015, le=2025)
    calendar_month: int = Field(ge=1, le=12)
    value: Optional[float]
    anomaly_vs_2015_2019_month_mean: Optional[float]
    anomaly_vs_2019_2021_month_mean: Optional[float]


class PowerMetricBlock(ContractModel):
    metric_id: str
    units: str
    is_interval_scale: StrictBool
    seasonal_mar_aug: PowerSeasonalSummary
    matched_months: List[PowerMatchedMonth] = Field(min_length=6, max_length=6)
    monthly_series: List[PowerMonthlyPoint] = Field(min_length=1)

    @model_validator(mode="after")
    def _interval_withholds_pct(self) -> "PowerMetricBlock":
        if self.is_interval_scale:
            for cmp in (self.seasonal_mar_aug.vs_2015_2019, self.seasonal_mar_aug.vs_2019_2021):
                if cmp.pct_change is not None or cmp.pct_change_status != "withheld_interval_scale":
                    raise ValueError(f"{self.metric_id}: interval-scale metrics must withhold pct_change")
        return self


class PowerRegionPayload(ContractModel):
    region_id: str
    name: str
    role: str
    is_ukraine_study_area: StrictBool
    area_km2: float = Field(gt=0.0)
    center: Dict[str, float]
    bounds: List[List[float]]
    geometry: GeoBoxFeature
    spatial_audit: Dict[str, Any]
    metrics: Dict[str, PowerMetricBlock]


class PowerElementStudyContract(ContractModel):
    schema_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    generated_at_utc: str
    case_id: str
    element_id: Literal["water", "land", "air"]
    element_label: str
    study_id: str
    conflict_start: str
    primary_indicator: str
    available_variables: List[CatalogVariableContract] = Field(min_length=1)
    supported_baselines: List[BaselineSupportEntry] = Field(min_length=1)
    map: Dict[str, Any]
    highlights: Dict[str, Any]
    result: Dict[str, Any]
    limitations: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_regions(self) -> "PowerElementStudyContract":
        regions = self.result.get("regions")
        if not isinstance(regions, dict) or not regions:
            raise ValueError("result.regions must be a non-empty mapping")
        for region_id, region_obj in regions.items():
            PowerRegionPayload.model_validate(region_obj)
        return self


class FireAnnualPoint(ContractModel):
    rate_per_1k_km2_obs_day: Optional[float]
    detections: int = NonNegInt
    satellite_observed_days: int = NonNegInt
    legacy_rate_per_observed_day: Optional[float]
    unique_0_01deg_cell_days: int = NonNegInt
    frp_sum_mw: Optional[float]


class FirePrimarySeasonalMetric(ContractModel):
    method_id: str
    units: str
    annual: Dict[str, FireAnnualPoint]
    baseline_2019_2021_mean: Optional[float]
    target_2022: Optional[float]
    vs_2019_2021: MetricChangeContract
    vs_2015_2019: MetricChangeContract

    @model_validator(mode="after")
    def _withhold_2015_2019(self) -> "FirePrimarySeasonalMetric":
        if (
            self.vs_2015_2019.pct_change is not None
            or self.vs_2015_2019.pct_change_status != "withheld_insufficient_baseline"
        ):
            raise ValueError("Fire seasonal vs_2015_2019 must be strictly withheld")
        return self


class FireLegacySeasonalMetric(ContractModel):
    method_id: str
    legacy_only: StrictBool
    units: str
    baseline_2019_2021_mean_rate: Optional[float]
    target_2022_rate: Optional[float]
    vs_2019_2021: MetricChangeContract
    baseline_2019_2021_mean_detections: Optional[float]
    target_2022_detections: Optional[float]


class FireSeasonalFilterBlock(ContractModel):
    filter_mode: str
    label: str
    primary_metric: FirePrimarySeasonalMetric
    matched_dates_169d_ukr_adm0_sensitivity: Dict[str, Any]
    legacy_unnormalized_rate: FireLegacySeasonalMetric


class FireMonthlyPoint(ContractModel):
    month: str = AtlasMonthStr
    year: int = Field(ge=2019, le=2025)
    calendar_month: int = Field(ge=3, le=8)
    detections: int = NonNegInt
    satellite_observed_days: int = NonNegInt
    calendar_days: int = Field(ge=28, le=31)
    satellite_coverage_fraction: float = Field(ge=0.0, le=1.0)
    has_cmr_outage_gap: StrictBool
    rate_per_1k_km2_obs_day: Optional[float]
    legacy_detections_per_observed_day: Optional[float]
    unique_0_01deg_cell_days: int = NonNegInt
    day_detections: int = NonNegInt
    night_detections: int = NonNegInt
    frp_sum_mw: Optional[float]
    frp_median_mw: Optional[float]


class FireMatchedMonth(ContractModel):
    calendar_month: int = Field(ge=3, le=8)
    month_name: str
    baseline_2019_2021_mean: Optional[float]
    baseline_2019_2021_min: Optional[float]
    baseline_2019_2021_max: Optional[float]
    target_2022: Optional[float]
    vs_2019_2021: MetricChangeContract
    vs_2015_2019: MetricChangeContract


class FireSeasonalCell(ContractModel):
    cell_id: str
    lat: float
    lon: float
    in_ukr_adm0: StrictBool
    region_ids: List[str]
    type0_nh_2019_2021_mean: float
    type0_nh_2022: int = NonNegInt
    type0_nh_abs_diff: float
    type0_all_2019_2021_mean: float
    type0_all_2022: int = NonNegInt
    type0_all_abs_diff: float
    type2_all_2019_2021_mean: float
    type2_all_2022: int = NonNegInt
    frp_sum_mw_2022: float


class FireDrynessPoint(ContractModel):
    region_id: str
    role: str
    month: str = AtlasMonthStr
    year: int = Field(ge=2019, le=2025)
    calendar_month: int = Field(ge=3, le=8)
    is_2022_war_year: StrictBool
    in_cmr_outage_month: StrictBool
    fire_type0_per_1k_km2_day: Optional[float]
    vpd_kpa: Optional[float]
    pet_fao56_mm_day: Optional[float]
    prectotcorr: Optional[float]
    gwettop: Optional[float]
    t2m_max: Optional[float]


class FireRegionPayload(ContractModel):
    region_id: str
    name: str
    role: str
    area_km2: float = Field(gt=0.0)
    bounding_box: Dict[str, float]
    spatial_audit: Dict[str, Any]
    pre_2022_comparator_matches: List[Dict[str, Any]]
    seasonal_comparisons_mar_aug: Dict[str, FireSeasonalFilterBlock]
    matched_months_mar_aug: Dict[str, List[FireMatchedMonth]]
    monthly_series: Dict[str, List[FireMonthlyPoint]]


class FireStudyContract(ContractModel):
    schema_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    generated_at_utc: str
    case_id: str
    element_id: Literal["fire"]
    element_label: str
    study_id: str
    conflict_start: str
    primary_indicator: str
    cells_endpoint: str
    available_variables: List[CatalogVariableContract] = Field(min_length=1)
    supported_baselines: List[BaselineSupportEntry] = Field(min_length=1)
    normalization: Dict[str, Any]
    filters: Dict[str, Any]
    quality_flags: Dict[str, Any]
    map: Dict[str, Any]
    highlights: Dict[str, Any]
    result: Dict[str, Any]
    limitations: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_fire_result(self) -> "FireStudyContract":
        regions = self.result.get("regions")
        if not isinstance(regions, dict) or not regions:
            raise ValueError("fire result.regions must be non-empty")
        for reg_obj in regions.values():
            FireRegionPayload.model_validate(reg_obj)
        cells = self.result.get("seasonal_spatial_cells_025deg")
        if not isinstance(cells, list) or not cells:
            raise ValueError("fire result.seasonal_spatial_cells_025deg must be non-empty")
        for c in cells:
            FireSeasonalCell.model_validate(c)
        scatter = self.result.get("fire_dryness_scatter")
        if not isinstance(scatter, list) or not scatter:
            raise ValueError("fire result.fire_dryness_scatter must be non-empty")
        for s in scatter:
            FireDrynessPoint.model_validate(s)
        return self


class FireCellRegistryEntry(ContractModel):
    cell_id: str
    lat: float
    lon: float
    bounds: List[List[float]]
    in_ukr_adm0: StrictBool
    region_ids: List[str]


class FireMonthlyCellEntry(ContractModel):
    month: str = AtlasMonthStr
    year: int = Field(ge=2019, le=2025)
    calendar_month: int = Field(ge=3, le=8)
    cell_id: str
    lat: float
    lon: float
    type0_all_count: int = NonNegInt
    type0_nh_count: int = NonNegInt
    type2_all_count: int = NonNegInt
    type2_nh_count: int = NonNegInt
    type3_all_count: int = NonNegInt
    frp_sum_mw: float
    cmr_observed_days: int = NonNegInt
    in_cmr_outage_month: StrictBool
    in_ukr_adm0: StrictBool


class FireCellsContract(ContractModel):
    schema_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    case_id: str
    element_id: Literal["fire"]
    study_id: str
    grid_step_deg: float = Field(gt=0.0)
    season_window: str
    completeness_note: str
    cmr_month_coverage: List[Dict[str, Any]] = Field(min_length=1)
    cell_registry: List[FireCellRegistryEntry] = Field(min_length=1)
    monthly_cells: List[FireMonthlyCellEntry] = Field(min_length=1)
