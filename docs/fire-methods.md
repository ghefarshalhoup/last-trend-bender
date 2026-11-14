# Fire / VIIRS S-NPP Data & Analytical Methods

**Regenerate all Fire artifacts from local archives:** `python -m src.fire_analysis`  
**Run all unit/integration tests:** `python -m unittest discover -s tests -v`

---

## 1. Input Verification & Archive Provenance

All four supplied archives in gitignored `data/raw/firms_viirs/` were verified read-only without mutating the source ZIP or inner CSV files. Every archive contains Ukraine NASA FIRMS `SV-C2` Suomi NPP VIIRS (`satellite=SNPP`, `instrument=SNPP`, `version=2`) active fire detections spanning `2019`–`2022` for March 1 through August 31 (`184` calendar days per year).

| Year | Archive File | Archive SHA-256 | Inner CSV Member | CSV SHA-256 | Raw Rows | Observed Date Span |
|---:|---|---|---|---:|---:|---|
| `2019` | `DL_FIRE_SV-C2_848862.zip` | `0e3e9c2a7377d94428a454dd4fafec6751d0a3bd5cf253d229deaabb737552ac` | `fire_archive_SV-C2_848862.csv` | `6dc427f13958fae881d8b019916bee7cec4d3319b30d20cab2fa3b3a3795c5c5` | `69,745` | `2019-03-01` .. `2019-08-31` |
| `2020` | `DL_FIRE_SV-C2_848867.zip` | `fdcc91f92c59de78c36f1249f4c66ded549cf2da83f50e01bb0716f94e05ae00` | `fire_archive_SV-C2_848867.csv` | `f272bbf4517f441bbdb842dfddc8d8578855a525a70d74b0b5f3a42f7954f4e9` | `75,589` | `2020-03-01` .. `2020-08-31` |
| `2021` | `DL_FIRE_SV-C2_848869.zip` | `ba708f25f185aa71d33a780e494994d81009d39ee3c88c866acd68e26ce105d1` | `fire_archive_SV-C2_848869.csv` | `e13f893851cdfc0c87658b0f2711ef7133db1f52205a705f19af10730374d57b` | `32,896` | `2021-03-01` .. `2021-08-31` |
| `2022` | `DL_FIRE_SV-C2_848848.zip` | `775ced69653f57267027729e16de8f5e4ec32ec25b48bd239744de71f9829d8b` | `fire_archive_SV-C2_848848.csv` | `fea9f54fb1c29a3b2318e69743cdf98e30df1d277ee716582637839f8b42d194` | `45,179` | `2022-03-01` .. `2022-08-31` |

Required 15 FIRMS `SV-C2` CSV columns checked on every archive: `latitude`, `longitude`, `brightness`, `scan`, `track`, `acq_date`, `acq_time`, `satellite`, `instrument`, `confidence`, `version`, `bright_t31`, `frp`, `daynight`, `type`.

## 2. Validation, Confidence/Type Filtering, and Deduplication Rules

Implemented in [`src/fire_pipeline.py`](../src/fire_pipeline.py):

1. **Coordinate, date, time, and classification validation:**
   - Coordinates must parse cleanly and lie within `[-90, 90]` latitude and `[-180, 180]` longitude; observed nationwide bounds span `44.39951°N–52.35735°N`, `22.13790°E–40.14302°E`.
   - `acq_date` must parse strictly as `YYYY-MM-DD`; `acq_time` is zero-padded to 4 digits (`HHMM`) and verified against valid hours `00–23` and minutes `00–59`.
   - `type` must parse as integer in `{0: presumed_vegetation_fire, 1: active_volcano, 2: other_static_land_source, 3: offshore}`.
   - `confidence` (`l`, `n`, `h`) and numeric fields (`brightness`, `frp`) are validated and audited in `reports/fire_quality.json`. Across the real archives (`223,409` total rows), invalid counts for coordinates, dates, times, types, confidence codes, and numeric fields were all **`0`**.
   - **Non-positive FRP:** `7` rows in 2020 carry `frp = 0.0` (valid FIRMS detection records where sub-threshold brightness prevents an FRP retrieval estimate); they are audited (`nonpositive_frp_rows_retained = 7`) and retained rather than silently deleted.
2. **Exact duplicate removal:**
   - Records are deduplicated on composite spatio-temporal/sensor identity `DEDUP_KEY_COLUMNS = ["latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument", "version"]` (`exact_duplicates_removed = 0` in the 4 real archives).
3. **FIRMS `type` and `confidence` stratification (`FILTER_MODES`):**
   - `type0_vegetation_all_conf` (primary analysis mode): retains `type == 0` (`184,674` rows across 2019–2022) across all confidence levels (`l`, `n`, `h`).
   - `type0_vegetation_nominal_high`: excludes `confidence == 'l'` (`l` represents `4.3%–6.2%` of `type=0` detections by year) as a low-confidence sensitivity test.
   - `all_types_all_conf`: retains `type in {0, 2, 3}` (`223,409` rows; `type=1` is `0` in Ukraine). Reported transparently to show why filtering `type=2` static industrial anomalies (`33,355` rows, mostly metallurgy/flares) matters.
   - `type2_static_industrial`: isolates `type == 2` (`11,649` in 2019, `10,344` in 2020, `9,033` in 2021, falling to `2,329` in 2022) to document industrial shutdown effects separately from landscape fire activity.

