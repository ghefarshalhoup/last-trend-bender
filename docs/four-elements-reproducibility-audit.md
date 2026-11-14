# Four-Elements Reproducibility & Statistical Audit (`PR #8 Follow-Up`)

This document responds directly to all methodological, reproducibility, provenance, and verification items raised in the PR #8 review (`4fd17d389986a4077688f242b938db951e314200`) for **Be An Earth System Trend Detective!**. Every artifact, hash, and metric below was verified directly against the committed follow-up branch `husam/audit-followup-analysis`.

> **Repository Boundary:** Analytical fixes, frozen provenance, and audit documentation live strictly in this analysis follow-up PR. Interactive UI updates (`web/*`, `src/build_web_bundle.py`) are isolated in a separate stacked UI PR. Milestone 1 API routes (`backend/`), `reports/air_no2_results.json`, and `reports/fire_viirs_results.json` remain completely untouched.

---

## Item 1 — Exact Frozen NASA POWER Evidence & Point Provenance
`.gitignore` now explicitly allows tracked immutable evidence in `data/frozen/`. Both composite POWER caches used to generate `reports/` are frozen byte-for-byte with SHA-256 checksums matching `reports/four_elements_quality.json`, and `src/weather_power_pipeline.py` automatically falls back to `data/frozen/nasa_power/` when `data/raw/nasa_power/` is absent:

| Frozen Artifact | Size (bytes) | SHA-256 Checksum | Purpose |
| --- | ---: | --- | --- |
| `data/frozen/nasa_power/ukraine_power_monthly_2015_2022.json` | 471,726 | `ab4dc36efd2fcb3cbb01fb9e67b96698f7806d1fa72c402413d3d7f3b2a51084` | Exact 8-region × 9-point `MERRA-2`/`CERES` monthly cache (`v2.10.0`, `LST`, fill `-999.0`) |
| `data/frozen/nasa_power/kyiv_power_daily_2015_2022.json` | 932,884 | `5447b5b4ee619b9e2a160b64e8a3ebc2787391cebe3623f4b66f05a1699c28f6` | Exact Kyiv center (`50.45 N, 30.523 E`) daily weather cache (`2,741` days `2015–2022`) |
| `data/frozen/nasa_power/power_point_request_manifest.json` | 50,152 | `8b875945c48da5fdedb3c6c5d700f08cfbabd78b02a93b85c42f727850924897` | Exact 72 monthly `3x3` point URLs, `cos(lat)` weights, API units/headers, timestamps, DEM vs configured elevation |
| `data/frozen/nasa_power/sample_kyiv_center_monthly_batch1.json` | 19,394 | `83c005bd3dd92ebe5685b2bb43af88b88b8847b45639902500f3c0c86532ed7d` | Verbatim upstream NASA POWER monthly Batch 1 JSON response (Kyiv center) |
| `data/frozen/nasa_power/sample_kyiv_center_monthly_batch2.json` | 19,080 | `4fbbeadc2ecefd60e91c888467165e95cbfdbb779381a860581bd48e47a1f654` | Verbatim upstream NASA POWER monthly Batch 2 JSON response (Kyiv center) |
| `data/frozen/nasa_power/sample_kyiv_center_daily_raw.json` | 922,469 | `deb99ef632a22880bc5042f16684a28d0e5a5ce47810ae4878c70f1feeed0b09` | Verbatim upstream NASA POWER daily JSON response (Kyiv center, `elevation = 128.71 m`) |
| `data/frozen/nasa_power/native_grid_vs_3x3_summary.json` | 1,808 | `48b46ab654071760bcfab0674abb1816eef81ed88d1fbccc60f6abbdd46cf119` | `3x3` vs dense `16-pt MERRA-2` / `12-pt CERES` audit + Kyiv DEM & FAO-56 sensitivity |
| `data/frozen/firms_cmr_vnp14img_daily_2019_2022.json` | 18,049 | `b997da3731077b67f7afe6d05ae1150d407a9c04a29b2f84e4c35a1e22c95ff0` | NASA CMR daily `VNP14IMG` granule inventory (`736` Mar–Aug days `2019–2022`) |
| `data/frozen/firms_download_Readme.txt` | 6,947 | `57cbdf28b2a423a94f831ea04870a065052d47b4aff9c228afb53d28a82bef4e` | Original FIRMS Readme confirming `VNP14IMGTML` science archive provenance |
| `data/frozen/firms_cmr_matched_audit.json` | 9,650 | `920d28486b9d7a75e9ef6f874f09b789a450df2c2709dbaa10b54cb3d2f60736` | Matched `169 d/yr` UKR-clipped Fire rates + top `0.01°` `type=2` cell year-by-year table |
| `data/frozen/ukraine_adm0_geoboundaries_simplified.geojson` | 215,443 | `c7266254f5d3994b4fb2019c861cb4f01775b7ad96c949fc84f892d56d9cfa7f` | geoBoundaries `UKR-ADM0-60985579` polygon (ODbL 1.0) |
| `data/frozen/ukraine_adm0_geoboundaries_meta.json` | 1,812 | `e0238d04574e8f9292046ff0504e0ea964ec41a392207b79d6b9271d5a6614e9` | geoBoundaries API metadata (`meanAreaSqKM = 640,065.42`) |
| `data/frozen/spatial_mask_audit.json` | 3,662 | `68d495511ba44afa968a8f53934dee8c66edf3ee6644d40abf57bf73b7d8bb05` | Box-vs-`UKR-ADM0` land fractions, POWER lattice counts, and FIRMS border clipping |

