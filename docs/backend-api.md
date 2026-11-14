# Backend API — Milestone 1 (Ukraine → Air/NO₂ → Kyiv)

A small, read-only FastAPI service that serves the validated Kyiv NO₂ result
artifact and its three charts to the frontend. It does **not** recompute any
science: it loads `reports/air_no2_results.json` (schema 1.x,
[air-results-schema.md](air-results-schema.md)), validates it, and serves it
unchanged. No database and no live NASA requests.

Code: [`backend/`](../backend). Analysis that produces the artifact:
`python -m src.air_analysis` (Husam).

## Install

From the repository root, in the project virtual environment:

```bash
pip install -r backend/requirements.txt        # run the API
pip install -r backend/requirements-dev.txt    # + tests
```

The backend needs only FastAPI, Pydantic and Uvicorn; it does not import the
analysis stack (pandas, scipy, matplotlib).

## Run

```bash
uvicorn backend.main:app --reload --port 8000
# from any other directory:
uvicorn --app-dir /path/to/war-environment-tracker backend.main:app --port 8000
```

Interactive docs: <http://localhost:8000/docs>. OpenAPI: `/openapi.json`.

The artifact is loaded once at startup. After regenerating results with
`python -m src.air_analysis`, **restart the server** (`--reload` only watches
Python files).

## Configure

All settings are environment variables. Relative paths are resolved against
the repository root (or the reports directory for the results file), never
against the shell's working directory.

| Variable | Default | Meaning |
|---|---|---|
| `WAR_TRACKER_REPORTS_DIR` | `reports` | Directory holding the chart PNGs. |
| `WAR_TRACKER_AIR_KYIV_RESULTS` | `air_no2_results.json` | Result contract. A relative value is resolved inside `WAR_TRACKER_REPORTS_DIR`. |
| `WAR_TRACKER_CORS_ORIGINS` | `http://localhost:5173, http://127.0.0.1:5173, http://localhost:3000, http://127.0.0.1:3000` | Comma-separated frontend origins allowed by CORS (GET only, no credentials). Empty string disables CORS; `*` allows any origin and cannot be mixed with explicit origins. |

Example for a deployed frontend:

