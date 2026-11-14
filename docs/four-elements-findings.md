# Key Empirical Findings: Ukraine & Kyiv 4-Elements Synthesis (`2015–2022`)

> **Inference Boundary:** Only one post-invasion spring–summer war season (`Mar–Aug 2022`) is included (`n = 1`). Before/after significance remains `not_assessed`, and standalone causal attribution remains `not_established`. These multi-element diagnostics provide meteorological and regional hydroclimatic context alongside war-period shifts without overclaiming proof (and coarse regional box averages cannot rule out localized drought).

## 1. Kyiv Air (`OMI NO2` + `MERRA-2`/`CERES` Confounder Controls)
- **Raw Monthly Shift (`kyiv_no2_box`, Mar–Aug 2022):** Equal-month mean `1.728e15 molec/cm^2` vs `2.388e15` in `2015–2019` (`-27.64%`) and `2.206e15` in `2019–2021` (`-21.68%`). Under strict grass-reference FAO-56 (`albedo = 0.23`, Eq. 37 `R_so`), Kyiv `pet_fao56_mm_day` shifts from `3.7043` (`2015–2019`) / `3.4768` (`2019–2021`) to `3.3912 mm/day` (`-8.45%` / `-2.46%`), while `2015–2019` VIIRS Fire baselines are strictly withheld (`"withheld_insufficient_baseline"`). Over `Mar–Aug 2022`, Kyiv was cooler (`t2m` `14.06 C` vs `15.19 C` in `2015–2019`, `-1.13 C`), slightly windier (`ws10m` `4.33` vs `4.14 m/s`, `+4.5%`), and slightly cloudier (`58.45%` vs `56.85%`, `+2.81%`).
- **Daily Wind & Cloud Stratification (`Mar–Aug 2022` vs Baselines):**
  - On pre-invasion `2015–2021` valid OMI days, higher daily wind is physically associated with lower NO2 (Spearman `rho = -0.2720`).
  - Filtering strictly to **stagnant low-wind days (`WS10M < 3.0 m/s`)**, Kyiv still records **`-24.42%`** vs `2015–2019` (`24` days in `2022` vs `153` baseline days) and **`-14.96%`** vs `2019–2021` (`103` baseline days).
  - Filtering to **clear/moderate cloud (`CLOUD_AMT < 60%`)** yields **`-22.99%`** vs `2015–2019` (`69` vs `359` days) and **`-21.72%`** vs `2019–2021`.
  - **Excluding `2022-04`** (where OMI had only `8/30` valid days) leaves `n = 98` days in `2022` with **`-28.24%`** vs `2015–2019` (`-20.59%` vs `2019–2021`).
- **Box–Tiao Monthly Step Regression (`2022-03` onset — full `no_step_counterfactual = trend + weather`):**
  - Unadjusted deseasonalized NO2 step (`n = 90` months): `delta = -5.868e14 molec/cm^2`, `R^2 = 0.080`, `resid AR(1) = 0.1626`, `p_ar1 = 0.0572`.
  - **Adding MERRA-2 Meteorology (`WS10M`, `CLOUD_AMT`, `T2M`, `PS`)** raises explained variance **4.5x** (`R^2 = 0.3627`), eliminates residual autocorrelation (`resid AR(1) = 0.0000`), and retains a step drop of `delta = -4.949e14 molec/cm^2` (`p_ar1 = 0.037281`).
  - **Mandatory Sensitivity Reporting:** Excluding sparse `2022-04` (`n = 89`) yields `delta = -4.709e14`, `R^2 = 0.3398`, **`p_ar1 = 0.065276`**; restricting strictly to matched `Mar–Aug` months (`n = 48`) yields `delta = -3.268e14`, `R^2 = 0.5064`, **`p_ar1 = 0.180953`** — demonstrating why `n = 1` war season is not statistically definitive alone.
- **External EU Weather Context:** Over `Mar–Aug 2022` vs `2015–2019`, Krakow (`cloud 64.6 -> 59.5%`, `vpd 0.631 -> 0.680 kPa`, `ws10m 3.73 -> 3.47 m/s`) and Prague (`cloud 66.5 -> 59.8%`, `vpd 0.730 -> 0.764 kPa`) were sunnier, calmer, and slightly drier while Kyiv became cooler and cloudier (`vpd 0.774 -> 0.665 kPa`, `-14.1%`) — underscoring why local meteorological adjustment is essential.

