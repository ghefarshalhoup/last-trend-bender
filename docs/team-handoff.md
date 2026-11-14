# Team handoff: what Husam, G and the frontend each do next

Updated 2026-11-15. Goal: a tool where a user picks a variable and a place, sees the time series, the rate of change, and whether the trend is statistically significant. Non-significant results are fine if we say so plainly.

## State of the build
- **Works now:** the illustrated atlas with Air over Kyiv. One scroll, three tabs: *Long-term trend* (timeline, invasion date, plain verdict, rate with 95% interval, test details behind "How this was tested"), *2022 comparison*, *About*. Two analysis periods: Full record, Before the invasion. 53 unit and 22 browser tests pass.
- **Not yet:** other variables and places in the panel. They need trend results from Husam (below). Until a result exists the UI shows "analysis not assessed" and never invents a verdict.

## Husam: analysis (in this order)
1. Run the trend tests already in `src/stats_rigor.py` on every existing monthly series, for each variable × region × period (`full_record`, `pre_invasion`). Same method as Kyiv NO₂: month fixed effects with Newey-West, seasonal Theil-Sen, Hamed-Rao Mann-Kendall.
2. Write one result per variable × region × period with: `status` (`assessed` / `insufficient_evidence` / `not_assessed`), `slope_per_year`, `ci_low`, `ci_high`, `p_value`, `significant`, `method`, `n_months`.
3. Fire: mark `insufficient_evidence` (four seasons only), unless FIRMS 2015–2018 is cheap to add.
4. About 200 tests means some will look significant by chance: apply BH-FDR and report adjusted p-values next to raw ones.
5. Kyiv NO₂ without the 37 low-coverage months: does the verdict hold? Report it either way.
6. Process G's new NO₂ CSVs (Donbas, Kraków, South steppe, West Ukraine, Prague) with `no2_pipeline`, flag low-coverage months, add trend results.
7. Review `docs/variable-definitions.md` for scientific accuracy.

## G: data and story
1. Download NO₂ from Giovanni for five regions (Donbas and Kraków first). Settings: Time Series, Area-Averaged; OMNO2d v004 30% cloud screened; 2015-03-01 to 2022-08-31; boxes in the region file (W,S,E,N): Donbas `35.5, 46.8, 40.2, 50.3`; Kraków `19.695, 49.8147, 20.195, 50.3147`; South steppe `30.0, 44.4, 35.5, 47.5`; West Ukraine `22.1, 47.7, 27.5, 51.8`; Prague `14.1878, 49.8255, 14.6878, 50.3255`. Do not edit the CSVs. Record product, version, box, dates and download date.
2. Choose two or three guided examples (suggest: Kyiv Air, a Donbas case, and one honest "no significant trend").
3. Review the voice of `docs/variable-definitions.md`.
4. Submission text, demo video.

## Frontend (Claude)
- Variable dropdown from `/api/variables`; named place pins and compare-two-places; "Start guided example"; reading Husam's results; disabling unreviewed combinations; Fire, Water and Earth layers; static packaging and README.

## If time runs out
1. Husam's step 1 (about 200 verdicts) and 2. Donbas and Kraków NO₂ matter most. Everything else is polish.