## 3. Satellite Observation Gaps & Active-Day Rate Normalization

Because FIRMS archive exports contain only detection rows (not empty swaths), zero-detection calendar days nationwide serve as the observable indicator of satellite outages:

- **2019, 2020, and 2021:** Every single calendar day from March 1 to August 31 (`184 / 184` days per year) recorded detections somewhere in Ukraine (`0` missing dates).
- **2022 (`16` missing dates across all of Ukraine):**
  - `2022-03-05` (`1` day in March → `30 / 31` observed days, `96.77%` coverage)
  - `2022-07-27` through `2022-08-10` (continuous **15-day blackout** spanning late July and early August → July 2022 has `26 / 31` observed days [`83.87%`], and August 2022 has only `21 / 31` observed days [`67.74%`]), aligning with the documented NASA Suomi NPP mid-2022 spacecraft anomaly/outage.
- **Rate adjustment:** For every region, filter mode, month, and seasonal window, [`src/fire_analysis.py`](../src/fire_analysis.py) reports both raw `detections` and `detections_per_observed_day = detections / satellite_observed_days` (where `satellite_observed_days` comes from Ukraine-wide S-NPP active dates so quiet rural sub-regions do not artificially inflate their own denominator). Note that rate division treats missed outage days as having the same daily rate as observed days in that month and remains approximate if peak harvest/fire weather differed inside July 27–August 10.

## 4. Repeated Detections & What Counts Measure

- **What a row is:** One VIIRS `375 m` pixel-center thermal anomaly flagged during a single ascending (daytime) or descending (nighttime) orbital overpass.
- **Repeated detection mechanism:** Swath overlap at mid-latitudes (`~49°N`), twice-daily day/night passes (`daynight = D / N`), large multi-pixel burn fronts, and multi-day active fires cause multiple rows to fall within the same local vicinity.
- **Diagnostic metric:** Rounding detections to a `0.01°` grid (`~1.1 km N–S × ~0.72 km E–W` at `49°N`) yields `unique_0_01deg_cell_days`, `multi_detection_cell_share`, and `mean_detections_per_cell_day` (`1.34–1.47` detections per `0.01°` cell-day for `type=0`, with `29.8%–38.2%` of populated `0.01°` cells receiving `>1` detection in any given year; max single `0.01°` cell across 2019–2022 is `176` for `type=0` and `1,768` for `all_types`, driven by persistent `type=2` steelworks).
- **Mandatory interpretation rule:** Detections count **hotspot pixels/overpasses**, NOT distinct fire ignitions, burned hectares, or forest-loss area.

## 5. Proposed Study & Reference Regions & Pre-2022 Comparability

Because the team has not yet finalized sub-national polygons (`"proposed_region_agreement": "proposed_pending_team_agreement"`), six candidate geographic bounding boxes inside Ukraine plus the national aggregate are evaluated for review in [`src/fire_analysis.py`](../src/fire_analysis.py):

- **Proposed study zones:** `donbas_kharkiv_east` (`46.80–50.30°N, 35.50–40.20°E`), `south_steppe_belt` (`44.40–47.50°N, 30.00–35.50°E`), `kyiv_north_belt` (`50.00–52.40°N, 28.50–34.50°E`), plus cross-layer Air/$\text{NO}_2$ check `kyiv_no2_box` (`50.200–50.700°N, 30.273–30.773°E`).
- **Candidate lower-ground-combat reference zones:** `central_interior_cand` (`47.50–50.00°N, 27.50–35.50°E`) and `west_ukraine_cand` (`47.70–51.80°N, 22.10–27.50°E`).
- **Pre-2022 comparability method (`assess_pre2022_comparability`):** Evaluates monthly `type=0` detection trajectories across all `18` pre-invasion months (`March–August` across `2019, 2020, 2021`) using Pearson correlation (`pre2022_pearson_r`), Spearman rank correlation (`pre2022_spearman_rho`), standardized z-score RMSE (`standardized_anomaly_rmse`), level ratio, June–August seasonal share, and annual coefficient of variation. Tiers: `strong_pre2022_seasonal_alignment` (`r >= 0.80`), `moderate_pre2022_alignment` (`0.60 <= r < 0.80`), `weak_regime_mismatch_not_comparable` (`r < 0.60`), or `not_assessed_zero_variance`.
- **Two seasonal sensitivity windows:** `mar_aug` (all 6 months) and `may_aug` (excluding March–April to test sensitivity to the extreme March–April 2020 wildfires/Chornobyl exclusion-zone fires in Northern and Western Ukraine and the February–March 2022 Kyiv offensive).
- **Inferential statistics (`before_after_seasonal_inference`):** Deliberately kept `"status": "not_assessed"` (`p_value: null`, `statistical_significance_claimed: false`) because only `n = 1` war year (`2022`) is observed against `3` pre-war seasons, pixels are strongly auto-correlated in space and time, 2022 misses 16 observation days, and weather/agricultural covariates are absent.
