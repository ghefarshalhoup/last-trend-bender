# Fire / Hotspot Activity Findings — Ukraine (`FIRMS VIIRS S-NPP SV-C2`, 2019–2022)

**Status:** `validated_descriptive_with_limitations` | **Inferential p-values:** `not_assessed` | **Causal attribution:** `not_established`  
**Machine-readable export:** [`reports/fire_viirs_results.json`](../reports/fire_viirs_results.json) ([schema](fire-results-schema.md))  
**Methods & provenance:** [`docs/fire-methods.md`](fire-methods.md) | **Regenerate all outputs:** `python -m src.fire_analysis`

---

## 1. Did Hotspot Amount and Location Change in 2022?

**Yes in spatial concentration and sector composition; mixed — NOT a uniform national surge — in raw aggregate totals.** Testing the question objectively without assuming an increase reveals three contrasting signals that national totals alone would hide:

1. **Unfiltered national counts declined (`-23.95%`), pushed down by both industrial shutdowns and a huge 2019–2020 pre-war spring wildfire baseline:**
   - All FIRMS types combined (`types 0, 2, 3`, March–August): `69,745` (`2019`), `75,589` (`2020`), `32,896` (`2021`) → `45,179` (`2022`). Relative to the `2019–2021` 3-year mean (`59,410.0`), 2022 was **`-23.95%`** (active-day rate `-16.71%` after adjusting for 16 missing satellite days), even though it rose `+37.34%` above unusually quiet `2021`.
   - **Static industrial thermal sources (`type=2`) collapsed `-77.48%` nationwide** (`11,649` in 2019, `10,344` in 2020, `9,033` in 2021 → **`2,329`** in 2022; `-84.61%` inside the Donbas–Kharkiv corridor), consistent with heavy industrial plant shutdowns/destruction (such as Mariupol steelworks and Kryvyi Rih furnaces). Mixing `type=2` with `type=0` depresses East corridor percentage changes from `+52.26%` to just `+8.56%`.
2. **National vegetation/open fire hotspots (`type=0`) were slightly below the 2019–2021 mean overall (`-11.01%`), nearly flat after outage adjustment (`-2.54%` per observed day), and slightly up in May–August (`+3.96%` count; `+18.40%` rate/day):**
   - `type=0` totals: `56,222` (`2019`), `63,707` (`2020`), `22,497` (`2021`) → **`42,248`** (`2022`), giving `-11.01%` vs. the `2019–2021` mean (`47,475.33`), `251.48` vs. `258.02` detections/observed day (`-2.54%`), and `+87.79%` above `2021`.
   - Restricting to **`nominal + high` confidence** (`93.8%–95.7%` of `type=0` rows) yields virtually identical changes (`-12.08%` count, `-3.70%` rate/day nationally; `+50.53%` count / `+64.86%` rate/day in East Frontline).
3. **Strong spatial redistribution toward eastern and southern frontline corridors alongside sharp declines in Central Interior and Western agricultural regions:**
   - Across `1,307` populated `0.25°` cells nationwide (`type=0`), **`312`** cells increased and **`988`** decreased relative to `2019–2021`, yet every one of the top 8 largest grid-cell increases (`+405.7` to `+683.7` detections per cell) clustered tightly along the **Donbas–Kharkiv–Izium–Sievierodonetsk corridor (`48.875–49.375°N, 37.125–38.625°E`)**, while the top grid-cell decreases (`-130.7` to `-219.0`) lay largely in northern Polesia/Chornobyl-era 2019–2020 burn cells (`50.625–51.625°N, 27.125–31.625°E`) and calmer Dnipropetrovsk–Donetsk western margins.

---

## 2. Regional Breakdown Across Proposed Regions (`type=0`, Open/Vegetation Fire)

> **Status note:** Sub-national boxes below are **proposed candidate boundaries awaiting team agreement**, NOT validated causal controls. Full table in [`reports/fire_regional_summary.csv`](../reports/fire_regional_summary.csv) and Visual [`reports/fire_monthly_comparison.png`](../reports/fire_monthly_comparison.png).

