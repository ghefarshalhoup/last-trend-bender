# Four-Element Atlas Exports & Backend Endpoints

Read-only extension on top of Milestone 1 ([backend-api.md](backend-api.md)). All existing Air endpoints (`GET /api/air/kyiv`, `GET /api/air/kyiv/charts/{chart_id}`) and `datasets.air_kyiv` health structure remain unchanged.

> Note on external handoff files: local Windows paths referenced during review (`C:/Users/ghefa/.../VARIABLE-CATALOG.md` and `variables.json`) are outside this workspace and inaccessible on macOS; all variable IDs, units, spatial support, and schemas here match this repository's verified 25-metric catalog and `backend/` Pydantic contracts.

## Regenerating the Reviewed Exports

```bash
MPLCONFIGDIR=/tmp/mpl python3 -m src.atlas_exports
```

Writes strictly finite (`allow_nan=False`), schema-validated JSON artifacts to `reports/`:

| Artifact | Endpoint | Role |
|---|---|---|
| `reports/atlas_catalog.json` | `GET /api/variables` | Master 25-metric catalog across Air (6), Fire (7), Earth/`land` (6), Water (6) |
| `reports/atlas_fire_ukraine.json` | `GET /api/fire/ukraine` | Fire study package: primary normalization, separated matched-date (`169d/yr` `UKR-ADM0`) & legacy rates, CMR outage flags, seasonal `0.25°` cells, Fire-vs-dryness scatter |
| `reports/atlas_fire_cells.json` | `GET /api/fire/ukraine/cells` | Complete `0.25° × 0.25°` monthly grid (`2019-03` to `2022-08`) with filter slices + `cell_registry` & `cmr_month_coverage` |
| `reports/atlas_water_ukraine.json` | `GET /api/water/ukraine` | Water regional context (`prectotcorr` + `vpd_kpa` primary; 6 Ukraine study boxes + 2 EU weather comparators) |
| `reports/atlas_earth_ukraine.json` | `GET /api/land/ukraine` | Earth/`land` regional context (`gwettop` primary; depth wetness, skin temperature, albedo) |
| `reports/atlas_air_weather_ukraine.json` | `GET /api/air/weather` | Additive Air meteorology context (`ws10m`, `cloud_amt`, `ps`, `clrsky_sfc_sw_dwn`, `cloud_radiative_attenuation_wm2`), Kyiv NO₂ coverage/weather sensitivities, & Kraków/Prague 2022 comparison |

Canonical multi-region trend verdicts (`reports/trend_results.json` served by `GET /api/trends`) and regional NO₂ series (`reports/atlas_no2_regional.json` served by `GET /api/air/no2`) are documented in [trend-results-schema.md](trend-results-schema.md).

## Endpoints

### `GET /api/cases`
Keeps `elements[0]` (`air` -> `/api/air/kyiv`) byte-for-byte compatible while updating `fire` (`/api/fire/ukraine`), `land` (`label: "Earth"`, `/api/land/ukraine`), and `water` (`/api/water/ukraine`) to report `available` (or `unavailable` with `reason: "data_not_ready"` if an artifact is missing or fails contract validation).

### `GET /api/health`
Reports readiness and Pydantic validation problems for `air_kyiv` plus all six atlas artifacts (`atlas_catalog`, `fire_ukraine`, `fire_ukraine_cells`, `water_ukraine`, `land_ukraine`, `air_weather`). Returns HTTP `503` with `status: "degraded"` if any configured artifact is missing or fails validation, while healthy sibling endpoints continue serving.

### `GET /api/variables`
Optional query filters:
- `element_id`: `air | fire | land | water` (`earth` accepted as an alias for `land`)
- `metric_id`: exact curated metric ID (returns `404 variable_not_found` if absent)

Every variable object guarantees:
- `plain_definition` (concise one-sentence definition for every one of the 25 metrics), `units`, `is_interval_scale`
- `dates` (`start`, `end`, `seasonal_window`, `n_years_available`)
- `supported_baselines` (`2015-2019` strictly marked `supported: false`, `status: "withheld_insufficient_baseline"` for Fire metrics)
- `spatial_support` (`presentation_type`, `resolution`, `sampling_method`, `supports_fine_heatmap`, `supports_spatial_cells`, `ukraine_region_ids`)
- `method_id`, `uncertainty_and_status`, `sources`, `limitations`

### `GET /api/fire/ukraine` & `GET /api/fire/ukraine/cells`
- Primary normalization (`method_id: "firms_type0_per_1k_km2_cmr_obsday_box_area_v1"`): `detections / (box_area_km2 / 1000) / cmr_observed_days`.
- Strictly separated from `matched_dates_169d_ukr_adm0_sensitivity` (`169d/yr` common CMR dates × `UKR-ADM0` clipped area) and `legacy_unnormalized_rate`.
- Quality flags: `2015–2019` baseline disabled, `16` missing 2022 CMR days (`2022-03-05` plus `2022-07-27..2022-08-10` orbit outage), repeated overpass clustering, and static `type=2` source caveats.
- `GET /api/fire/ukraine/cells` supports optional read-only query filters: `month` (`YYYY-MM`), `year` (`2019..2022`), `calendar_month` (`3..8`), `region_id`, `type_mode` (`all | type0 | type2 | type3`), `confidence_mode` (`all | nominal_high`), `inside_ukr_only` (`bool`).

### `GET /api/water/ukraine` & `GET /api/land/ukraine`
- Featured indicators first (`prectotcorr` + `vpd_kpa` for Water; `gwettop` for Earth/`land`), followed by secondary variables in `available_variables`.
- GeoJSON `FeatureCollection` polygons for all 6 Ukraine regional study boxes (with `box_vs_ukr_adm0` spatial audit stats) plus 2 external EU weather comparator boxes.
- Interval-scale / signed metrics (`precip_minus_pet_mm_day`, `ts`, `ts_minus_t2m_c`, `t2m`, `t2m_max`, `cloud_radiative_attenuation_wm2`) strictly set `pct_change: null` and `pct_change_status: "withheld_interval_scale"`.
- Explicitly scoped as coarse `0.5°` / `1.0°` regional environmental context (cannot produce local heatmaps, do not rule out localized drought, and do not observe direct war infrastructure damage).

### `GET /api/air/weather` (additive Kyiv & comparator diagnostics)
- Carries `kyiv_no2_sensitivities`: Kyiv OMI NO₂ coverage-exclusion sensitivity (excluding the 37 `<50%`-coverage months, dropping Nov/Dec) and weather-covariate-adjusted Month-FE OLS + calendar-lag Newey–West HAC regressions (`ws10m`, `cloud_amt`, `ps`, `t2m`), plus Box–Tiao intervention references.
- Carries `krakow_prague_2022_comparison`: March–August 2022 vs. `2015–2019` and `2019–2021` shifts across all 22 NASA POWER indicators and OMI NO₂ (`kyiv_no2_box`, `poland_krakow`, `czechia_prague`, `kharkiv_city`).
