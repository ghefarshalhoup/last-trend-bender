/**
 * Types for the parts of the backend contract this frontend reads.
 * Source of truth: docs/backend-api.md and docs/air-results-schema.md.
 *
 * Every measured value that can be absent is `number | null`. Null is meaningful
 * (missing measurement, or a statistic that was not assessed) and must never be
 * rendered as zero.
 */

export type PctChangeStatus =
  | 'computed'
  | 'withheld_nonpositive_baseline'
  | 'withheld_missing_data'
  | 'withheld_no_remaining_months'

// ---- /api/cases -----------------------------------------------------------

export interface StudyLink {
  study_id: string
  name: string
  endpoint: string
}

export interface ElementEntry {
  element_id: string
  label: string
  status: 'available' | 'unavailable'
  indicator: string | null
  reason: string | null
  studies: StudyLink[]
}

export interface CaseEntry {
  case_id: string
  name: string
  conflict_start: string
  elements: ElementEntry[]
}

export interface CasesResponse {
  cases: CaseEntry[]
}

// ---- /api/air/kyiv: envelope ---------------------------------------------

export interface GeoJsonFeature {
  type: 'Feature'
  geometry: { type: 'Polygon'; coordinates: number[][][] }
  properties: Record<string, unknown>
}

export interface MapPayload {
  center: { lat: number; lon: number }
  /** [[south, west], [north, east]] */
  bounds: [[number, number], [number, number]]
  study_boundary: GeoJsonFeature
  sampled_grid_center_extent: GeoJsonFeature
  rendering: 'boundary_only'
  note: string
}

export interface ChartLink {
  chart_id: string
  title: string
  url: string
  media_type: 'image/png'
  contract: Record<string, unknown>
}

export interface FlaggedMonth {
  month: string
  valid_days: number
  calendar_days: number
  coverage_fraction: number
}

export interface ClaimStatus {
  overall: string
  data_cleaning_and_accounting: string
  baseline_comparison: string
  before_after_significance: string
  reference_region_comparison: string
  causal_attribution: string
  paper_replication_classification: string
}

export interface Highlights {
  claim_status: ClaimStatus
  notices: string[]
  seasonal_differences: {
    description: string
    significance_status: string
    headline_comparison_id: string
    comparison_ids: string[]
    coverage_sensitivity_ids: Record<string, string[]>
  }
  multi_year_trend: { description: string; window_ids: string[] }
  coverage_warnings: FlaggedMonth[]
}

// ---- /api/air/kyiv: result contract (schema 1.x) -------------------------

export interface Comparison {
  comparison_id: string
  label: string
  weighting: string
  baseline_years_requested: number[]
  available_baseline_years: number[]
  unavailable_baseline_years: number[]
  target_year: number
  months_included: number[]
  baseline_mean_molec_cm2: number | null
  baseline_annual_min_molec_cm2: number | null
  baseline_annual_max_molec_cm2: number | null
  target_mean_molec_cm2: number | null
  absolute_change_molec_cm2: number | null
  pct_change: number | null
  pct_change_status: PctChangeStatus
  baseline_valid_days: number
  baseline_calendar_days: number
  target_valid_days: number
  target_calendar_days: number
  flagged_months_in_baseline: FlaggedMonth[]
  flagged_months_in_target: FlaggedMonth[]
  any_flagged_month: boolean
  sampling_sensitivity_review_required: boolean
  note?: string
}

export interface MonthChange {
  absolute_change_molec_cm2: number | null
  pct_change: number | null
  pct_change_status: PctChangeStatus
}

export interface BaselineMonth {
  mean_molec_cm2: number | null
  min_molec_cm2: number | null
  max_molec_cm2: number | null
  sd_molec_cm2: number | null
  available_years: number[]
  unavailable_years: number[]
  mean_coverage_fraction: number | null
  valid_days_total: number
  calendar_days_total: number
  flagged_years_count: number
  flagged_years_detail: string[]
}

export interface MatchedMonth {
  calendar_month: number
  month_name: string
  primary_2015_2019: BaselineMonth
  sensitivity_2019_2021: BaselineMonth
  year_2021_mean_molec_cm2: number | null
  target_2022: {
    mean_molec_cm2: number | null
    valid_days: number
    calendar_days: number
    coverage_fraction: number
    flagged_below_50_pct: boolean
  }
  vs_primary_2015_2019: MonthChange
  vs_sensitivity_2019_2021: MonthChange
}

export interface BeforeAfterInference {
  status: string
  p_value: number | null
  ci_95_lower_molec_cm2: number | null
  ci_95_upper_molec_cm2: number | null
  statistical_significance_claimed: boolean
  reasons_not_assessed: string[]
}

export interface TrendWindow {
  window_id: string
  label: string
  status: string
  start_month: string
  end_month: string
  n_months: number
  primary_method: string
  slope_molec_cm2_per_year: number | null
  ci_95_lower_molec_cm2_per_year: number | null
  ci_95_upper_molec_cm2_per_year: number | null
  p_value: number | null
  significant_at_alpha_0_05: boolean | null
  assumptions_and_caveats: string[]
  /** Rank-based check of the same trend (seasonal Theil–Sen slope, modified Mann–Kendall). */
  nonparametric_sensitivity?: {
    method: string
    seasonal_theil_sen_molec_cm2_per_year: number | null
    hamed_rao_mk?: { n_months: number; p_value_unadjusted: number | null; p_value_hamed_rao: number | null }
  }
}

export interface MonthlyPoint {
  month: string
  no2_mean_molec_cm2: number | null
  valid_days: number
  calendar_days: number
  coverage_fraction: number
  flagged_below_50_pct: boolean
  flagged_below_10_valid_days: boolean
}

export interface AirResult {
  schema_version: string
  status: ClaimStatus
  region: {
    region_id: string
    name: string
    center: { lat: number; lon: number }
    spatial_note: string
  }
  dataset: {
    provider: string
    instrument: string
    product: string
    version: string
    variable: string
    units: string
    cloud_screen_rule?: string
    spatial_resolution_deg?: number
    reproducibility_url?: string
    catalogue_url?: string
  }
  quality_rules: {
    proposed_coverage_flag_rule?: string
    daily_counts?: {
      start_date: string
      end_date: string
      calendar_days: number
      valid_observations: number
      fill_value_rows: number
      absent_dates_count: number
      negative_valid_observations: number
    }
  }
  monthly_series: MonthlyPoint[]
  comparisons: Record<string, Comparison>
  coverage_sensitivity: {
    strict_all_years_unflagged: Record<string, Comparison>
    excluding_target_flagged_months: Record<string, Comparison>
  }
  matched_months: MatchedMonth[]
  statistics: {
    before_after_seasonal_inference: BeforeAfterInference
    multi_year_seasonality_aware_trend: {
      pre_invasion: TrendWindow
      full_record: TrendWindow
    }
  }
  limitations: string[]
}

export interface StudyPackage {
  case_id: string
  element_id: string
  study_id: string
  schema_version: string
  map: MapPayload
  charts: ChartLink[]
  highlights: Highlights
  result: AirResult
}
