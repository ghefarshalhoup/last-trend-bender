# Air / Tropospheric $\text{NO}_2$ Findings — Kyiv (`OMNO2d v004`, 2015–2022)

**Status:** `validated_descriptive_with_limitations` | **Paper alignment:** `related_comparison` ([Ialongo et al., 2023](https://www.nature.com/articles/s41598-023-42118-w))  
**Machine-readable export:** `reports/air_no2_results.json` ([schema](air-results-schema.md))  
**Regenerate all outputs:** `python -m src.air_analysis`

---

## 1. What Changed, Where, and by How Much?

- **Area & product:** NASA Giovanni daily Level-3 `OMNO2d v004` (`ColumnAmountNO2TropCloudScreened`, 30% cloud-screened, `0.25°` grid) over the Kyiv study box requested at `30.273°E–30.773°E, 50.200°N–50.700°N` (Giovanni snapped grid-center bounds `30.375°E–30.625°E, 50.375°N–50.625°N`), spanning `2015-03-01` to `2022-08-31` (`2,741` calendar days; `1,432` valid observations; `1,282` fill-value rows; `27` absent dates; `43` legitimate negative retrievals preserved).
- **Headline March–August 2022 difference (study-spec primary weighting — equal weight across annual valid-day seasonal means):**
  - **vs. Primary Baseline (`2015–2019` March–August):** Decreased from **`2.358 × 10¹⁵`** to **`1.698 × 10¹⁵` molecules/cm²** (**`-6.592 × 10¹⁴` molecules/cm²**, **`-27.96%`**).
  - **vs. Sensitivity Baseline (`2019–2021` March–August, includes pandemic years):** Decreased from **`2.132 × 10¹⁵`** to **`1.698 × 10¹⁵` molecules/cm²** (**`-4.337 × 10¹⁴` molecules/cm²**, **`-20.34%`**).

### Annual Progression & Matched Calendar Months (March–August)

| Year | Valid / Cal Days | Coverage | Valid-Day Mean (`10¹⁵`) | Equal-Month Mean (`10¹⁵`) | Flagged `<50%` Months (Project Rule) |
|---|---:|---:|---:|---:|---|
| 2015 | 118 / 184 | 64.1% | 2.539 | 2.538 | None |
| 2016 | 92 / 184 | 50.0% | 2.381 | 2.459 | `2016-03` (4/31), `2016-05` (13/31), `2016-06` (13/30) |
| 2017 | 102 / 184 | 55.4% | 2.319 | 2.336 | `2017-03` (13/31) |
| 2018 | 124 / 184 | 67.4% | 2.088 | 2.053 | None |
| 2019 | 108 / 184 | 58.7% | 2.461 | 2.553 | `2019-03` (12/31) |
| 2020 | 118 / 184 | 64.1% | 2.115 | 2.169 | `2020-03` (15/31), `2020-05` (13/31) |
| 2021 | 114 / 184 | 62.0% | 1.819 | 1.897 | `2021-03` (15/31), `2021-04` (11/30) |
| **2022** | **106 / 184** | **57.6%** | **1.698** | **1.728** | **`2022-04` (8/30 = 26.7%)** |

Matched monthly comparisons (`reports/no2_matched_months.png`, `reports/no2_matched_months.csv`):
- **March:** `2.361 × 10¹⁵` (`19/31d`, 61.3%) — `-22.07%` vs. `2015–2019` (`3/5` baseline years `<50%`, `2016-03` had `4/31d`), `-7.74%` vs. `2019–2021` (`3/3` baseline years `<50%`). Notably above `2021-03` (`1.811 × 10¹⁵`).
- **April (`<50%` flagged):** `1.822 × 10¹⁵` (**only `8/30` valid days = `26.67%`**) — largest nominal drop (`-37.00%` vs. `2015–2019`, `-33.16%` vs. `2019–2021`), but heavily exposed to clear-sky cloud sampling variance.
- **May:** `1.683 × 10¹⁵` (`18/31d`, 58.1%) — `-25.24%` vs. `2015–2019`, `-22.75%` vs. `2019–2021`.
- **June:** `1.374 × 10¹⁵` (`22/30d`, 73.3%) — `-17.74%` vs. `2015–2019`, `-20.27%` vs. `2019–2021`.
- **July:** `1.435 × 10¹⁵` (`23/31d`, 74.2%, zero flagged baseline years) — `-26.93%` vs. `2015–2019`, `-22.49%` vs. `2019–2021`.
- **August:** `1.692 × 10¹⁵` (`16/31d`, 51.6%, zero flagged baseline years) — `-32.84%` vs. `2015–2019`, `-23.06%` vs. `2019–2021`.

---

## 2. How Sensitive Is the Finding to Baseline, Weighting, Coverage, and Trend Framing?

| Sensitivity Specification | Months Included | `2022` vs. `2015–2019` | `2022` vs. `2019–2021` |
|---|---|---:|---:|
| **Primary weighting (`valid-day`, annual equal weight)** | Mar–Aug | **-27.96%** | **-20.34%** |
| **Equal-month weighting (`1/6` per month)** | Mar–Aug | -27.64% | -21.68% |
| **Excluding `2022`-flagged `April` (`8/30d`) identically across years** | Mar, May–Aug | -24.96% (`valid-day`) / -25.27% (`eq-mo`) | -18.03% (`valid-day`) / -18.71% (`eq-mo`) |
| **Strict intersection (`>=50%` coverage in every compared year)** | `Jul–Aug` (`15–19`), `Jun–Aug` (`19–21`) | -31.91% (`valid-day`) / -30.25% (`eq-mo`) | -23.06% (`valid-day`) / -22.04% (`eq-mo`) |

Key takeaways (`reports/no2_seasonal_comparison.png`):
1. **Baseline choice shifts magnitude by ~7.6 percentage points** (`-27.96%` vs. `-20.34%`) because `2020` (`2.115 × 10¹⁵`) and especially `2021` (`1.819 × 10¹⁵`) were already lower than `2015–2019` (`2.358 × 10¹⁵`).
2. **Weighting (`valid-day` vs. `equal-month`) shifts results modestly (~0.3–1.3 percentage points).**
3. **April 2022 (`8/30d`, `<50%` proposed project flag) accounts for ~2.3–3.0 percentage points of the raw headline drop** — excluding April lowers the reduction to `-24.96%` (`2015–2019`) and `-18.03%` (`2019–2021`). Yet when retaining only months meeting `>=50%` coverage in *every* year (`Jul–Aug` for `2015–2019`, `Jun–Aug` for `2019–2021`), well-sampled mid/late-summer reductions remain `-31.91%` and `-23.06%`.

### Seasonal Before/After Contrast vs. Long-Term Trend Over Time

- **Before/after significance (`March–August 2022` vs. baseline): `not_assessed`.** Only `n = 1` post-invasion season exists, daily deseasonalized anomalies are positively autocorrelated (`lag-1d r = 0.180`, `n = 836` pairs; `lag-3d r = 0.111`), April 2022 is sparse (`8/30d`), and no comparator cities or weather covariates exist. We explicitly withhold any confidence interval or p-value on the seasonal percentage difference.
- **Seasonality-aware multi-year linear trend (Month-Fixed-Effects OLS with Newey–West HAC SEs up to `6`-month lags; cross-checked via Seasonal Theil–Sen and Hamed–Rao 1998 modified Mann–Kendall):**
  - **Pre-invasion (`2015-03` to `2022-02`, `n = 84` months, `df = 71`):** `-1.73 × 10¹³` molec/cm²/yr (`95% CI: [-7.55 × 10¹³, +4.09 × 10¹³]`, `t = -0.59`, `p = 0.555`; Seasonal Theil–Sen `-2.43 × 10¹³`/yr, Hamed–Rao `p = 0.554`). Not statistically distinguishable from zero.
  - **Full record (`2015-03` to `2022-08`, `n = 90` months, `df = 77`):** `-4.18 × 10¹³` molec/cm²/yr (`95% CI: [-9.53 × 10¹³, +1.18 × 10¹³]`, `t = -1.55`, `p = 0.124`, residual lag-1 `r = 0.179`; Seasonal Theil–Sen `-5.08 × 10¹³`/yr, Hamed–Rao `VIF = 1.254`, `p = 0.150`). Including 2022 steepens the downward slope, yet once seasonality and serial correlation are properly modeled it does not cross `p < 0.05` — and a single linear rate blends pre-war variation, pandemic years, and the 2022 disruption.

---

## 3. Comparison with Ialongo et al. (2023) OMI Component

- **Project label:** **`related_comparison`** (not exact replication).
- [Ialongo et al. (2023)](https://www.nature.com/articles/s41598-023-42118-w) reported OMI Kyiv spring–summer 2022 $\text{NO}_2$ **`32%` lower vs. `2015–2019`** (`docs/reference-check.md`), while our exploratory `OMNO2d v004` export shows **`-27.96%`** (or `-31.91%` in strictly well-sampled `Jul–Aug`).
- Direction and rough magnitude agree, **but exact replication is not claimed** because key paper implementation details remain unverified against main-text Methods: the exact OMI product/version and cloud screen, the paper's OMI spatial mask/box boundaries versus our `30.273°E–30.773°E, 50.200°N–50.700°N` box, spatial/temporal weighting rules, and OMI missing-day screening. Our analysis also does not implement the paper's higher-resolution `4-km` Sentinel-5P TROPOMI or `< 3 m/s` wind-speed filtering (`-42.4%` / `-51.5%`).

---

## 4. What Can We Conclude, What Remains Uncertain, and Exact Additional Data Needed

- **Supported conclusion:** Tropospheric vertical column $\text{NO}_2$ over the Kyiv `0.25°` study box during March–August 2022 was lower across all six months than the `2015–2019` and `2019–2021` baselines (`-18%` to `-32%` across seasonal checks), with well-sampled mid/late-summer drops (`July -26.9%`, `August -32.8%` vs. `2015–2019`) that fall near or below the entire `2015–2019` min–max envelope.
- **Unresolved / not established:**
  - **No war causation established:** Temporal drops in one unadjusted region cannot separate armed-conflict disruption from synoptic meteorology, boundary-layer dispersion, cloud-screening selection, or the pre-existing `2020–2021` decline (`2.115 -> 1.819 -> 1.698 × 10¹⁵`).
  - **Not street-level air quality:** Column $\text{NO}_2$ ($\text{molecules/cm}^2$) is not ground-level exposure.
- **Exact additional data needed next:**
  1. **Comparator / reference city Giovanni exports (`OMNO2d v004`, identical `2015-03-01`–`2022-08-31` dates and `±0.25°` box size):** e.g., **Kraków, Poland** (`49.8147–50.3147°N, 19.6950–20.1950°E`) and **Prague, Czechia** (`49.8255–50.3255°N, 14.1878–14.6878°E`) — plus any lower-conflict western Ukrainian comparator or Donetsk / Dnipro–Zaporizhzhia study boxes if extending coverage. Must test pre-2022 trajectory alignment before treating any comparator as a counterfactual control.
  2. **Meteorological covariates (daily wind speed, cloud fraction, boundary-layer height/temperature)** — e.g., NASA MERRA-2 / NASA POWER or ERA5 matched to `2015-03`–`2022-08` — to assess weather confounding and wind sensitivity.
  3. **Level-2 Sentinel-5P TROPOMI (`2018–2022`, Copernicus Data Space)** only if the team chooses to pursue fine-scale `4-km` urban replication.
