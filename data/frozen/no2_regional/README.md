# OMI NO₂ regional raw exports

Downloaded from NASA Giovanni on **2026-11-15**. All five required exports, the requested Kharkiv city candidate, and optional Central Interior are included.

Every export uses **Time Series, Area-Averaged (ArAvTs)**, **OMNO2d v004**, **NO₂ Tropospheric Column (30% Cloud Screened)**, **molecules/cm²**, **daily 0.25°**, and **2015-03-01 00:00:00 UTC through 2022-08-31 23:59:59 UTC**. Giovanni v4.40 was observed. No requests needed splitting.

## Validation

All seven files passed checks for the exact requested bounding box, date metadata, product token, service, daily header, reproduction URL, numeric values, unique increasing dates and first/last dates. Each contains **2,714 daily rows** within the **2,741 calendar-day** window; **27 dates are absent**. Missing dates were not inserted. Existing fill values (`-1.267651e+30`) and all other values, including negative nonfill retrievals, were retained.

Files were renamed by copying their bytes; the raw CSV content was not edited or opened in Excel. SHA-256 hashes in `manifest.json` match the original downloads. This is download and coverage validation, not validation of trends or war attribution.

| Region | Requested box W, S, E, N | Valid days | Fill days | Months under 50% coverage |
| --- | --- | ---: | ---: | ---: |
| donbas_kharkiv_east | 35.5, 46.8, 40.2, 50.3 | 2,435 | 279 | 1/90 |
| poland_krakow | 19.695, 49.8147, 20.195, 50.3147 | 1,372 | 1,342 | 45/90 |
| south_steppe_belt | 30.0, 44.4, 35.5, 47.5 | 2,440 | 274 | 0/90 |
| west_ukraine_cand | 22.1, 47.7, 27.5, 51.8 | 2,452 | 262 | 0/90 |
| czechia_prague | 14.1878, 49.8255, 14.6878, 50.3255 | 1,273 | 1,441 | 46/90 |
| kharkiv_city | 35.98, 49.74, 36.48, 50.24 | 1,454 | 1,260 | 39/90 |
| central_interior_cand | 27.5, 47.5, 35.5, 50.0 | 2,457 | 257 | 0/90 |

Coverage is nonfill daily values divided by calendar days in each month, counting absent dates as unobserved. The 50% threshold is a project warning, not a NASA quality guarantee. `monthly-coverage-check.csv` provides all 630 region-month counts without changing the raw inputs.

## Interpretation and handoff

- These are daily averages over each requested rectangular box, not gridded pollution maps or street-level exposure measurements. Large boxes represent regional conditions; they are not city equivalents or country-clipped boundaries.
- The sampled grid-coordinate bounds differ from the requested bounds. Both are recorded per file in the original header and `manifest.json`; keep them when reporting spatial support.
- Kraków and Prague have low coverage in 45 and 46 of the 90 months, respectively; Kharkiv has 39. Husam must carry those warnings through monthly aggregation and assess whether comparisons remain usable.
- Kraków and Prague are candidate reference areas. Geography alone does not establish that they are valid causal controls. Differences in regional scale, historical behavior, weather and sampling still need assessment.
- Kharkiv city is an additional candidate region, downloaded as requested. Agree its inclusion and region definition with Husam before adding it to the analysis catalog.
- Observed changes alone cannot establish their cause. No new slope, significance test, uncertainty interval or causal finding is claimed here.

## Contents

- Seven `no2_<region_id>_OMNO2d_v004_2015-03_2022-08.csv` files: untouched daily source data.
- `manifest.json`: source filenames, hashes, original metadata, reproduction URLs, sampled bounds, missing dates and monthly coverage counts.
- `monthly-coverage-check.csv`: derived coverage audit only; no monthly NO₂ averages.
- `source-notes.md`: reusable source description.
- `message-to-husam.md`: prepared handoff; not sent to an external service.

Next: feed the daily CSVs through `no2_pipeline`, preserve missingness and coverage warnings, and review comparison suitability before producing frontend findings. Monthly NO₂ averaging belongs in that pipeline.