> **Kyiv Elevation Sensitivity:** Using configured `179.0 m` vs POWER SRTM DEM `128.71 m` shifts `pet_fao56_mm_day` across all 96 Kyiv months by at most `0.0024 mm/day` (`native_grid_vs_3x3_summary.json`).

---

## Item 2 — Exact Environment, Clean Regeneration & Rounding/ULP Explanation
- **Pinned Environment (`requirements.txt`, Python `3.10.19`):** `numpy==2.2.6`, `pandas==2.3.3`, `matplotlib==3.10.8`, `scipy==1.15.3`.
- **Single-Command Clean Regeneration (Offline-Reproducible with `data/raw/` or `data/frozen/`):**
  ```bash
  pip install -r requirements.txt
  python -m src.audit_exports && python -m src.four_elements_analysis && python -m src.reference_benchmark
  python -m unittest discover -s tests -p 'test_*.py'
  ```
- **Why CSV Re-ingestion Showed 0.0001 / Two Hamed–Rao Differences (`0.573962 vs 0.571971`, `0.768293 vs 0.741607`):**
  1. `four_elements_monthly_panel.csv` rounds physical series to `4–5` decimal places on CSV export for human readability, whereas `four_elements_analysis.py` computes statistical tests on **unrounded IEEE-754 floats**.
  2. In `allsky_sfc_sw_dwn` (`min_gap = 4.44089e-16`) and `allsky_srf_alb` (`min_gap = 0.0`), the Hamed & Rao (1998) variance ties correction counts exact ties in centered **Kendall ranks (`R_i`)** on deseasonalized values. Rounding an input panel to 4 or 5 decimals merges near-equal monthly anomalies into artificial tie groups (`unrounded_p_hr = 0.571971 -> round_5dec = 0.573962` for `allsky_sfc_sw_dwn`; `0.741607 -> 0.761847` for `allsky_srf_alb`), shifting the modified variance factor `n/n*`.
  3. Quantified in [`reports/stats_reference_benchmark.json`](../reports/stats_reference_benchmark.json): **zero** hypothesis conclusions change (`p > 0.57` throughout; neither metric approaches `p < 0.05` or FDR `q < 0.05`). The engine operates strictly on unrounded floats without artificial tie-merging or tolerance cutoffs.

---

## Item 3 — Custom Statistical Engine Sources & Independent SciPy Benchmark
[`src/stats_rigor.py`](../src/stats_rigor.py) was originally authored using standard numpy/math primitives and now includes an automated verification suite ([`src/reference_benchmark.py`](../src/reference_benchmark.py) -> [`reports/stats_reference_benchmark.json`](../reports/stats_reference_benchmark.json)) checked directly against `scipy==1.15.3`:

| Statistical Method | Primary Literature Reference | SciPy Benchmark Metric | Measured Result (`reports/stats_reference_benchmark.json`) |
| --- | --- | --- | --- |
| **Kendall tau-b & Variance** | Kendall (1975); Helsel et al. USGS | Max `|ours - scipy.stats.kendalltau|` | **`0.0`** |
| **Unit / Scale Invariance** | Exact order-rank definition (zero `1e-12..1e-24` cutoffs) | Max diff across `1e-8` and `1e+8` scaling | **`0.0`** (fixed previous `0.8222 -> 0` bug) |
| **Theil–Sen Slope** | Sen (1968), *JASA*; Theil (1950) | Max `|ours - scipy.stats.theilslopes|` (`slope/yr`) | **`0.0`** |
| **Theil–Sen 95% CI** | Lehmann (1963) / Hollander–Wolfe duality-locked order statistics vs `scipy.stats.theilslopes` normal approx | Empirical 95% CI coverage (`80` Monte Carlo AR/IID trials) | **Both `0.975`** (`ours` uses exact Sen CI bounds rather than SciPy normal approx; hence endpoint diffs exist while empirical coverage matches) |
| **Seasonal MK & Covariance** | Hirsch & Slack (1984), *WRR* 20(6):727; Dietz & Killeen (1981) | Intra-year covariance matrix + normal `erfc` | Zero cutoff distortion; verified via unit tests |
| **Seasonal Homogeneity** | van Belle & Hughes (1984), *WRR* 20(1):127 | Additive `chi^2_total - chi^2_trend` | Exact `chi^2_{m-1}` decomposition |
| **AR(1) Modified MK & VIF** | Hamed & Rao (1998), *J. Hydrol.* 204:182; Marriott & Pope (1954), *Biometrika* | Rank autocorrelation + `n/n*` VIF + small-sample bias correction `(n*r + 1)/(n - 3)` | Verified (`unrounded`, no `1e-15` cutoff) |
| **Student-t Two-Sided p** | Press et al. continued-fraction incomplete beta | Max `|ours - scipy.stats.t.sf*2|` | **`5.425e-14`** |
| **BH & BY FDR Control** | Benjamini & Hochberg (1995); Benjamini & Yekutieli (2001) | Max `|ours - scipy.stats.false_discovery_control|` | **`0.0`** (`BH` and `BY`) |
| **Box–Tiao OLS Step + AR(1)** | Box & Tiao (1975), *JASA* 70(349); Marriott & Pope (1954) | Max `|ours - numpy.linalg.lstsq|` OLS coefficients | **`0.0`** |
| **Piecewise Breakpoint** | Davies (1987), *Biometrika* 74:33; Pettitt (1979) | Supremum F / Davies upper bound + `ΔBIC` | `Davies p = 0.2718, ΔBIC = -4.6` (no false break) |
| **FAO-56 Reference ET** | Allen et al. (1998), *FAO Irrigation & Drainage Paper 56* | Grass `albedo = 0.23`, Eq. (37) `R_so`, monthly `G = 0` | Strict reference compliance (`RMSE = 0.11918 mm/day` vs legacy) |

---

## Item 4 — Independent FIRMS CMR `VNP14IMG` Outage Audit & `type=2` Forensics
1. **Verified S-NPP Granule Coverage (`data/frozen/firms_cmr_vnp14img_daily_2019_2022.json`):** Querying NASA CMR for collection `VNP14IMG` across all `736` March–August days (`2019–2022`, bbox `22.0,44.3,40.3,52.5`):
   - **False outage fixed:** **`2022-03-05` had `8` `VNP14IMG` granules** over Ukraine (`VNP14IMG.A2022064.*`) — zero FIRMS detections on that date reflects valid weather/ground absence of fires, NOT a satellite orbit gap.
   - **Verified true outage:** Strictly **`2022-07-27..2022-08-10`** (`15` consecutive days) returned **`0` `VNP14IMG` granules**, bounded by `7` granules on `2022-07-26` and `9` on `2022-08-11`. (`2021-08-04`: `2` granules; `2022-06-28`: `3` granules.)
