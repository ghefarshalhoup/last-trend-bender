# Study brief: NO₂ over Kyiv, March–August 2022

**Status:** proposed analysis design; reference checked 14 November 2026.  
**Owners:** G — study design, research, review and demo; Husam — processing, analysis and reproducibility.

## Question and scope

How did satellite-observed NO₂ over our selected area change during March–August 2022 compared with the same months before the invasion?

Study a fixed window around Kyiv, Ukraine, centered at **50.450°N, 30.523°E**. The requested bounding box is **west 30.273°E, south 50.200°N, east 30.773°E, north 50.700°N**. Giovanni reports sampled grid-center bounds of **30.375°E–30.625°E, 50.375°N–50.625°N**; these describe the selected grid points, not a replacement city boundary or the full satellite footprints.

## Data and provenance

Use NASA Aura's Ozone Monitoring Instrument (**OMI**), daily Level-3 **OMNO2d v004**, 0.25° grid. Variable: **NO₂ Tropospheric Column (30% Cloud Screened)**, identifier `OMNO2d_004_ColumnAmountNO2TropCloudScreened`, units **molecules/cm²**. This is a tropospheric column measurement; it is not a surface concentration or a direct emissions estimate.

Input: the unchanged Giovanni **Time Series, Area-Averaged** CSV, covering **2015-03-01–2022-08-31 UTC**. Preserve its metadata and [reproduction link](https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2015-03-01T00:00:00Z&endtime=2022-08-31T23:59:59Z&bbox=30.273,50.2,30.773,50.7&data=OMNO2d_004_ColumnAmountNO2TropCloudScreened). [Dataset catalogue](https://disc.gsfc.nasa.gov/datasets/OMNO2d_004/summary).

## Comparisons and calculation

**Primary baseline: 2015–2019. Sensitivity baseline: 2019–2021.** These periods are confirmed in the paper's OMI methods; their use in our implementation remains a proposed design. Compare **March–August only** in every year. The secondary baseline includes the pandemic period.

For each year, calculate the mean of valid daily values during March–August, then average those annual means with equal weight across baseline years. Report the 2022 absolute difference and `100 × (2022 mean − baseline mean) / baseline mean`; withhold the percentage if the baseline is nonpositive or missing. Also compare matched calendar-month means and check sensitivity to equal weighting of the six monthly means. These are explicit project aggregation choices; exact agreement with the paper's weighting remains unverified.

## Data quality and interpretation

Convert the declared fill value `-1.267651e+30` to missing; retain absent dates as missing and never substitute zero. The full export contains **2,714 dated rows: 1,282 fill values and 1,432 numeric observations; 27 calendar dates are absent**. Preserve other numeric values, including negatives, pending a documented quality decision.

Report valid days/calendar days for every month. Proposed project rule: flag coverage below 50%; show exploratory values, but review sampling sensitivity before presenting a headline seasonal percentage when any contributing month is flagged. Report unavailable baseline years explicitly.

**Observed changes alone cannot establish their cause.** Weather, cloud-dependent sampling, retrieval uncertainty, long-term trends and pandemic-related activity changes can influence the comparison. This single-region design has no validated control area and cannot quantify war-attributable emissions, exposure or overall environmental damage.

## Reference relationship and delivery

**Classification: related comparison aligned with the paper's OMI component.** Exact reproduction requires matching its spatial selection, product/version, screening and aggregation. See [reference check](reference-check.md), based on [Ialongo et al. (2023)](https://www.nature.com/articles/s41598-023-42118-w), Methods and Supplementary Fig. 7 discussion.

Deliver a monthly CSV, coverage report, comparison chart and documented regeneration command. G reviews the study claims; Husam supplies the reproducible pipeline.
