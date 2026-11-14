# Reference check: Ialongo et al. (2023)

Checked 14 November 2026 against the article's Results, Materials and methods, and discussion of Supplementary Fig. 7.

## Recorded evidence

[Ialongo, I., Bun, R., Hakkarainen, J., Virta, H. & Oda, T. *Satellites capture socioeconomic disruptions during the 2022 full-scale war in Ukraine*. Scientific Reports 13, 14954 (2023)](https://www.nature.com/articles/s41598-023-42118-w). DOI: 10.1038/s41598-023-42118-w.

| Item | Paper record |
| --- | --- |
| Instruments | Sentinel-5P/TROPOMI for detailed NO₂; Aura/OMI for longer-term NO₂. Supporting data: OCO-2 CO₂, VIIRS fires and Sentinel-2 imagery. |
| Locations | Ukrainian cities and industrial sources, including Kyiv, Donetsk and Dnipro/Zaporizhzhia. OMI examines these three areas. |
| Dates | TROPOMI March–August maps: 2019–2022; quarterly reference: 2018–2021 (2018 Q3–Q4 only). OMI spring–summer series: 2015–2022. |
| Comparison | TROPOMI: area-weighted 1-km maps, site observations within 4 km, matched-quarter anomalies, and wind-speed sensitivity below 3 m/s. OMI: 0.25° grid; baselines 2015–2019 and 2019–2021. |
| Main finding | TROPOMI April–June 2022 NO₂ was 15–46% lower across selected sources versus matched reference quarters. OMI Kyiv spring–summer NO₂ was 32% lower versus 2015–2019. |

Source locations: Methods, “TROPOMI and OMI NO₂ product description and data processing”; Results, “Substantial NO₂ reductions observed over Ukraine”; Table 1 and Supplementary Fig. 7 discussion. [Publisher PDF](https://www.nature.com/articles/s41598-023-42118-w.pdf).

## Project decision

Use **related comparison** as the current label. Our OMI route is relevant, but a similar instrument and date range do not establish numerical reproducibility. The reported reductions above are published findings, not results from our CSV or targets to tune toward.

Before claiming reproduction of the OMI Kyiv result, Husam and G must verify:

- Exact OMI product/version and variable, including the cloud screen.
- The paper's OMI spatial mask or bounding box and its relation to our chosen window.
- Spatial weighting and temporal aggregation, including baseline-year weighting.
- Missing-data handling and comparable sampling coverage.

The inspected main-text description does not establish all those implementation details. The supplementary figures themselves have not been independently inspected in this check; the Fig. 7 result above is recorded from the main-text discussion. Author data/code or further supplementary review may be needed to close the gaps.

The TROPOMI site radius and wind sensitivity belong to that component of the paper; our exported regional OMI series cannot be treated as an implementation of those steps.

## Handoff

Follow [study-spec.md](study-spec.md) for the proposed first analysis. Keep disagreements with the paper documented. Present measured differences and limitations separately from any causal interpretation.
