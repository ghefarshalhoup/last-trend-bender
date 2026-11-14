# Four-Elements Analytical & Statistical Methodology (`kyiv_four_elements`)

## 1. Study Design & Spatial Alignment
To bridge atmospheric composition, active thermal anomalies, hydrology, and land-surface state over the **Ukraine 2022 case** (`conflict_start = 2022-02-24`), this module integrates three NASA/EOSDIS Earth-observation streams across **8 aligned study regions**:

1. `kyiv_no2_box` (`1,968.2 km^2`, primary urban study box aligned with Milestone 1 `OMNO2d v004`)
2. `kyiv_north_belt` (`111,556.5 km^2`, war theater study belt)
3. `donbas_kharkiv_east` (`134,618.7 km^2`, Eastern frontline corridor)
4. `south_steppe_belt` (`146,556.8 km^2`, Southern frontline corridor)
5. `central_interior_cand` (`163,034.7 km^2`, non-frontline Ukraine reference)
6. `west_ukraine_cand` (`176,836.5 km^2`, non-frontline Western reference)
7. `poland_krakow` (`1,973.8 km^2`, external EU meteorological context only)
8. `czechia_prague` (`1,945.2 km^2`, external EU meteorological context only)

## 2. Multi-Sensor Input Data & Physical Derivations
- **Air (Tropospheric NO2):** NASA Giovanni OMI `OMNO2d v004` daily area-averaged cloud-screened tropospheric NO2 (`molec/cm^2`, `2015-03-01` to `2022-08-31`). Missing/fill days (`-1.26765e+30`) remain `NaN` and are never zero-filled. April 2022 has `8/30` (`26.67%`) valid days and is explicitly flagged in all summaries and sensitivity models.
- **Fire (Active Thermal Anomalies):** NASA FIRMS VIIRS S-NPP Science-Quality Archive `VNP14IMGTML` (`"version": "2"` / Collection 2, `375 m` nominal, `Mar–Aug 2019–2022`) split into:
  - `type0_vegetation_nominal_high` (presumed vegetation / land-surface thermal detections, `nominal` + `high` confidence)
  - `type2_static_industrial` (other static land sources; persistent industrial, flare, and power signatures — Collection 2 static-classification caveat verified per cell)
  Primary panel densities normalize by detection-day counts and full rectangular WGS84 box area (`per 1,000 km^2 / day`); an explicit CMR `VNP14IMG` daily granule outage audit (`data/frozen/firms_cmr_vnp14img_daily_2019_2022.json`) and GeoBoundaries `UKR-ADM0` clipped sensitivity (`data/frozen/firms_cmr_matched_audit.json`, matched `169 days/yr` excluding `2022-07-27..2022-08-10` across all years) are also emitted. Notably, CMR proves `2022-03-05` had `8` `VNP14IMG` granules over Ukraine (a valid zero-detection day), whereas **`2022-07-27..2022-08-10`** (`15` days) was the true `0`-granule S-NPP outage.