2. **Matched-Date Sensitivity (`169 days/yr` excluding `Jul 27–Aug 10` across all `2019–2022`, clipped to `UKR-ADM0`):**

| Region | Panel Monthly Rate Change (`type0_nh`) | CMR Observed-Day Rect Box (`type0_nh`) | Matched `169d` UKR-Clipped (`type0_nh`) | Matched `169d` UKR-Clipped (`type0_all`) | Matched `169d` UKR-Clipped (`type2_all`) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `donbas_kharkiv_east` | `+72.44%` | `+63.89%` | **`+104.30%`** (`0.4669 -> 0.9539`) | **`+107.53%`** | **`-82.91%`** (`0.2868 -> 0.0490`) |
| `south_steppe_belt` | `+42.90%` | `+31.67%` | **`+59.53%`** (`0.1834 -> 0.2926`) | **`+57.94%`** | `-58.18%` |
| `kyiv_north_belt` | `-25.12%` | `-22.07%` | `-26.85%` (`0.5604 -> 0.4099`) | `-26.52%` | `-100.00%` |
| `kyiv_no2_box` | `+83.03%` | `+94.54%` | **`+84.09%`** (`0.2646 -> 0.4870`) | `+83.09%` | `n/a (0 -> 0)` |
| `central_interior_cand` | `-55.83%` | `-55.46%` | `-50.63%` (`0.2996 -> 0.1479`) | `-50.44%` | `-69.11%` |
| `west_ukraine_cand` | `-22.18%` | `-17.79%` | `-21.44%` (`0.3514 -> 0.2760`) | `-21.29%` | `-39.73%` |

3. **`type=2` Provenance & Reclassification Forensics (`firms_download_Readme.txt` + `firms_cmr_matched_audit.json`):** The bundled FIRMS archive Readme verifies **Science-Quality Standard Processing `VNP14IMGTML`** (`"version": "2"` / Collection 2 monthly reprocessed CSV, NOT NRT `VNP14IMGTDL_NRT`). Cell-level `0.01°` year-by-year tracking confirms the top historical static `type=2` cells (metallurgy/industrial corridors in Avdiivka, Kryvyi Rih, Mariupol) dropped sharply in `2022` **without** reappearing as `type=0` detections:
   - `[48.17, 37.70]`: `type=2` `688 (2019), 587 (2020), 465 (2021) -> 28 (2022)`; `type=0`: `1, 0, 2 -> 0`
   - `[47.87, 33.39]`: `type=2` `551, 426, 346 -> 3`; `type=0`: `1, 0, 2 -> 0`
   - `[47.16, 37.56]`: `type=2` `350, 435, 362 -> 0`; `type=0`: `6, 2, 0 -> 0`
   - `[47.09, 37.60]`: `type=2` `423, 428, 280 -> 1`; `type=0`: `0, 1, 0 -> 0`

---

## Item 5 — Spatial Masks, `3x3` Sampled Approximation & Candidate Role Qualification
- **Country-Boundary Mismatch (`data/frozen/spatial_mask_audit.json` vs `UKR-ADM0`):** Rectangular boxes used for POWER include adjacent sea/border cells whereas FIRMS country CSVs clip to Ukraine borders (`pct_firms_inside_ukr_adm0 = 99.53%–100.0%`). Because total box area exceeds Ukrainian land area (`71.7%–93.6%` for regional boxes), rectangular-box area normalization understates true within-Ukraine thermal anomaly density by `1.068x–1.395x` on regional boxes (which divides out in relative `2022 / baseline` `%` ratios, as verified in Item 4).
- **`3x3` Sampled Approximation vs Dense Native Grid (`data/frozen/nasa_power/native_grid_vs_3x3_summary.json`):** Explicitly labeled as a `3x3 cos(lat)` sampled approximation; checked across `96` months in `donbas_kharkiv_east` against a dense `16-pt MERRA-2` (`0.5° × 0.625°`) / `12-pt CERES` (`1.0°`) grid (`T2M RMSE = 0.17039 °C`, `PRECTOTCORR RMSE = 0.10993 mm/day`, `EVPTRNS RMSE = 0.15360 mm/day`, `CLOUD_AMT RMSE = 2.14%`, `ALLSKY_SRF_ALB RMSE = 0.02288`).
- **Role Qualification (`candidate_role_qualification`):** `central_interior_cand` and `west_ukraine_cand` are spatial comparison regions only (NOT un-impacted causal controls, given nationwide airspace closure, displacement, and infrastructure strikes). `poland_krakow` (`1,984.2 km^2`, `0% UKR`) and `czechia_prague` (`1,983.8 km^2`, `0% UKR`) provide weather context only.