| Region (`region_id`) | Role | `2019` | `2020` | `2021` | `2022` | `2019–21` Mean | `2022` vs `19–21` (`Mar–Aug`) | `Rate/ObsDay` % (`Mar–Aug`) | `2022` vs `19–21` (`May–Aug` / `Rate%`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Ukraine National** (`ukraine_national`) | National aggregate | 56,222 | 63,707 | 22,497 | 42,248 | 47,475.33 | **-11.01%** | **-2.54%** | +3.96% / +18.40% |
| **East Frontline Corridor** (`donbas_kharkiv_east`) | Proposed study | 11,727 | 18,044 | 5,836 | 18,072 | 11,869.00 | **+52.26%** | **+66.76%** | +57.82% / +79.74% |
| **South Steppe Corridor** (`south_steppe_belt`) | Proposed study | 7,209 | 3,899 | 3,820 | 5,946 | 4,976.00 | **+19.49%** | **+30.87%** | +13.71% / +29.51% |
| **North / Kyiv Belt** (`kyiv_north_belt`) | Proposed study | 10,278 | 13,705 | 2,120 | 6,253 | 8,701.00 | **-28.13%** | **-21.29%** | **+88.81% / +115.03%** |
| **Kyiv `NO2` Box (`0.5°`)** (`kyiv_no2_box`) | Cross-layer box | 129 | 127 | 24 | 166 | 93.33 | **+77.86%** | **+94.80%** | -61.29% / -55.91% |
| **Central Interior Steppe** (`central_interior_cand`) | Candidate ref | 12,964 | 10,607 | 5,747 | 4,004 | 9,772.67 | **-59.03%** | **-55.13%** | -75.54% / -72.15% |
| **Western Ukraine** (`west_ukraine_cand`) | Candidate ref | 9,660 | 11,341 | 3,137 | 6,075 | 8,046.00 | **-24.50%** | **-17.31%** | -45.73% / -38.19% |

Key seasonal dynamics visible in [`reports/fire_monthly.csv`](../reports/fire_monthly.csv):
- **March 2022 Kyiv / North spike followed by post-withdrawal drop:** `kyiv_north_belt` recorded `4,326` `type=0` detections in March 2022 (`144.20/obs day` vs. `843` in March 2021), dropping to `139` in April 2022, though May (`980`) and August (`542`) still ran above `2019–2021` baseline levels (`May–Aug +88.81%`). In the tiny `kyiv_no2_box` matching the Air analysis, `154` of `166` total 2022 hotspots occurred in **March 2022** alone (`5.13/obs day` vs. `5` detections in March 2021), falling to just `8` total hotspots across May–August (`-61.29%`). That temporal contrast aligns chronologically with fighting around Kyiv in March, but without weather controls or ground incident linkage it remains descriptive only.
- **Persistent May–August elevation in the East:** `donbas_kharkiv_east` stayed elevated every month from March through August (`3,617` Mar, `1,569` Apr, `2,749` May, `2,472` Jun, `3,700` Jul, `3,965` Aug), even before rate-adjusting August (`188.81/obs day` over `21` observed days). Meanwhile, neighboring `central_interior_cand` dropped to `-75.54%` in May–August.

---

## 3. Pre-2022 Comparability of Proposed Study & Reference Regions

Across `18` pre-invasion months (`2019–2021` Mar–Aug, `type=0`), **Ukraine contains two fundamentally distinct pre-war fire regimes**, making single-national or mismatched internal reference regions misleading ([`reports/fire_comparability_matrix.csv`](../reports/fire_comparability_matrix.csv)):

- **Regime A — Summer steppe & harvest/dry-grass burn belt (June–August dominated):** Pre-2022 June–August share is **`67.72%`** in East Frontline, **`87.13%`** in South Steppe, and **`55.44%`** in `central_interior_cand`. Accordingly, `central_interior_cand` aligns well with **`donbas_kharkiv_east` (`r = 0.8120`, `rho = 0.9009`, `"strong_pre2022_seasonal_alignment"`)** and moderately with **`south_steppe_belt` (`r = 0.7124`, `rho = 0.8039`)**.
- **Regime B — Spring agricultural & woodland burn belt (March–April dominated):** Pre-2022 June–August share is only **`9.66%`** in `kyiv_north_belt`, **`20.36%`** in `kyiv_no2_box`, and **`17.41%`** in `west_ukraine_cand` (largely driven by March–April agricultural/peat/Chornobyl-zone fires in 2019–2020). Thus `west_ukraine_cand` aligns strongly with **`kyiv_north_belt` (`r = 0.8938`, `rho = 0.9216`)** and **`kyiv_no2_box` (`r = 0.9219`, `rho = 0.6510`)**, whereas cross-regime pairings (e.g., East vs. West `r = 0.2795`, South vs. West `r = -0.1243`) fail pre-2022 comparability.
- **Crucial caveat on internal references:** Even climate-matched internal zones (`central_interior_cand`, `west_ukraine_cand`) experienced nationwide war disruptions (curfews, ruined/suspended spring agricultural burning, fuel shortages, displaced labor, missile strikes, and different regional drought/heat gradients) and are **candidate comparators requiring team decision**, not counterfactual controls.

---

## 4. Observation Gaps, Repeated Detections, and Scope Limitations

1. **July–August 2022 Suomi NPP outage (`16` missing dates):** Zero detections exist across all of Ukraine on `2022-03-05` (`1` day) and continuously across **`2022-07-27`–`2022-08-10`** (`15` days), reducing July 2022 to `26/31` observed days (`83.87%`) and August 2022 to `21/31` days (`67.74%`). Rate-adjusted comparisons (`detections_per_observed_day`) reduce national Mar–Aug `type=0` change from `-11.01%` to `-2.54%` and amplify East Frontline from `+52.26%` to `+66.76%`.
2. **Repeated detections vs. burned area:** Across `2019–2022` `type=0` detections (`184,674` rows), **`40.68%`** of populated `0.01°` cells registered more than one detection overall (`38.22%` in 2022, mean `1.4577` detections per `0.01°` cell-day). Slow-moving or persistent fires accumulate multiple pixels and overpasses, so counts must never be translated into burned hectares or forest-loss totals.
3. **No meteorological covariates or statistical significance claims:** Dryness, temperature, wind, cloud obstruction (fires beneath thick cloud go undetected by VIIRS), and pre-war spring agricultural burn bans are unmodeled; `before_after_seasonal_inference` remains `"not_assessed"`.

---

## 5. Next Decisions Needed

- Confirm which proposed sub-national regions and filter defaults (`type=0 all conf` primary, `type=0 nominal+high` & `May–Aug` sensitivities) the team adopts for the shared presentation and backend API.
- Decide whether late-summer 2022 rate normalization (`detections_per_observed_day`) or explicit outage-exclusion sensitivity (dropping July 27–August 10 across all years) should also be exposed on frontend cards.