```bash
export WAR_TRACKER_CORS_ORIGINS="https://our-demo.example"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Method & path | Success | Failure |
|---|---|---|
| `GET /api/health` | `200` with `status: "ok"` | `503` with `status: "degraded"` and a `problems` list |
| `GET /api/cases` | `200` | — (Air shows `unavailable` if data is not ready) |
| `GET /api/air/kyiv` | `200` study envelope | `503 data_unavailable` |
| `GET /api/air/kyiv/charts/{chart_id}` | `200 image/png` | `404 chart_not_found`, `503 data_unavailable` / `chart_unavailable` |

Allowed `chart_id` values: `monthly_timeline`, `seasonal_comparison`,
`matched_months`. Files are resolved from this allowlist only; nothing in a
request or in the JSON can point the server at another file.

### `GET /api/health`

```json
{
  "status": "ok",
  "service": "war-environment-tracker-backend",
  "version": "0.1.0",
  "datasets": {
    "air_kyiv": {
      "ready": true,
      "source_file": "reports/air_no2_results.json",
      "schema_version": "1.0.0",
      "loaded_at": "2026-11-14T17:38:58+00:00",
      "charts": { "monthly_timeline": true, "seasonal_comparison": true, "matched_months": true },
      "problems": []
    }
  }
}
```

### `GET /api/cases`

```json
{
  "cases": [
    {
      "case_id": "ukraine",
      "name": "Ukraine",
      "conflict_start": "2022-02-24",
      "elements": [
        {
          "element_id": "air", "label": "Air", "status": "available",
          "indicator": "Tropospheric NO₂ column (OMI OMNO2d v004)", "reason": null,
          "studies": [{ "study_id": "kyiv", "name": "Kyiv, Ukraine", "endpoint": "/api/air/kyiv" }]
        },
        { "element_id": "fire",  "label": "Fire",  "status": "unavailable", "indicator": null, "reason": "not_yet_integrated", "studies": [] },
        { "element_id": "land",  "label": "Land",  "status": "unavailable", "indicator": null, "reason": "not_yet_integrated", "studies": [] },
        { "element_id": "water", "label": "Water", "status": "unavailable", "indicator": null, "reason": "not_yet_integrated", "studies": [] }
      ]
    }
  ]
}
```

The pending elements are placeholders defined in `backend/catalog.py`;
confirm the final list and labels with G.

### `GET /api/air/kyiv`

```json
{
  "case_id": "ukraine",
  "element_id": "air",
  "study_id": "kyiv",
  "schema_version": "1.0.0",
  "map": {
    "center": { "lat": 50.45, "lon": 30.523 },
    "bounds": [[50.2, 30.273], [50.7, 30.773]],
    "study_boundary": {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[30.273, 50.2], [30.773, 50.2], [30.773, 50.7], [30.273, 50.7], [30.273, 50.2]]] },
      "properties": { "kind": "study_boundary", "region_id": "ukraine_kyiv", "name": "Kyiv, Ukraine", "source": "region.user_bounding_box" }
    },
    "sampled_grid_center_extent": {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[30.375, 50.375], [30.625, 50.375], [30.625, 50.625], [30.375, 50.625], [30.375, 50.375]]] },
      "properties": { "kind": "sampled_grid_center_extent", "source": "region.data_bounding_box", "note": "Giovanni reports snapped 0.25-degree grid-center bounds …" }
    },
    "rendering": "boundary_only",
    "note": "The polygon is the study window used for the area average. It is not a pollution heatmap: each NO₂ value describes the whole box, not places inside it."
  },
  "charts": [
    {
      "chart_id": "monthly_timeline",
      "title": "Monthly tropospheric NO₂ over the Kyiv study box, 2015–2022",
      "url": "/api/air/kyiv/charts/monthly_timeline",
      "media_type": "image/png",
      "contract": { "png_path": "reports/no2_monthly.png", "data_csv_path": "reports/no2_monthly.csv", "baseline_displayed": "…", "coverage_flag_displayed": "…" }
    }
  ],
  "highlights": {
    "claim_status": { "before_after_significance": "not_assessed", "causal_attribution": "not_established", "…": "…" },
    "notices": [
      "Before/after significance not assessed (status: not_assessed).",
      "Causal attribution to the war: not_established.",
      "Reference-region comparison: not_assessed_missing_comparator_regions."
    ],
    "seasonal_differences": {
      "description": "Descriptive March–August differences between 2022 and baseline seasons. Not a trend, and not tested for significance.",
      "significance_status": "not_assessed",
      "headline_comparison_id": "primary_2015_2019_valid_day",
      "comparison_ids": ["primary_2015_2019_valid_day", "sensitivity_2019_2021_valid_day", "primary_2015_2019_equal_month", "sensitivity_2019_2021_equal_month"],
      "coverage_sensitivity_ids": { "strict_all_years_unflagged": ["…"], "excluding_target_flagged_months": ["…"] },
      "source": "result.comparisons, result.coverage_sensitivity, result.matched_months"
    },
    "multi_year_trend": {
      "description": "Seasonality-aware linear trend across the monthly record. Answers a different question from the seasonal differences.",
      "window_ids": ["pre_invasion", "full_record"],
      "source": "result.statistics.multi_year_seasonality_aware_trend"
    },
    "coverage_warnings": [{ "month": "2022-04", "valid_days": 8, "calendar_days": 30, "coverage_fraction": 0.2667 }]
  },
  "result": { "…": "the full reports/air_no2_results.json contract, unchanged" }
}
```

### Errors

Every error uses one shape:

```json
{ "error": { "code": "chart_not_found", "message": "Unknown chart 'x'.", "details": { "allowed_chart_ids": ["monthly_timeline", "seasonal_comparison", "matched_months"] } } }
```

| Code | Status | When |
|---|---|---|
| `data_unavailable` | 503 | Result file missing, unreadable or invalid. `details` lists the load problems. |
| `chart_unavailable` | 503 | Contract is fine but that chart's entry is missing or points elsewhere, or its PNG is missing or not a PNG. |
| `chart_not_found` | 404 | `chart_id` is not on the allowlist. |
| `not_found` / `method_not_allowed` | 404 / 405 | Unknown route or non-GET method. |

Load problem codes reported by `/api/health`: `results_missing`,
`results_unreadable` (bad JSON or `NaN`/`Infinity`), `results_invalid`
(schema violation, with per-field details), `chart_missing`, `chart_invalid`,
`chart_contract_mismatch`.

## What the validation gate enforces

Validation never alters values; it decides whether the artifact may be
served. Beyond types and required keys of schema 1.x, it checks:

- Strict JSON: `NaN`, `Infinity` and `-Infinity` are rejected.
- `schema_version` is `1.x.y`. A major version change needs a backend update.
- Bounding boxes have `west < east` and `south < north`.
- `monthly_series` is strictly chronological; `valid_days ≤ calendar_days`;
  a month with zero valid days has a `null` mean (never zero-filled).
- `pct_change` is a number only when `pct_change_status` is `computed`.
- Before/after inference: unless `status` is `assessed`, `p_value` and both
  CI bounds must be `null` and significance must not be claimed.
- An assessed trend window has a slope and a `p_value` in [0, 1].
- Types are strict, with no coercion: every numeric value in the contract is
  declared, and a numeric string (`"123"`), a boolean, or a fractional count
  is rejected. JSON integers remain valid where a float is expected.
- Booleans are real JSON booleans.
- The contract lists all three charts, each pointing at the expected file.

Unknown extra keys are allowed and passed through, so additive analysis
changes do not break the API. Removing or renaming fields does; coordinate
those with the backend.

## Frontend handoff

1. **Discover** — `GET /api/cases`. Render Ukraine's elements; only those with
   `status: "available"` are clickable. Follow `studies[].endpoint`.
2. **Load the study** — `GET /api/air/kyiv` once; everything below is in it.
3. **Map** — draw `map.study_boundary` (GeoJSON, `[lon, lat]` order) as the
   only shape and fit the view with `map.bounds` (`[[south, west], [north,
   east]]`, Leaflet `fitBounds` order). `sampled_grid_center_extent` is
   optional context; label it as grid-center bounds, not a footprint. There is
   no pollution heatmap: show `map.note` near the map.
4. **Charts** — `charts` lists only charts that are ready to load; an
   unavailable chart is omitted (and reported by `/api/health`). Use each `charts[].url` as an `<img src>` (prefix the API base
   URL), with `title` as caption. `contract.data_csv_path` names the CSV behind
   each figure if interactive charts come later.
5. **Results** — read numbers from `result`:
   - Seasonal differences: `result.comparisons.*` (headline:
     `highlights.seasonal_differences.headline_comparison_id`), both baselines,
     plus `result.coverage_sensitivity` and `result.matched_months`.
   - Multi-year trend: `result.statistics.multi_year_seasonality_aware_trend`
     (`pre_invasion`, `full_record`). Keep this visually separate from the
     seasonal differences; they answer different questions.
   - Coverage: `result.monthly_series[].valid_days / calendar_days`,
     `flagged_below_50_pct`. `highlights.coverage_warnings` lists target-season
     months below 50% (April 2022: 8/30 days); show it next to the headline.
   - Significance: render `highlights.notices` verbatim. `null` means "not
     available" — display "not assessed", never 0 or a blank.
   - Sources and caveats: `result.dataset` (provider, product, Giovanni
     reproducibility URL) and `result.limitations` (render all items).
6. **Conclusion text** — take wording from
   [air-findings.md](air-findings.md) §4, reviewed by G. The API deliberately
   does not author conclusions.
7. **Readiness** — on `503`, show `error.message` and point to `/api/health`.

Large numbers are in molecules/cm² (`~10¹⁵`); format them in the UI.

## Tests

```bash
python -m pytest backend/tests -q                 # backend (54 tests)
python -m unittest discover -s tests -v           # existing analysis tests
```