## 2. Sub-National Fire-Weather × Hydroclimate Detection Contrasts (`Mar–Aug 2022` vs `2019–2021`)
Standard fire-weather intuition predicts hotter, drier regions record elevated presumed-vegetation detections (`type0`). Across the six Ukrainian analysis boxes (all labeled strictly as spatial study/comparator regions, **not** causal controls), box-level thermal anomaly density changes do not follow a uniform regional evaporative-drying pattern:

| Region | Box Area (`km^2`) | `type0` Presumed Veg. Rate Change (Panel) | Matched `169d` `UKR-ADM0` `type0` Change | `type2` Static Land Source Change (Panel) | `ΔVPD` (`kPa`) | `ΔGWETTOP` | `ΔT2M` (`°C`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Donbas–Kharkiv East (`donbas_kharkiv_east`) | 134,618.7 | **+72.44%** (`0.446 -> 0.769`) | **+104.30%** | **-83.27%** (`0.225 -> 0.038`) | +0.052 | +0.005 | -0.39 |
| South Steppe Belt (`south_steppe_belt`) | 146,556.8 | **+42.90%** (`0.162 -> 0.232`) | **+59.53%** | **-57.87%** (`0.009 -> 0.004`) | +0.054 | -0.015 | -0.31 |
| Kyiv North Belt (`kyiv_north_belt`) | 111,556.5 | -25.12% (`0.419 -> 0.314`) | -26.85% | -100.00% (`0.001 -> 0.000`) | -0.067 | +0.027 | -0.79 |
| Kyiv NO2 Box (`kyiv_no2_box`) | 1,968.2 | +83.03% (`0.252 -> 0.461`) | +84.09% | `n/a` (`0.000 -> 0.000`) | -0.030 | -0.008 | -0.73 |
| Central Interior Comparator (`central_interior_cand`) | 163,034.7 | **-55.83%** (`0.310 -> 0.137`) | -50.63% | -69.62% (`0.132 -> 0.040`) | **+0.058** | -0.028 | -0.28 |
| West Ukraine Comparator (`west_ukraine_cand`) | 176,836.5 | **-22.18%** (`0.242 -> 0.188`) | -21.44% | -42.45% (`0.016 -> 0.009`) | **+0.137** | -0.043 | +0.11 |

- **Interpretation & Scope Limits:** Across box-level regional averages, Western & Central Ukraine comparators showed stronger mean evaporative drying (`+0.058` to `+0.137 kPa` VPD, topsoil `-0.028` to `-0.043`) alongside *declining* presumed-vegetation detections (`type0` `-22.18%` and `-55.83%` panel; `-21.44%` / `-50.63%` matched `169d` `UKR-ADM0`). Meanwhile, the Donbas–Kharkiv box showed smaller coarse mean weather shifts (`+0.052 kPa` VPD, `z = +0.087 SD`, topsoil `+0.005`, `-0.39 C`), while `type0` detection rates increased **`+72.44%`** (`+63.89%` using CMR observed days; **`+104.30%`** on matched `169d/yr` `UKR-ADM0` land area) and `type2` static land detections fell **`-83.27%`** (`-82.91%` matched). Coarse `0.5° × 0.625°` regional box averages provide meteorological context only and cannot rule out localized or sub-monthly drought. Hotspot counts do **not** measure burned hectares or prove physical cause, and Water/Earth metrics reflect background hydroclimate rather than war-caused contamination or land destruction (see [`docs/claim-spec-water.md`](claim-spec-water.md) & [`docs/claim-spec-earth.md`](claim-spec-earth.md)).

## 3. Multiple-Testing Guardrails & Physical Couplings (`2015–2022`)
- **8-Year Kyiv Seasonal MK Trends:** Across all non-fire metrics, Benjamini–Hochberg FDR `q >= 0.5` (`0` false-discovery multi-year climate trend claims over an 8-year window).
- **Verified Prewhitened Cross-Element Couplings (`BH-FDR <= 0.05`):**
  - Kyiv `prectotcorr -> gwettop` (lag `0` mo): `tau = +0.4446`, `q = 0.0000`
  - Kyiv `prectotcorr -> gwetroot` (lag `0` mo): `tau = +0.3554`, `q = 0.0000`
  - Kyiv `gwettop -> vpd_kpa` (lag `0` mo): `tau = -0.4262`, `q = 0.0000`
  - Kyiv `t2m -> no2_mean_molec_cm2` (lag `0` mo): `tau = +0.2875`, `q = 0.0005`
  - Donbas `prectotcorr -> gwetroot` (lag `0` mo): `tau = +0.3241`, `q = 0.000024`
  - West Ukraine `gwettop -> vpd_kpa` (lag `0` mo): `tau = -0.4352`, `q = 0.0000`
