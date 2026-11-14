# Key Empirical Findings: Ukraine & Kyiv 4-Elements Synthesis (`2015–2022`)

> **Inference Boundary:** Only one post-invasion spring–summer war season (`Mar–Aug 2022`) is included (`n = 1`). Before/after significance remains `not_assessed`, and standalone causal attribution remains `not_established`. These multi-element diagnostics separate meteorological noise and regional drought signals from war-period shifts without overclaiming proof.

## 1. Kyiv Air (`OMI NO2` + `MERRA-2`/`CERES` Confounder Controls)
- **Raw Monthly Shift (`kyiv_no2_box`, Mar–Aug 2022):** Mean `1.728e15 molec/cm^2` vs `2.388e15` in `2015–2019` (`-27.64%`) and `2.206e15` in `2019–2021` (`-21.68%`). Over the same window, Kyiv was cooler (`t2m` `14.06 C` vs `15.19 C` in `2015–2019`, `-1.13 C`), slightly windier (`ws10m` `4.33` vs `4.14 m/s`, `+4.5%`), and slightly cloudier (`58.45%` vs `56.85%`, `+2.81%`).
- **Daily Wind & Cloud Stratification (`Mar–Aug 2022` vs Baselines):**
  - On pre-invasion `2015–2021` valid OMI days, higher daily wind is physically associated with lower NO2 (Spearman `rho = -0.2720`).
  - Filtering strictly to **stagnant low-wind days (`WS10M < 3.0 m/s`)**, Kyiv still records **`-24.42%`** vs `2015–2019` (`24` days in `2022` vs `153` baseline days) and **`-14.96%`** vs `2019–2021` (`103` baseline days).
  - Filtering to **clear/moderate cloud (`CLOUD_AMT < 60%`)** yields **`-22.99%`** vs `2015–2019` (`69` vs `359` days) and **`-21.72%`** vs `2019–2021`.
  - **Excluding `2022-04`** (where OMI had only `8/30` valid days) leaves `n = 98` days in `2022` with **`-28.24%`** vs `2015–2019` (`-20.59%` vs `2019–2021`).
- **Box–Tiao Monthly Step Regression (`2022-03` onset):**
  - Unadjusted deseasonalized NO2 step (`n = 90` months): `delta = -5.868e14 molec/cm^2`, `R^2 = 0.080`, `resid AR(1) = 0.1626`, `p_ar1 = 0.0572`.
  - **Adding MERRA-2 Meteorology (`WS10M`, `CLOUD_AMT`, `T2M`, `PS`)** raises explained variance **4.5x** (`R^2 = 0.3627`), eliminates residual autocorrelation (`resid AR(1) = 0.0000`), and retains a step drop of `delta = -4.949e14 molec/cm^2` (`p_ar1 = 0.0373`).
  - Excluding `2022-04` (`n = 89`): `delta = -4.709e14`, `R^2 = 0.3398`, `p_ar1 = 0.0653`.
  - Restricted strictly to matched `Mar–Aug` months (`n = 48`): `delta = -3.268e14`, `R^2 = 0.5064`, `p_ar1 = 0.1810` — showing clearly why `n = 1` war season lacks power for stand-alone significance even after weather control.
- **External EU Weather Context:** Over `Mar–Aug 2022` vs `2015–2019`, Krakow (`cloud 64.6 -> 59.5%`, `vpd 1.090 -> 1.348 kPa`, `ws10m 3.73 -> 3.47 m/s`) and Prague (`cloud 66.5 -> 59.8%`, `vpd 1.275 -> 1.407 kPa`) were sunnier, calmer, and drier while Kyiv became cooler and cloudier — underscoring why local meteorological adjustment cannot be skipped.

## 2. Sub-National Fire × Water × Earth Drought-Mismatch (`Mar–Aug 2022` vs `2019–2021`)
Standard drought theory predicts hotter, drier regions burn *more* vegetation. The 6-region Ukraine synthesis shows the opposite spatial pattern:

| Region | Area (`km^2`) | Fire `type0` Shift | Static Flare `type2` Shift | `ΔVPD` (`kPa`) | `ΔGWETTOP` | `ΔT2M` (`°C`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Donbas–Kharkiv East (`donbas_kharkiv_east`) | 134,618.7 | **+72.44%** (`0.446 -> 0.769`) | **-83.27%** (`0.225 -> 0.038`) | +0.045 | +0.005 | -0.39 |
| South Steppe Belt (`south_steppe_belt`) | 146,556.8 | **+42.90%** (`0.162 -> 0.232`) | **-57.87%** (`0.009 -> 0.004`) | +0.109 | -0.015 | -0.31 |
| Kyiv North Belt (`kyiv_north_belt`) | 111,556.5 | -25.12% (`0.419 -> 0.314`) | -100.00% (`0.001 -> 0.000`) | -0.066 | +0.027 | -0.79 |
| Kyiv NO2 Box (`kyiv_no2_box`) | 1,968.2 | +83.03% (`0.252 -> 0.461`) | `n/a` (`0.000 -> 0.000`) | +0.032 | -0.008 | -0.73 |
| Central Interior Ref (`central_interior_cand`) | 163,034.7 | **-55.83%** (`0.310 -> 0.137`) | -69.62% (`0.132 -> 0.040`) | **+0.137** | -0.028 | -0.28 |
| West Ukraine Ref (`west_ukraine_cand`) | 176,836.5 | **-22.18%** (`0.242 -> 0.188`) | -42.45% (`0.016 -> 0.009`) | **+0.225** | -0.043 | +0.11 |

- **Interpretation:** Western & Central Ukraine experienced strong evaporative drying (`+0.137` to `+0.225 kPa` VPD, topsoil loss `-0.028` to `-0.043`) yet vegetation fire detections (`type0`) *declined* (`-22.2%` and `-55.8%`). Meanwhile, the Donbas–Kharkiv frontline experienced near-baseline VPD (`+0.045 kPa`, slight soil wetting `+0.005`, cooler air `-0.39 C`), yet `type0` fires rose **`+72.44%`** while heavy industrial hotspots (`type2`) collapsed **`-83.27%`**.

## 3. Multiple-Testing Guardrails & Physical Couplings (`2015–2022`)
- **8-Year Kyiv Seasonal MK Trends:** Across all 22 non-fire metrics, Benjamini–Hochberg FDR `q >= 0.576` (`0` false-discovery multi-year climate trend claims over an 8-year window).
- **Verified Prewhitened Cross-Element Couplings (`BH-FDR <= 0.05`):**
  - Kyiv `prectotcorr -> gwettop` (lag `0` mo): `tau = +0.4446`, `q = 0.0000`
  - Kyiv `prectotcorr -> gwetroot` (lag `0` mo): `tau = +0.3554`, `q = 0.0000`
  - Kyiv `gwettop -> vpd_kpa` (lag `0` mo): `tau = -0.3362`, `q = 0.00002`
  - Kyiv `t2m -> no2_mean_molec_cm2` (lag `0` mo): `tau = +0.2875`, `q = 0.0005`
  - Donbas `prectotcorr -> gwetroot` (lag `0` mo): `tau = +0.3241`, `q = 0.000024`
  - West Ukraine `gwettop -> vpd_kpa` (lag `0` mo): `tau = -0.4316`, `q = 0.0000`
