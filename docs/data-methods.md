# NO₂ Data Pipeline & Methodology (`OMNO2d v004`)

## 1. Provenance & Input Specification
- **Product:** NASA Giovanni Area-Averaged Daily Time Series — `OMNO2d v004` (`ColumnAmountNO2TropCloudScreened`), OMI/Aura Level-3 daily gridded (`0.25° × 0.25°`), 30% cloud-screened tropospheric NO₂ vertical column density.
- **Units:** `molecules/cm^2` (vertical column through the lower atmosphere, **not** ground/street-level concentration in $\mu\text{g/m}^3$ or ppb).
- **Spatial selection:** Kyiv study bounding box `west=30.273, south=50.20, east=30.773, north=50.70` (Giovanni snapped `Data Bounding Box: 30.375, 50.375, 30.625, 50.625`).
- **Temporal span:** `2015-03-01` through `2022-08-31` (`2,741` calendar days; `90` months).
- **Raw data policy:** The untouched source CSV is kept local under `data/raw/` (excluded from Git via `.gitignore`) and hashed (`SHA-256`) during every run into `reports/data_quality.json`.

## 2. Processing & Quality Rules
1. **Dynamic Header Discovery:** Scans preamble metadata lines dynamically until locating the tabular header (`time, ...`) rather than skipping a fixed line count.
2. **Fill-Value Conversion:** Extracts the declared fill sentinel (`-1.267651e+30`) from file metadata and converts matching cells to `NaN`. Missing values are never replaced with `0`.
3. **Daily Calendar Reindexing:** Reindexes parsed rows onto the continuous daily calendar (`2015-03-01` to `2022-08-31`), separating **absent dates** (dates omitted from the CSV entirely) from **fill-value rows** (dates present with `-1.267651e+30`).
4. **Negative Value Preservation:** Legitimate small negative OMI retrievals (e.g., retrieval/stratospheric-subtraction noise around low tropospheric NO₂ columns) are preserved rather than clipped or dropped, avoiding positive truncation bias.
5. **Monthly Aggregation & Coverage Flagging:** Computes arithmetic monthly means from valid daily observations alongside `valid_days`, `calendar_days`, and `coverage_fraction = valid_days / calendar_days`. Months with `valid_days == 0` remain `NaN`; months with `valid_days < 10` are flagged as sparse in `reports/data_quality.json` and highlighted visually in `reports/no2_monthly.png` (without silently interpolating gaps).

## 3. Outputs
- `reports/no2_monthly.csv` — Columns: `month, no2_mean_molec_cm2, valid_days, calendar_days, coverage_fraction`
- `reports/no2_monthly.png` — Monthly time series with seasonal (`2018–2021`) context and valid-day coverage bars flagging sparse months
- `reports/data_quality.json` — Raw file hash, extracted Giovanni metadata, exact daily accounting invariants, and sparse-month flags

## 4. Limitations & Interpretation Guardrails
- **Not yet a replication of Ialongo et al. (2023):** [Ialongo et al. (2023)](https://www.nature.com/articles/s41598-023-42118-w) primarily analyzed higher-resolution Sentinel-5P TROPOMI (`3.5 × 5.5 km`), whereas `OMNO2d` bins observations onto a coarser `0.25°` (~25 km) grid affected by the OMI row anomaly. City-center emission drops may therefore appear attenuated by peri-urban averaging.
- **Uneven sampling & sparse months:** Cloud screening and orbital/row-anomaly gaps yield `~52%` overall daily coverage, with `13` sparse months (`valid_days < 10`), including **April 2022 (`8/30` valid days)**, **March 2016 (`4/31` valid days)**, and **November 2020 (`4/30` valid days)**.
- **Non-causal scope:** Tropospheric NO₂ exhibits strong seasonality (higher in winter, lower in summer) and interannual variability (including the 2020 COVID-19 lockdown period). Observed changes in one region alone cannot establish war causation without matched reference controls and meteorological/transport analysis (to be coordinated with G's study specification).

## 5. One-Command Regeneration

Place the raw Giovanni CSV in `data/raw/` (e.g., `data/raw/NASA_Giovanni_NO2_2015-03-01_to_2022-08-31.csv`) and run:

```bash
python -m src.no2_pipeline
```

To run the test suite:

```bash
python -m unittest discover -s tests -v
```
