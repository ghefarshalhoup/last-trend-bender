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
- **Fire (Active Thermal Anomalies):** NASA FIRMS VIIRS S-NPP `SV-C2` (`375 m` nominal, `Mar–Aug 2019–2022`) split into:
  - `type0_vegetation_nominal_high` (vegetation/unclassified fires)
  - `type2_static_industrial` (static industrial hotspots, flares, and smelters)
  Normalized per observed satellite day (accounting for known `2022` S-NPP orbit outage days) and per `1,000 km^2` of spherical WGS84 box area.
- **Water, Earth & Air Meteorology (NASA POWER `MERRA-2` & `CERES`):**
  - Monthly (`2015–2022`) sampled across a `3 x 3` latitude/longitude lattice inside each study box and aggregated using **`cos(lat)` spherical cosine weighting**.
  - Daily (`2015-01-01..2022-12-31`) fetched at the Kyiv center (`50.45 N, 30.525 E`) for direct day-level alignment with OMI overpasses.
  - Derived physical quantities implemented in [`src/stats_rigor.py`](../src/stats_rigor.py) & [`src/weather_power_pipeline.py`](../src/weather_power_pipeline.py):
    - **Mean Daily Diurnal Bounds (`T2M_RANGE`)**: NASA POWER's monthly `T2M_MAX` / `T2M_MIN` report single-month extremes rather than monthly means of daily highs/lows (`~24 °C` extreme spread vs `~10.5 °C` daily range). We therefore fetch monthly `T2M_RANGE` and reconstruct effective mean daily bounds (`T2M ± 0.5 * T2M_RANGE`) for Tetens VPD and FAO-56 PET, preventing convex saturation-vapor inflation (`0.93 kPa` vs exact daily-mean `0.91 kPa` in July 2022 Kyiv).
    - **Vapor Pressure Deficit (`vpd_kpa`)**: Tetens saturation vapor pressure `0.5 * (e_s(Tmax_day_mean) + e_s(Tmin_day_mean))` minus actual vapor pressure derived from MERRA-2 `QV2M`/`PS` (fallback `RH2M`).
    - **FAO-56 Reference Evapotranspiration (`pet_fao56_mm_day`)**: ASCE/Allen FAO-56 Penman–Monteith equation using net radiation proxy from `ALLSKY_SFC_SW_DWN`, `T2M ± 0.5 * T2M_RANGE`, `WS10M`, `PS`, and box elevation.
    - **Climatic Water Balance (`precip_minus_pet_mm_day`)**: `PRECTOTCORR - PET_FAO56`.
    - **Transpiration Flux Conversion (`evptrns_mm_day`)**: NASA POWER `AG` returns `EVPTRNS` in `MJ/m^2/day`; converted via Bolton latent heat of vaporization `lambda(T) = 2.501 - 0.002361 * T2M`.
    - **Skin–Air Thermal Decoupling (`ts_minus_t2m_c`)**: `TS - T2M`.
    - **Cloud Radiative Attenuation (`cloud_radiative_attenuation_wm2`)**: `(CLRSKY_SFC_SW_DWN - ALLSKY_SFC_SW_DWN) * 11.574074` (`MJ/m^2/day -> W/m^2`).

## 3. Statistical & Causal Safeguards (`src/stats_rigor.py`)
1. **Single-Season Honor (`n = 1` war season):** Because only one post-invasion spring–summer season (`Mar–Aug 2022`) exists, formal year-level before/after hypothesis testing remains `"before_after_significance": "not_assessed"` and standalone causal attribution remains `"causal_attribution": "not_established"`.
2. **Interval-Scale Percent Suppression:** Variables on an arbitrary-zero Celsius scale (`T2M`, `T2M_MAX`, `DTR`, `TS`, `Ts - T2m`, and zero-crossing `P - PET`) compute absolute differences only (`pct_change = None`, status `"withheld_interval_scale"`).
3. **Daily Wind & Cloud Stratification:** Tests whether `Mar–Aug 2022` Kyiv NO2 drops persist within calm stagnant days (`WS10M < 3.0 m/s`), ventilated days (`>= 3.0 m/s`), clear/moderate skies (`CLOUD_AMT < 60%`), and when excluding low-coverage `2022-04`.
4. **Exploratory Box–Tiao Step Intervention w/ Meteorology:** Fits simultaneous OLS linear trend + `2022-03` step + mean-centered meteorological anomalies (`WS10M`, `CLOUD_AMT`, `T2M`, `PS`) with Marriott–Pope AR(1) Variance Inflation Factor (`VIF`) Student-t standard errors.
5. **Autocorrelation-Safe Seasonal Trends & Couplings:** Computes Hirsch–Slack covariance-adjusted Seasonal Mann–Kendall + Lehmann–Romano duality-locked 95% CIs across `2015–2022`, controlled by Benjamini–Hochberg (BH) & Benjamini–Yekutieli (BY) FDR. Cross-element couplings apply AR(1) prewhitening (`e_x = x_t - r1 * x_{t-1}`), lag-window Sidak correction (`-2..+2` months), and BH-FDR.
