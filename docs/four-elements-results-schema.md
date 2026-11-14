# Four-Elements Results & Web Bundle Schema (`1.0.0`)

All JSON outputs emitted by [`src/four_elements_analysis.py`](../src/four_elements_analysis.py), [`src/weather_power_pipeline.py`](../src/weather_power_pipeline.py), and [`src/build_web_bundle.py`](../src/build_web_bundle.py) use `write_strict_json` (`allow_nan=False`, finite IEEE floats or `null`, strict RFC 8259).

## 1. Reports Generated in `reports/`
| Artifact | Format | Description |
| --- | --- | --- |
| `kyiv_four_elements_results.json` | Strict JSON | Top-level 4-Elements case study results, daily wind/cloud strata, Box–Tiao weather controls, 6-region drought/fire matrix, Seasonal MK trends + BH/BY FDR, and AR(1)-prewhitened couplings. |
| `four_elements_quality.json` | Strict JSON | Input SHA-256 checksums, panel/daily row counts, missing-data & causal safeguard invariants. |
| `four_elements_monthly_panel.csv` | CSV | 768 region-month rows (`8 regions x 96 months 2015-01..2022-12`) fusing NASA POWER (`cos(lat)` 3x3 mean + derived VPD/PET/water balance), Kyiv OMI NO2, and FIRMS VIIRS area-normalized densities. |
| `kyiv_daily_air_weather.csv` | CSV | Daily Kyiv OMI NO2 calendar aligned with MERRA-2/CERES daily weather (`2015-03-01..2022-08-31`). |
| `four_elements_comparisons.csv` | CSV | 24 Kyiv Mar–Aug 2022 vs `2015–2019` & `2019–2021` 4-element comparisons (`is_interval_scale` preserved). |
| `kyiv_four_elements_dashboard.png` | PNG | 4-row stacked Kyiv deseasonalized monthly anomaly overview (`2015–2022`). |
| `kyiv_weather_no2_sensitivity.png` | PNG | Kyiv daily wind/cloud strata bar plot & observed-vs-weather Box–Tiao counterfactual trajectory. |
| `ukraine_fire_drought_contrast.png` | PNG | Sub-national `ΔVPD` vs `type0` fire scatter + `type0` vs `type2` regional bar divergence. |

> **Milestone 1 Compatibility:** Existing `reports/air_no2_results.json`, `reports/fire_viirs_results.json`, and `backend/` remain untouched so Milestone 1 API routes and tests remain 100% compatible.

## 2. Top-Level Structure of `reports/kyiv_four_elements_results.json`
- `schema_version`: `"1.0.0"`
- `case_id`: `"ukraine"`
- `study_id`: `"kyiv_four_elements"`
- `conflict_start`: `"2022-02-24"`
- `region`: Kyiv study bounding box (`kyiv_no2_box`), WGS84 area (`km^2`), and sensor resolution statement.
- `status`:
  - `before_after_significance`: `"not_assessed"`
  - `exploratory_monthly_intervention`: `"assessed_noncausal_single_season_only"`
  - `causal_attribution`: `"not_established"`
  - `confounder_control`: `"assessed_via_daily_stratification_and_monthly_covariates"`
  - `sub_national_drought_fire_contrast`: `"assessed_descriptive_2019_2022"`
- `kyiv_four_element_comparisons`: Array of 24 metrics with `is_interval_scale`, `baseline_2015_2019_mean`, `baseline_2019_2021_mean`, `target_2022_mean`, `*_abs_diff`, `*_pct_change` (`null` on Celsius/zero-crossing metrics), and `*_status`.
- `kyiv_daily_wind_cloud_sensitivity`: 5 daily filter strata (`all_valid_days`, `low_wind_lt_3ms`, `higher_wind_ge_3ms`, `clear_moderate_cloud_lt_60pct`, `excluding_april_2022`) + pre-invasion Spearman correlations.
- `kyiv_intervention_and_weather_controls`: Unadjusted + meteorological Box–Tiao step models, April-2022 exclusion & Mar–Aug sensitivities, pre-invasion partial trends, Davies structural break test, and monthly observed vs weather-expected series.
- `regional_fire_water_earth_contrast`: `regions` array (6 Ukraine boxes) + `external_eu_weather_context_2015_2019_vs_2022` (`poland_krakow`, `czechia_prague`).
- `multi_element_trends_and_couplings`: `kyiv_seasonal_trends` (Hirsch–Slack Sen slopes + BH/BY q-values) and `prewhitened_cross_element_couplings` (lagged Kendall tau-b + Sidak p + BH-FDR q).
- `limitations`: Mandatory scientific caveats list.

## 3. Standalone Trend Observatory Bundle (`web/data/ukraine_4elements_bundle.json`)
Built by `python -m src.build_web_bundle`, containing the analytical summaries above plus precomputed `2015–2019` and `2019–2021` deseasonalized monthly anomaly arrays and data-quality flags across all 8 study boxes and 16 core variables across Air, Fire, Water, and Earth.

Serve locally via HTTP (because browsers block `fetch()` over `file://`):
```bash
python3 -m http.server 8080 --directory web
```
Then open `http://localhost:8080/`.
