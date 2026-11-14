# Backend Handoff Schema: `reports/air_no2_results.json`

**Schema version:** `1.0.0`  
**Primary consumer:** Backend API / frontend study integration (coordinated with G).  
**Generator:** `python -m src.air_analysis` (also re-emitted by `python -m src.no2_pipeline`).

## 1. JSON Contract & Nullability Rules

- **Strict RFC 8259 JSON (`allow_nan=False`):** `NaN`, `Infinity`, and `-Infinity` are forbidden anywhere in the file. Unavailable numeric metrics, withheld percentage changes (`baseline <= 0` or missing), and unassessed inferential statistics serialize strictly as JSON **`null`**.
- **Existing deliverables preserved:**
  - `reports/no2_monthly.csv` — unchanged 5-column monthly series (`month, no2_mean_molec_cm2, valid_days, calendar_days, coverage_fraction`)
  - `reports/data_quality.json` — input provenance, daily calendar reconciliation, `<50%` proposed project coverage flag summary, and accounting checks
  - `reports/no2_seasonal_comparisons.csv` & `reports/no2_matched_months.csv` — tabular chart data backing Figures 2 and 3
  - `reports/no2_monthly.png`, `reports/no2_seasonal_comparison.png`, `reports/no2_matched_months.png` — presentation figures

## 2. Top-Level Object Structure

| Key | Type | Description |
|---|---|---|
| `schema_version` | `string` | Semantic schema version (`"1.0.0"`). |
| `status` | `object` | Machine-readable validation and claim-level status flags (`overall`, `data_cleaning_and_accounting`, `baseline_comparison`, `before_after_significance`, `reference_region_comparison`, `causal_attribution`, `paper_replication_classification`). |
| `region` | `object` | `region_id`, `name`, `center` (`lat`/`lon`), `user_bounding_box`, `data_bounding_box` (Giovanni snapped grid-center bounds), and `spatial_note`. |
| `dataset` | `object` | Provider, instrument, product, version, variable token, units (`"molecules/cm^2"`), declared fill sentinel, Giovanni reproducibility URL, and SHA-256 hash/size of raw input. |
| `quality_rules` | `object` | Zero-fill / negative-preservation rules, proposed `<50%` flag rule (`coverage_fraction < 0.50`), severe-sparsity reference (`valid_days < 10`), `daily_counts`, `monthly_summary`, and boolean `validation_checks`. |
| `monthly_series` | `array<object>` | Full chronological series (`90` months). Each item has `month`, `no2_mean_molec_cm2` (`number \| null`), `valid_days`, `calendar_days`, `coverage_fraction`, `flagged_below_50_pct`, `flagged_below_10_valid_days`. |
| `annual_march_august` | `array<object>` | Per-year March–August metrics (`2015`–`2022`) including `valid_days`, `calendar_days`, `coverage_fraction`, `valid_day_mean_molec_cm2`, `equal_month_mean_molec_cm2`, `flagged_months`, and `any_flagged_month`. |
| `comparisons` | `object` | March–August baseline and prior-year comparisons: `primary_2015_2019_valid_day`, `sensitivity_2019_2021_valid_day`, `primary_2015_2019_equal_month`, `sensitivity_2019_2021_equal_month`, `context_2021_valid_day`, `context_2021_equal_month`. |
| `coverage_sensitivity` | `object` | Identical-remaining-month exclusions (`strict_all_years_unflagged` and `excluding_target_flagged_months`) evaluated under both baselines and weightings. |
| `matched_months` | `array<object>` | Calendar-month comparisons (`Mar`–`Aug`): baseline mean/min/max/SD/coverage/flagged years, `year_2021_mean_molec_cm2`, `target_2022` values & coverage, and changes vs. both baselines. |
| `statistics` | `object` | Separated inferential structures: `before_after_seasonal_inference` (`"status": "not_assessed"`), `multi_year_seasonality_aware_trend` (`pre_invasion` & `full_record`), and `daily_autocorrelation_diagnostics`. |
| `charts` | `object` | Relative paths and metadata for all 3 PNG figures and their backing CSV data tables. |
| `limitations` | `array<string>` | Explicit guardrails to render in UI/API notes alongside any displayed metrics. |
| `reproducibility` | `object` | Exact regeneration command (`python -m src.air_analysis`), test command, and doc paths. |

### Comparison Object Fields (`comparisons.*` & `coverage_sensitivity.*.*`)

- `comparison_id`, `label`, `weighting` (`"valid_day_annual_equal_weight"` or `"equal_month_annual_equal_weight"`)
- `baseline_years_requested`, `available_baseline_years`, `unavailable_baseline_years`, `target_year`, `months_included`
- `baseline_mean_molec_cm2`, `baseline_annual_min_molec_cm2`, `baseline_annual_max_molec_cm2`, `target_mean_molec_cm2` (`number | null`)
- `absolute_change_molec_cm2`, `pct_change` (`number | null`), `pct_change_status` (`"computed"` | `"withheld_nonpositive_baseline"` | `"withheld_missing_data"` | `"withheld_no_remaining_months"`)
- `baseline_valid_days`, `baseline_calendar_days`, `target_valid_days`, `target_calendar_days`
- `flagged_months_in_baseline`, `flagged_months_in_target`, `any_flagged_month`, `sampling_sensitivity_review_required`

## 3. Abbreviated Example Payload (`reports/air_no2_results.json`)

```json
{
  "schema_version": "1.0.0",
  "status": {
    "overall": "validated_descriptive_with_limitations",
    "data_cleaning_and_accounting": "validated",
    "baseline_comparison": "validated",
    "before_after_significance": "not_assessed",
    "reference_region_comparison": "not_assessed_missing_comparator_regions",
    "causal_attribution": "not_established",
    "paper_replication_classification": "related_comparison"
  },
  "region": {
    "region_id": "ukraine_kyiv",
    "name": "Kyiv, Ukraine",
    "center": { "lat": 50.45, "lon": 30.523 },
    "user_bounding_box": { "west": 30.273, "south": 50.2, "east": 30.773, "north": 50.7 },
    "data_bounding_box": { "west": 30.375, "south": 50.375, "east": 30.625, "north": 50.625 }
  },
  "dataset": {
    "provider": "NASA Giovanni",
    "instrument": "Aura/OMI",
    "product": "OMNO2d v004",
    "version": "004",
    "variable": "mean_OMNO2d_004_ColumnAmountNO2TropCloudScreened",
    "units": "molecules/cm^2"
  },
  "comparisons": {
    "primary_2015_2019_valid_day": {
      "weighting": "valid_day_annual_equal_weight",
      "months_included": [3, 4, 5, 6, 7, 8],
      "baseline_mean_molec_cm2": 2357619230901594.0,
      "target_mean_molec_cm2": 1698443510624528.2,
      "absolute_change_molec_cm2": -659175720277065.8,
      "pct_change": -27.9594,
      "pct_change_status": "computed",
      "any_flagged_month": true
    }
  },
  "statistics": {
    "before_after_seasonal_inference": {
      "status": "not_assessed",
      "p_value": null,
      "ci_95_lower_molec_cm2": null,
      "ci_95_upper_molec_cm2": null
    },
    "multi_year_seasonality_aware_trend": {
      "full_record": {
        "status": "assessed",
        "n_months": 90,
        "primary_method": "Month-Fixed-Effects OLS with Newey-West HAC standard errors",
        "slope_molec_cm2_per_year": -41778617093514.8,
        "p_value": 0.124486,
        "significant_at_alpha_0_05": false
      }
    }
  }
}
```