- **Water, Earth & Air Meteorology (NASA POWER `MERRA-2` & `CERES`):**
  - Monthly (`2015–2022`) sampled across a `3 x 3` latitude/longitude lattice inside each study box and aggregated using **`cos(lat)` spherical cosine weighting** (`fill_value = -999.0` stripped strictly at POWER ingest). This is an explicit `3x3` sampled approximation; dense native-cell verification (`16-pt MERRA-2`, `12-pt CERES`) over `donbas_kharkiv_east` (`96` months) is archived in [`data/frozen/nasa_power/native_grid_vs_3x3_summary.json`](../data/frozen/nasa_power/native_grid_vs_3x3_summary.json).
  - Daily (`2015-01-01..2022-12-31`) fetched at the Kyiv center (`50.45 N, 30.523 E`) for direct day-level alignment with OMI overpasses; elevation difference (`179.0 m` vs POWER SRTM DEM `128.71 m`) shifts PET by `<= 0.0024 mm/day`.
  - Derived physical quantities implemented in [`src/stats_rigor.py`](../src/stats_rigor.py) & [`src/weather_power_pipeline.py`](../src/weather_power_pipeline.py):
    - **Mean Daily Diurnal Bounds (`T2M_RANGE`)**: NASA POWER's monthly `T2M_MAX` / `T2M_MIN` report single-month extremes rather than monthly means of daily highs/lows (`~24 °C` extreme spread vs `~10.5 °C` daily range). We therefore fetch monthly `T2M_RANGE` and reconstruct effective mean daily bounds (`T2M ± 0.5 * T2M_RANGE`) for Tetens VPD and FAO-56 PET, preventing convex saturation-vapor inflation (`0.93 kPa` vs exact daily-mean `0.91 kPa` in July 2022 Kyiv).
    - **Vapor Pressure Deficit (`vpd_kpa`)**: Tetens saturation vapor pressure `0.5 * (e_s(Tmax_day_mean) + e_s(Tmin_day_mean))` minus actual vapor pressure derived from MERRA-2 `QV2M`/`PS` (fallback `RH2M`).
    - **FAO-56 Reference Evapotranspiration (`pet_fao56_mm_day`)**: ASCE/Allen FAO-56 Penman–Monteith equation over a hypothetical well-watered grass surface using strict **`alpha = 0.23`** reference albedo (`use_reference_albedo=True`), astronomical clear-sky solar radiation FAO-56 Eq. (37) `R_so = (0.75 + 2e-5 * z) * R_a` (`use_fao56_clear_sky_rso=True`), monthly soil heat flux `G = 0`, `ALLSKY_SFC_SW_DWN`, `T2M ± 0.5 * T2M_RANGE`, `WS10M`, `PS`, and box elevation.
    - **Climatic Water Balance (`precip_minus_pet_mm_day`)**: `PRECTOTCORR - PET_FAO56` (atmospheric water demand balance only; see [`docs/claim-spec-water.md`](claim-spec-water.md)).
    - **Transpiration Flux Conversion (`evptrns_mm_day`)**: NASA POWER `AG` returns `EVPTRNS` in `MJ/m^2/day`; converted via Bolton latent heat of vaporization `lambda(T) = 2.501 - 0.002361 * T2M`.
    - **Skin–Air Thermal Decoupling (`ts_minus_t2m_c`)**: `TS - T2M`.
    - **Cloud Radiative Attenuation (`cloud_radiative_attenuation_wm2`)**: `(CLRSKY_SFC_SW_DWN - ALLSKY_SFC_SW_DWN) * 11.574074` (`MJ/m^2/day -> W/m^2`).

## 3. Statistical & Causal Safeguards (`src/stats_rigor.py`)
1. **Single-Season Honor (`n = 1` war season):** Because only one post-invasion spring–summer season (`Mar–Aug 2022`) exists, formal year-level before/after hypothesis testing remains `"before_after_significance": "not_assessed"` and standalone causal attribution remains `"causal_attribution": "not_established"`.
2. **Baseline Withholding & Scale-Invariance:** `compute_baseline_climatology_anomalies` strictly withholds periods with `< min_baseline_years` (`2`) as `NaN` rather than falling back to all years; `2015–2019` VIIRS comparisons emit `null` / `"withheld_insufficient_baseline"`. Variables on an arbitrary-zero Celsius scale (`T2M`, `T2M_MAX`, `DTR`, `TS`, `Ts - T2m`, zero-crossing `P - PET`) compute absolute differences only (`"withheld_interval_scale"`). All rank/trend primitives operate strictly without arbitrary `1e-12`–`1e-24` cutoffs (`>= 1e-8` to `1e8` unit-invariance verified) and do not round raw floats prior to Hamed–Rao tie counting.
3. **Candidate Spatial Comparators vs Controls:** `west_ukraine_cand` and `central_interior_cand` are non-frontline Ukrainian spatial comparators (not un-impacted causal controls); `poland_krakow` and `czechia_prague` provide external meteorological context only.
4. **Exploratory Box–Tiao Step & Counterfactual Trajectory:** Fits simultaneous OLS linear trend + `2022-03` step + mean-centered meteorological anomalies (`WS10M`, `CLOUD_AMT`, `T2M`, `PS`) with Marriott–Pope AR(1) `VIF` Student-t standard errors. Both the full `no_step_counterfactual` (`trend + weather ± 95% AR(1) CI`) and three sensitivity specifications (all `90` months `p=0.0373`, excluding sparse April 2022 `p=0.0653`, and `Mar–Aug` only `p=0.1810`) are always reported together.
5. **Autocorrelation-Safe Seasonal Trends & Couplings + Benchmark (`src/reference_benchmark.py`):** Hirsch–Slack covariance-adjusted Seasonal Mann–Kendall + Lehmann–Romano duality-locked 95% CIs across `2015–2022` (verified against `scipy==1.15.3` in [`reports/stats_reference_benchmark.json`](../reports/stats_reference_benchmark.json)), controlled by BH/BY FDR. Cross-element couplings apply AR(1) prewhitening (`e_x = x_t - r1 * x_{t-1}`), lag-window Sidak correction (`-2..+2` months), and BH-FDR. See [`docs/four-elements-reproducibility-audit.md`](four-elements-reproducibility-audit.md).
