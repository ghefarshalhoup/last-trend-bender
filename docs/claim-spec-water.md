# Claim Specification: Water Element (Ukraine & Kyiv `2015–2022`)

> **Verdict on Water Claims:** Our Water layer quantifies **regional hydroclimatic background conditions and atmospheric water demand**, NOT war-caused hydrological infrastructure damage or water contamination. Direct water-quality and river/reservoir impact telemetry remain **evidence gaps** in the current `2015–2022` dataset.

## 1. Measured Outcomes & Units
All Water metrics originate from NASA POWER (`v2.10.0`, `AG` community, **MERRA-2 `0.5° × 0.625°`** + CERES radiative terms for reference ET):
- `prectotcorr` (`mm/day`): Bias-corrected total surface precipitation.
- `qv2m` (`g/kg`) & `rh2m` (`%`): 2m specific and relative humidity.
- `evptrns_mm_day` (`mm/day`): Vegetation transpiration energy flux (`EVPTRNS`, `MJ/m^2/day`) converted via Bolton latent heat `lambda(T2M)`.
- `vpd_kpa` (`kPa`): Vapor Pressure Deficit from `T2M ± 0.5 * T2M_RANGE` and `QV2M`/`PS`.
- `pet_fao56_mm_day` (`mm/day`): ASCE/Allen FAO-56 Penman–Monteith **grass-reference** evapotranspiration (`alpha = 0.23`, FAO-56 Eq. 37 clear-sky `R_so`, monthly `G = 0`).
- `precip_minus_pet_mm_day` (`mm/day`): Climatic water balance (`PRECTOTCORR - PET_FAO56`; interval-scale, zero-crossing — `%` changes suppressed).

**Observed Kyiv (`kyiv_no2_box`, `Mar–Aug 2022`):** `prectotcorr = 1.7006 mm/day` (`+8.90%` vs `2015–2019`; `-8.78%` vs `2019–2021`), `vpd_kpa = 0.6646 kPa` (`-14.10%` / `-4.36%`), `pet_fao56_mm_day = 3.3912 mm/day` (`-8.45%` / `-2.46%`), `evptrns_mm_day = 1.0103 mm/day` (`-3.74%` / `-9.44%`), and `precip_minus_pet = -1.6906 mm/day` (`+0.4522` / `-0.0780` abs diff).

## 2. Exact Study Area & Temporal Scope
- **Window Retained (`2015–2022`, focus `Mar–Aug 2022`):** 96 monthly steps across 8 aligned regions (`data/frozen/nasa_power/ukraine_power_monthly_2015_2022.json`).
- **Spatial Footprints & Mask Audit:** Rectangular `3 x 3` `cos(lat)` sampled lattices (`data/frozen/spatial_mask_audit.json`): `kyiv_no2_box` (`1,968.2 km^2`, `100.0%` inside `UKR-ADM0`), `donbas_kharkiv_east` (`77.02%`), `south_steppe_belt` (`73.60%`), `kyiv_north_belt` (`78.76%`), `central_interior_cand` (`93.63%`), `west_ukraine_cand` (`71.70%`), plus `poland_krakow` and `czechia_prague` (`0.0%` UKR, meteorological context only).

## 3. Adverse Impact Definition vs. What Can Actually Be Claimed
- **What constitutes an adverse conflict water impact:** Destruction of dams/pumping stations, reservoir drainage, wetland inundation, chemical/munitions/heavy-metal/PFAS contamination, sewage discharge, or turbidity spikes in surface and drinking water.
- **What our dataset supports:** Examining coarse regional evaporative demand (`ΔVPD`, `ΔPET`, `ΔPRECTOTCORR`) alongside spatial differences in 2022 fire detections. Across box-level averages, Western (`west_ukraine_cand`: `ΔPRECTOTCORR -0.616 mm/day`, `ΔVPD +0.137 kPa`) and Central (`-0.305 mm/day`, `+0.058 kPa`) comparators exhibited larger mean increases in atmospheric drying demand than Donbas–Kharkiv (`-0.310 mm/day`, `+0.052 kPa`) and Kyiv (`-0.164 mm/day`, `-0.030 kPa`). Because `0.5° × 0.625°` regional averages smooth local extremes and short dry spells, they do not rule out localized drought; rather, they show that the eastern `type0` surge does not track a simple uniform box-mean atmospheric-drought gradient.
- **What is NOT claimed:** We make **no** claim of war-caused water scarcity, contamination, or hydrological damage from NASA POWER fields.

## 4. Documented Conflict Mechanism vs. Evidence Gap
- Documented warfare mechanisms (shelled water utilities, damaged industrial lagoons, altered irrigation/dam control) act on watersheds, channels, and aquifers at **meter-to-kilometer** scales and are **not represented** in MERRA-2 `0.5° × 0.625°` meteorological assimilation, which reflects synoptic circulation and ERA/gauge precipitation rather than combat infrastructure damage.
- No standalone conflict impact on Kyiv precipitation or `P - PET` is statistically established (`q_bh >= 0.6147` on 8-year Kyiv Seasonal Mann–Kendall trends).

## 5. Comparison / Control Design & Uncertainty
- **Comparators:** `west_ukraine_cand` and `central_interior_cand` are non-frontline Ukrainian **spatial comparators** (subject to airspace/economic/power disruption nationwide — **not** un-impacted causal controls). `poland_krakow` and `czechia_prague` provide EU synoptic weather context only.
- **Uncertainty:** `3 x 3` sampled lattice vs dense native MERRA-2 (`donbas_kharkiv_east`, `96` months): `PRECTOTCORR RMSE = 0.10993 mm/day` (`max = 0.43784`), `EVPTRNS RMSE = 0.15360 mm/day` (`max = 0.63111`). Border/coastal POWER points (`4/9` inside `UKR-ADM0` for Donbas, `5/9` for South Steppe) blend adjacent Russian/Black Sea/EU grid cells. Single post-invasion warm season (`n = 1`).

## 6. Independent Validation Evidence & Explicit Gap Report
| Required Evidence Class for Direct Conflict Water Claims | Present in Current Bundle? | Status / Explicit Gap |
| --- | --- | --- |
| Hydrological station discharge / river gauge series | **No** | Not included; needed to verify flow disruptions |
| Optical/altimetric reservoir & wetland extent (`Sentinel-2 NDWI`, `SWOT`/`ICESat-2`) | **No** | Not included; needed to observe dam/flooding events |
| Water quality remote sensing (turbidity, TSM, Chl-a) or lab assays | **No** | Not included; needed for contamination/sewage claims |
| Geo-located water infrastructure damage logs | **No** | Outside Earth-observation reanalysis scope |
| Physical meteorological/ET audit (`VPD`, FAO-56 `alpha=0.23`, native grid check) | **Yes** | Verified (`PRECTOTCORR -> GWETTOP` prewhitened `tau=+0.445, q<0.001`) |