---

## Item 6 — Confirmed Code Fixes & Old-vs-New Metrics Reconciliation
| Item | Old Behavior (`origin/main` `4fd17d3`) | New Audited Behavior (`husam/audit-followup-analysis`) | Metric / Output Change (`Mar–Aug 2022`) |
| --- | --- | --- | --- |
| **Insufficient Baseline Fallback** | `compute_baseline_climatology_anomalies` fell back to all years when `< min_baseline_years` (`2`) | Withholds `nan` whenever baseline `< min_baseline_years` (`min_baseline_years = 2` for Fire `2015–2019`) | Kyiv `fire_type0` `2015–2019`: **`0.3479 (+32.5%)` -> `null ("withheld_insufficient_baseline")`**; `fire_type2` `2015–2019`: **`0.0 -> null ("withheld_insufficient_baseline")`** |
| **Sentinel `-900` & Scale Cutoffs** | `-900.0` filter & `1e-12..1e-24` / `round(...,5)` cutoffs in math helpers (`kendall tau -> 0` under `1e-8` rescaling) | `-900.0` stripped solely at POWER ingest; `math.isfinite` & zero scale cutoffs in `stats_rigor.py` | Scale-invariance across `1e-8..1e8` verified (`max diff = 0.0`) |
| **FAO-56 Reference ET** | Substituted CERES `ALLSKY_SRF_ALB` and `CLRSKY_SFC_SW_DWN` `R_so` (`3.8381 / 3.6022 / 3.5202 mm/day`, `-8.28% / -2.28%`) | Strict grass reference **`albedo = 0.23`**, FAO-56 Eq. (37) `R_so`, monthly `G = 0` (`3.7043 / 3.4768 / 3.3912`, `-8.45% / -2.46%`) | `pet_fao56_mm_day` `RMSE = 0.11918 mm/day`, `max_abs = 0.28773 mm/day`; `P - PET`: `-2.2766 -> -2.1428` (`15–19`), `-1.8197 -> -1.6906` (`2022`) |
| **NO2 Step Counterfactual & Sensitivities** | PNG/series plotted weather contribution without linear trend and did not emphasize all 3 p-values together | Emits & plots full **`no_step_counterfactual` (`trend + weather ± 95% AR(1) CI`)**, preserves backward-compat key, and reports all 3 Box–Tiao p-values | `p = 0.037281` (all `90` mo), `p = 0.065276` (excl. `2022-04`, `n=89`), `p = 0.180953` (`Mar–Aug` only, `n=48`) |
| **Fire Labels & Attribution** | Mixed `Vegetation/Conflict`, `Industrial Flares`, `industrial collapse`, `burned +72.4%` | Replaced across CSV/JSON/PNG/docs with **Presumed Vegetation (`type0`)**, **Other Static Land Sources (`type2`)**, **detection-rate change** | Terminology only; also clarifies monthly equal-month NO2 (`-27.64%`) vs daily valid-day pooling (`-27.81%`, `air_no2_results.json` preserved) |
| **Water & Earth Claim Specs** | No formal claim-boundary audit | Explicit 1-page specs (`docs/claim-spec-water.md`, `docs/claim-spec-earth.md`) | Reports hydroclimate context vs missing hydrology/contamination/SAR/burn-scar validation gaps |
