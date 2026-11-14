# Claim Specification: Earth Element (Ukraine & Kyiv `2015–2022`)

> **Verdict on Earth Claims:** Our Earth layer measures **coarse reanalysis soil moisture and surface radiation/temperature context**, NOT mechanical soil disturbance, agricultural war damage, or heavy-metal soil pollution. Direct land-destruction evidence remains an **explicit gap** in the `2015–2022` bundle.

## 1. Measured Outcomes & Units
All Earth metrics derive from NASA POWER (`v2.10.0`, **MERRA-2 `0.5° × 0.625°`** land surface tiles and **CERES SYN1deg `1.0°`** broadband radiative fluxes):
- `gwettop` (`0–1` wetness fraction): Modeled surface soil wetness (`0–5 cm` layer).
- `gwetroot` (`0–1` wetness fraction): Modeled root-zone soil wetness (`0–100 cm`).
- `gwetprof` (`0–1` wetness fraction): Modeled full soil profile moisture.
- `ts` (`°C`): Earth skin temperature (interval scale; `%` change suppressed).
- `ts_minus_t2m_c` (`°C`): Land–air thermal decoupling (`TS - T2M`; interval scale).
- `allsky_srf_alb` (`dimensionless`): All-sky surface broadband albedo.

**Observed Kyiv (`kyiv_no2_box`, `Mar–Aug 2022` vs `2019–2021`):** `gwettop = 0.5131` (`-0.0080` / `-1.53%`), `gwetroot = 0.4831` (`-0.0083`), `gwetprof = 0.5157` (`-0.0075`), `ts = 14.4736 °C` (`-0.6482 °C`), `ts - t2m = +0.4140 °C` (`+0.0778 °C`), and `allsky_srf_alb = 0.1517` (`-0.0056` / `-3.53%`).

## 2. Exact Study Area & Temporal Scope
- **Window Retained (`2015–2022`, focus `Mar–Aug 2022`):** 96 monthly observations per region across all 8 study boxes (`data/frozen/nasa_power/ukraine_power_monthly_2015_2022.json`).
- **Spatial Footprints & Mask Audit:** Rectangular boxes sampled via `3 x 3` `cos(lat)` points (`data/frozen/spatial_mask_audit.json`). Box overlap with Ukraine borders (`UKR-ADM0`): `100.0%` for `kyiv_no2_box`, `77.02%` for `donbas_kharkiv_east`, `73.60%` for `south_steppe_belt`, `78.76%` for `kyiv_north_belt`, `93.63%` for `central_interior_cand`, and `71.70%` for `west_ukraine_cand`.

## 3. Adverse Impact Definition vs. What Can Actually Be Claimed
- **What constitutes an adverse conflict Earth impact:** Artillery cratering, trenching, military vehicle soil compaction, unexploded ordnance (UXO)/landmine contamination, conflict burn scars, crop abandonment/unharvested field loss, and heavy-metal/propellant topsoil contamination.
- **What our dataset supports:** Comparing coarse regional reanalysis wetness (`GWETTOP`/`GWETROOT`) alongside active fire detection shifts (`VIIRS type0`). In `Mar–Aug 2022` vs `2019–2021`, `west_ukraine_cand` (`ΔGWETTOP = -0.0432`, `ΔVPD = +0.137 kPa`) and `central_interior_cand` (`-0.0278`) showed larger box-mean topsoil drying than frontline `donbas_kharkiv_east` (`+0.0048`), indicating that `type0` shifts across these large boxes do not follow a simple uniform topsoil-drying gradient (though coarse `~50 km` box averages do not establish absence of localized or short-term drought).
- **What is NOT claimed:** We make **no** claim of war-caused land degradation, soil pollution, or crop loss from MERRA-2/CERES metrics.

## 4. Documented Conflict Mechanism vs. Evidence Gap
- Explosive ordnance craters (`~2–15 m`), armored compaction, fuel/propellant spills, and abandoned agricultural harvests occur at **sub-kilometer plot scales** and are **invisible** to MERRA-2 Catchment Land Surface Model assimilation (`0.5° × 0.625°`), where modeled `GWETTOP`/`GWETROOT` respond predominantly to gridded precipitation and radiative forcing rather than soil disturbance or UXO damage.
- No 8-year monotonic trend in Kyiv soil wetness or albedo is statistically significant (`q_bh >= 0.6147`, Seasonal Mann–Kendall). Physical land–atmosphere consistency is verified via negative `GWETTOP -> VPD` prewhitened coupling in both Kyiv (`tau = -0.426, q < 0.001`) and West Ukraine (`tau = -0.435, q < 0.001`).

## 5. Comparison / Control Design & Uncertainty
- **Comparators:** `west_ukraine_cand` and `central_interior_cand` serve purely as non-frontline spatial comparators (`candidate_role_qualification`), not causal controls unaffected by mobilization or supply disruption.
- **Uncertainty:** Coarse native resolution (`~50 km` MERRA-2 / `~111 km` CERES), `3 x 3` sampling approximation over `donbas_kharkiv_east` (`ALLSKY_SRF_ALB RMSE = 0.02288`, `max = 0.08362` vs dense native grid), out-of-country border/sea grid inclusion, and single post-invasion season (`n = 1`).

## 6. Independent Validation Evidence & Explicit Gap Report
| Required Evidence Class for Direct Conflict Earth / Land Claims | Present in Current Bundle? | Status / Explicit Gap |
| --- | --- | --- |
| High-res optical burn scar mapping (`Sentinel-2 / Landsat dNBR`) | **No** | Absent; required to measure actual burned hectares |
| SAR coherence / structural land disturbance (`Sentinel-1 InSAR / GRD`) | **No** | Absent; required to detect trenching, craters, infrastructure damage |
| High-res agricultural crop-mask / NDVI harvest anomaly (`10–30 m`) | **No** | Absent; coarse CERES albedo cannot separate crop harvest from cloud/snow residuals |
| In-situ soil heavy-metal / PAH / propellant lab sampling & UXO maps | **No** | Outside Earth-observation reanalysis scope |
| Physical soil-climate coupling check (`PRECTOTCORR -> GWETTOP`, `GWETTOP -> VPD`) | **Yes** | Verified (`q_bh <= 0.0001` across regions) |
