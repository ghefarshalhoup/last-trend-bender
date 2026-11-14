# NO₂ Data Pipeline & Methodology (`OMNO2d v004`)

## 1. Provenance & Input Specification
- **Product:** NASA Giovanni Area-Averaged Daily Time Series — `OMNO2d v004` (`ColumnAmountNO2TropCloudScreened`), OMI/Aura Level-3 daily gridded (`0.25° × 0.25°`), 30% cloud-screened tropospheric NO₂ vertical column density.
- **Units:** `molecules/cm^2` (vertical column through the lower atmosphere, **not** ground/street-level concentration in $\mu\text{g/m}^3$ or ppb).
- **Spatial selection:** Kyiv study bounding box `west=30.273, south=50.20, east=30.773, north=50.70` (Giovanni snapped `Data Bounding Box: 30.375, 50.375, 30.625, 50.625`).
- **Temporal span:** `2015-03-01` through `2022-08-31` (`2,741` calendar days; `90` months).
- **Raw data policy:** The untouched source CSV is kept local under `data/raw/` (excluded from Git via `.gitignore`) and hashed (`SHA-256`) during every run into `reports/data_quality.json` and `reports/air_no2_results.json`.

## 2. Processing, Quality Rules & Comparison Design
1. **Dynamic Header Discovery:** Scans preamble metadata lines dynamically until locating the tabular header (`time, ...`) rather than assuming a fixed line count.
2. **Fill-Value Conversion:** Extracts the declared fill sentinel (`-1.267651e+30`) from file metadata and converts matching cells to `NaN`. Missing values are never replaced with `0`.
3. **Daily Calendar Reindexing:** Reindexes parsed rows onto the continuous daily calendar (`2015-03-01` to `2022-08-31`), separating **absent dates** (`27` omitted CSV dates) from **fill-value rows** (`1,282` cloudy/missing rows).
4. **Negative Value Preservation:** Legitimate small negative OMI retrievals (`43` valid observations) are preserved rather than clipped or dropped, avoiding positive truncation bias.
5. **Monthly Aggregation & Coverage Flagging (`<50%` Proposed Project Rule):** Computes monthly means and `coverage_fraction = valid_days / calendar_days`. Following [study-spec.md](study-spec.md), months with **`coverage_fraction < 0.50`** (`37/90` total months, including **April 2022 with `8/30` valid days = `26.67%`**) are flagged under the proposed project coverage rule; the legacy `<10` valid-day count (`13/90` months) is retained in `reports/data_quality.json` and `reports/air_no2_results.json` for continuity.
6. **March–August Comparisons & Sensitivity:** Compares `March–August 2022` against **Primary (`2015–2019`)** and **Sensitivity (`2019–2021`)** baselines using equal weighting of yearly valid-day seasonal means, alongside `equal-month (1/6)` weighting and identical-remaining-month exclusions (`strict_all_years_unflagged` and `excluding_target_flagged_months`). Percentages are withheld (`null`) if a baseline is nonpositive or missing.
7. **Statistical Assessment:** Before/after seasonal hypothesis testing is explicitly exported as **`not_assessed`** (`n = 1` post-war season, autocorrelated daily rows, no controls/weather). Multi-year seasonality-aware trend slopes (`2015-03`–`2022-02` pre-invasion and `2015-03`–`2022-08` full record) use Month-Fixed-Effects OLS with Newey–West HAC SEs (`lags <= 6`), cross-checked with Seasonal Theil–Sen and Hamed–Rao (1998) modified Mann–Kendall.

## 3. Outputs
- `reports/no2_monthly.csv` — Monthly table (`month, no2_mean_molec_cm2, valid_days, calendar_days, coverage_fraction`)
- `reports/data_quality.json` — Raw file hash, Giovanni metadata, daily accounting invariants, and `<50%` / `<10d` coverage flags
- `reports/air_no2_results.json` — Backend-ready structured JSON ([schema](air-results-schema.md)) containing comparisons, sensitivity checks, statistics (`not_assessed` before/after + trend), chart pointers, and limitations
- `reports/no2_seasonal_comparisons.csv` & `reports/no2_matched_months.csv` — Reusable tabular chart data
- `reports/no2_monthly.png` — Full monthly timeline (`2015–2022`) with `2015–2019` min–max historical variability, Feb 24 2022 marker, and `<50%` coverage panel
- `reports/no2_seasonal_comparison.png` — March–August 2022 vs. both baselines and methodological sensitivity
- `reports/no2_matched_months.png` — Matched calendar-month (`Mar–Aug`) comparison with visible `<50%` flags (`Apr 2022: 8/30d`)
- `docs/air-findings.md` — Narrative findings, sensitivity synthesis, reference-paper comparison, and next data needs

## 4. One-Command Regeneration

Place the raw Giovanni CSV in `data/raw/` (e.g., `data/raw/NASA_Giovanni_NO2_2015-03-01_to_2022-08-31.csv`) and run one command to regenerate all CSVs, JSONs, and charts:

```bash
python -m src.air_analysis
```

To run all unit and integration tests:

```bash
python -m unittest discover -s tests -v
```
