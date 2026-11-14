"""Pydantic models.

Two groups live here:

* ``AirResultsContract`` and its parts validate ``reports/air_no2_results.json``
  (schema 1.x, documented in ``docs/air-results-schema.md``). Validation is a
  gate only: the API serves the original parsed JSON, so values, key order and
  ``null`` entries reach the frontend unchanged. Unknown keys are allowed so
  additive analysis changes do not break the backend.
* The ``*Response`` models describe the API envelopes for OpenAPI docs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

# ---------------------------------------------------------------------------
# Result contract (schema 1.x)
# ---------------------------------------------------------------------------


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)


MonthStr = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
Fraction = Field(ge=0.0, le=1.0)
Count = Field(ge=0)

PctChangeStatus = Literal[
    "computed",
    "withheld_nonpositive_baseline",
    "withheld_missing_data",
    "withheld_no_remaining_months",
]


class ClaimStatus(ContractModel):
    overall: str
    data_cleaning_and_accounting: str
    baseline_comparison: str
    before_after_significance: str
    reference_region_comparison: str
    causal_attribution: str
    paper_replication_classification: str


class LatLon(ContractModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class BoundingBox(ContractModel):
    west: float = Field(ge=-180.0, le=180.0)
    south: float = Field(ge=-90.0, le=90.0)
    east: float = Field(ge=-180.0, le=180.0)
    north: float = Field(ge=-90.0, le=90.0)

    @model_validator(mode="after")
    def _ordered(self) -> "BoundingBox":
        if self.west >= self.east:
            raise ValueError("bounding box must have west < east")
        if self.south >= self.north:
            raise ValueError("bounding box must have south < north")
        return self


class Region(ContractModel):
    region_id: str
    name: str
    center: LatLon
    user_bounding_box: BoundingBox
    data_bounding_box: BoundingBox
    spatial_note: str


class Dataset(ContractModel):
    provider: str
    instrument: str
    product: str
    version: str
    variable: str
    units: str


class QualityRules(ContractModel):
    validation_checks: Dict[str, StrictBool]


class MonthlyPoint(ContractModel):
    month: str = MonthStr
    no2_mean_molec_cm2: Optional[float]
    valid_days: int = Count
    calendar_days: int = Field(ge=1, le=31)
    coverage_fraction: float = Fraction
    flagged_below_50_pct: StrictBool
    flagged_below_10_valid_days: StrictBool

    @model_validator(mode="after")
    def _consistent(self) -> "MonthlyPoint":
        if self.valid_days > self.calendar_days:
            raise ValueError("valid_days cannot exceed calendar_days")
        if self.valid_days == 0 and self.no2_mean_molec_cm2 is not None:
            raise ValueError("a month with zero valid days must have a null mean, never a filled value")
        return self


class FlaggedMonth(ContractModel):
    month: str = MonthStr
    valid_days: int = Count
    calendar_days: int = Field(ge=1, le=31)
    coverage_fraction: float = Fraction


class AnnualSeason(ContractModel):
    year: int
    valid_days: int = Count
    calendar_days: int = Count
    coverage_fraction: float = Fraction
    valid_day_mean_molec_cm2: Optional[float]
    equal_month_mean_molec_cm2: Optional[float]
    flagged_months: List[Any]
    any_flagged_month: StrictBool


class Comparison(ContractModel):
    comparison_id: str
    label: str
    weighting: Literal["valid_day_annual_equal_weight", "equal_month_annual_equal_weight"]
    baseline_years_requested: List[int]
    available_baseline_years: List[int]
    unavailable_baseline_years: List[int]
    target_year: int
    months_included: List[int]
    baseline_mean_molec_cm2: Optional[float]
    baseline_annual_min_molec_cm2: Optional[float]
    baseline_annual_max_molec_cm2: Optional[float]
    target_mean_molec_cm2: Optional[float]
    absolute_change_molec_cm2: Optional[float]
    pct_change: Optional[float]
    pct_change_status: PctChangeStatus
    baseline_valid_days: int = Count
    baseline_calendar_days: int = Count
    target_valid_days: int = Count
    target_calendar_days: int = Count
    flagged_months_in_baseline: List[FlaggedMonth]
    flagged_months_in_target: List[FlaggedMonth]
    any_flagged_month: StrictBool
    sampling_sensitivity_review_required: StrictBool

    @model_validator(mode="after")
    def _pct_matches_status(self) -> "Comparison":
        if self.pct_change_status == "computed" and self.pct_change is None:
            raise ValueError("pct_change_status 'computed' requires a numeric pct_change")
        if self.pct_change_status != "computed" and self.pct_change is not None:
            raise ValueError("a withheld pct_change must be null")
        if any(not 1 <= m <= 12 for m in self.months_included):
            raise ValueError("months_included must contain calendar months 1–12")
        return self


class Comparisons(ContractModel):
    primary_2015_2019_valid_day: Comparison
    sensitivity_2019_2021_valid_day: Comparison
    primary_2015_2019_equal_month: Comparison
    sensitivity_2019_2021_equal_month: Comparison


class CoverageSensitivity(ContractModel):
    strict_all_years_unflagged: Dict[str, Comparison]
    excluding_target_flagged_months: Dict[str, Comparison]


class MonthChange(ContractModel):
    absolute_change_molec_cm2: Optional[float]
    pct_change: Optional[float]
    pct_change_status: PctChangeStatus


class TargetMonth(ContractModel):
    mean_molec_cm2: Optional[float]
    valid_days: int = Count
    calendar_days: int = Field(ge=1, le=31)
    coverage_fraction: float = Fraction
    flagged_below_50_pct: StrictBool


class MatchedMonth(ContractModel):
    calendar_month: int = Field(ge=1, le=12)
    month_name: str
    primary_2015_2019: Dict[str, Any]
    sensitivity_2019_2021: Dict[str, Any]
    target_2022: TargetMonth
    vs_primary_2015_2019: MonthChange
    vs_sensitivity_2019_2021: MonthChange


class BeforeAfterInference(ContractModel):
    status: str
    p_value: Optional[float]
    ci_95_lower_molec_cm2: Optional[float]
    ci_95_upper_molec_cm2: Optional[float]
    statistical_significance_claimed: StrictBool
    reasons_not_assessed: List[str]

    @model_validator(mode="after")
    def _no_stats_unless_assessed(self) -> "BeforeAfterInference":
        if self.status != "assessed":
            filled = [
                name
                for name in ("p_value", "ci_95_lower_molec_cm2", "ci_95_upper_molec_cm2")
                if getattr(self, name) is not None
            ]
            if filled:
                raise ValueError(f"status '{self.status}' requires null {', '.join(filled)}")
            if self.statistical_significance_claimed:
                raise ValueError(f"status '{self.status}' cannot claim statistical significance")
        return self


class TrendWindow(ContractModel):
    window_id: str
    label: str
    status: str
    start_month: str = MonthStr
    end_month: str = MonthStr
    n_months: int = Count
    primary_method: str
    slope_molec_cm2_per_year: Optional[float]
    ci_95_lower_molec_cm2_per_year: Optional[float]
    ci_95_upper_molec_cm2_per_year: Optional[float]
    p_value: Optional[float] = Field(ge=0.0, le=1.0)
    significant_at_alpha_0_05: Optional[StrictBool]
    assumptions_and_caveats: List[str]

    @model_validator(mode="after")
    def _assessed_has_values(self) -> "TrendWindow":
        if self.status == "assessed" and (self.slope_molec_cm2_per_year is None or self.p_value is None):
            raise ValueError("an assessed trend window requires slope and p_value")
        return self


class TrendWindows(ContractModel):
    pre_invasion: TrendWindow
    full_record: TrendWindow


class Statistics(ContractModel):
    before_after_seasonal_inference: BeforeAfterInference
    multi_year_seasonality_aware_trend: TrendWindows
    daily_autocorrelation_diagnostics: Dict[str, Any]


class ChartEntry(ContractModel):
    png_path: str
    data_csv_path: str


class AirResultsContract(ContractModel):
    schema_version: str = Field(pattern=r"^1\.\d+\.\d+$")
    status: ClaimStatus
    region: Region
    dataset: Dataset
    quality_rules: QualityRules
    monthly_series: List[MonthlyPoint] = Field(min_length=1)
    annual_march_august: List[AnnualSeason]
    comparisons: Comparisons
    coverage_sensitivity: CoverageSensitivity
    matched_months: List[MatchedMonth]
    statistics: Statistics
    charts: Dict[str, ChartEntry]
    limitations: List[str] = Field(min_length=1)
    reproducibility: Dict[str, Any]

    @model_validator(mode="after")
    def _months_ordered(self) -> "AirResultsContract":
        months = [point.month for point in self.monthly_series]
        if any(earlier >= later for earlier, later in zip(months, months[1:])):
            raise ValueError("monthly_series must be strictly chronological with unique months")
        return self


# ---------------------------------------------------------------------------
# API envelopes (documentation and shape of responses)
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class DatasetHealth(BaseModel):
    ready: bool
    source_file: str
    schema_version: Optional[str]
    loaded_at: Optional[str]
    charts: Dict[str, bool]
    problems: List[ErrorBody]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    datasets: Dict[str, DatasetHealth]


class StudyLink(BaseModel):
    study_id: str
    name: str
    endpoint: str


class ElementEntry(BaseModel):
    element_id: str
    label: str
    status: Literal["available", "unavailable"]
    indicator: Optional[str] = None
    reason: Optional[str] = None
    studies: List[StudyLink] = []


class CaseEntry(BaseModel):
    case_id: str
    name: str
    conflict_start: str
    elements: List[ElementEntry]


class CasesResponse(BaseModel):
    cases: List[CaseEntry]


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    geometry: GeoJSONPolygon
    properties: Dict[str, Any]


class MapPayload(BaseModel):
    center: Dict[str, float]
    bounds: List[List[float]] = Field(description="[[south, west], [north, east]] for fitBounds-style APIs")
    study_boundary: GeoJSONFeature
    sampled_grid_center_extent: GeoJSONFeature
    rendering: Literal["boundary_only"]
    note: str


class ChartLink(BaseModel):
    chart_id: str
    title: str
    url: str
    media_type: Literal["image/png"]
    contract: Dict[str, Any]


class Highlights(BaseModel):
    claim_status: Dict[str, str]
    notices: List[str]
    seasonal_differences: Dict[str, Any]
    multi_year_trend: Dict[str, Any]
    coverage_warnings: List[Dict[str, Any]]


class AirStudyResponse(BaseModel):
    case_id: str
    element_id: str
    study_id: str
    schema_version: str
    map: MapPayload
    charts: List[ChartLink]
    highlights: Highlights
    result: Dict[str, Any] = Field(description="The validated result contract, served unchanged")
