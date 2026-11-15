# Project page text (copy into the NASA Space Apps form)

Everything below is English and ready to paste. Items in **[brackets]** need the team.

## Project Name

Environmental Fingerprints of War

## High-Level Project Summary

Environmental Fingerprints of War is a web atlas that turns anyone into an Earth-system trend detective. You pick a place in or near Ukraine and a period, then open up to four NASA variables as cards over an illustrated map. Each card shows the monthly time series, the rate of change per year with its 95% range, and a plain verdict: significant, not significant, or too little data. We built it around one hard question: did the 2022 invasion leave a mark that satellites can see? The honest answer is the point of the tool. Across 348 trend tests on 25 variables, only one place shows a significant long-term trend, and it is Prague, where NO₂ was already falling before the war. Kyiv and Kharkiv lost almost 30% of their NO₂ in spring and summer 2022, but that is a sudden step, not a trend. The atlas teaches the difference between a trend, a shock, and noise, and it never shows a number it cannot defend.

## Link to Project Demo

**[Public link to the 7-slide deck: `docs/submission/demo-deck.pdf` in the repository, or a 30-second video]**

## Link to Final Project

https://github.com/ghefarshalhoup/war-environment-tracker

**[Add the hosted link here if we deploy one.]**

## Detailed Project Description

### What it does

1. **Choose a place and a period.** Nine study places: six regions of Ukraine, Kyiv city, Kharkiv city, and two comparison cities outside the war (Kraków and Prague). Two periods: the full record, or only the months before the invasion.
2. **Choose variables.** 25 variables in four groups, each with a one-sentence definition:
   - **Air:** NO₂, wind, cloud, pressure, sunlight.
   - **Fire:** vegetation fires, industrial heat sources, temperature, evaporation demand.
   - **Water:** rainfall, humidity, dryness of the air, water balance.
   - **Earth:** soil wetness at three depths, surface temperature, albedo.
3. **Read the cards.** Each card answers the four questions of the challenge:
   - **What is changing?** The variable, with a definition on the back of the card.
   - **Where?** The chosen place, drawn at its true size on the map.
   - **How much?** The rate per year with a 95% confidence range, and the change in March–August 2022 against earlier years.
   - **Is it significant?** A verdict symbol, the p-value, and the test used.
4. **Watch a guided example.** One button opens Kyiv with NO₂, wind and cloud, and a guide explains what the cards show.

### How it works

- **Data pipeline (Python).** Daily and monthly NASA data are cleaned and averaged per place. Missing days are never filled in. Months where the satellite saw the place on fewer than half the days are flagged and drawn as hollow points.
- **Trend test.** For every series we fit a straight line with one offset per calendar month, which removes the seasonal cycle, and Newey-West standard errors, which allow for month-to-month memory. Seasonal Theil-Sen slopes and a modified Mann-Kendall test are stored as checks.
- **Many tests, honest verdicts.** We run 348 tests, so some would look significant by luck. We apply the Benjamini-Hochberg correction within each variable.
- **Cloudy places.** A NO₂ trend is only called significant if it holds on well-observed months alone (April–September where winter is too cloudy).
- **Too little data is a result.** Fire has four comparable seasons, so its cards say "Too little data" and show the 2022 change as a description only.
- **Web app.** A read-only FastAPI service serves the results. A React app draws the atlas and the cards. Nothing is computed in the browser, so every number on screen can be traced to a file in the repository.

### What we found

- **A shock, not a trend.** March–August 2022 NO₂ against 2015–2019: Kharkiv city −29.4%, Kyiv city −28.0%, Kraków −11.0%, Prague −7.5%. The two cities under attack fell about three times as much as the two comparison cities.
- **No significant long-term trend in Ukraine.** Kyiv NO₂: −0.042 ×10¹⁵ molecules/cm² per year, p = 0.12.
- **The one significant trend is outside the war.** Prague NO₂ fell by 0.147 ×10¹⁵ molecules/cm² per year, and it was already falling before February 2022.
- **Weather did not trend.** No weather, water or soil variable shows a significant trend over 2015–2022 in any place. Eight years is short; the challenge itself notes that a longer record can turn a trend significant.

### Benefits

- Students and the public see how a real analysis handles seasons, gaps, and many tests.
- The tool separates three things people confuse: a steady trend, a sudden change, and chance.
- Every card states its limits in plain words. "Significant" never means "caused by the war".

### What we hope to achieve

A reusable pattern for conflict and disaster regions: the same pipeline can take another place, another period, and other NASA variables. Next steps are longer records (through 2025), more comparison regions, and a view for sudden changes with its own test.

### Tools

Python (pandas, NumPy, SciPy, Matplotlib), FastAPI, React, TypeScript, Vite, Recharts, d3-geo, pytest, Vitest, Playwright, Git and GitHub. NASA Giovanni, NASA FIRMS, and the NASA POWER API for data access.

## Use of Artificial Intelligence

Yes. **[Confirm the list.]**

- **Claude (Anthropic), through Claude Code:** wrote most of the web frontend, parts of the backend and of the analysis scripts, tests, and documentation, and drafted this text. Commits written with Claude carry a `Co-Authored-By: Claude` line, and the repository README states it.
- **Codex / ChatGPT (OpenAI):** code review, a scientific audit of the analysis, and validation of the data downloads.
- **[Any tool Husam used.]**
- **No AI-generated images, video or audio.** The map is drawn by code from Natural Earth data. Charts are drawn from our result files. No NASA logos or mission identifiers are used or modified.
- The team chose the question, the places, the statistical rules and every decision recorded in `docs/decisions.md`, and reviewed the results.

## NASA Data

- **OMI/Aura OMNO2d v004**, tropospheric NO₂ column, 30% cloud screened, daily 0.25°, March 2015 – August 2022, area-averaged per place with **NASA Giovanni**. Used for the NO₂ series, coverage flags, trends and the 2022 comparison in eight places.
- **VIIRS S-NPP 375 m active fires (VNP14IMG)** from **NASA FIRMS**, March 2019 – August 2022. Used for vegetation fire density and static industrial heat sources, normalised by area and by days the satellite observed.
- **NASA POWER** (MERRA-2 meteorology and CERES SYN1deg radiation), monthly, 2015–2022. Used for temperature, wind, cloud, pressure, humidity, rainfall, soil wetness, surface temperature, albedo and sunlight, and to compute evaporation demand (FAO-56).

## Space Agency Partner & Other Data

- OMI is a Dutch–Finnish instrument (KNMI, FMI) flying on NASA's Aura satellite. We used it through NASA's OMNO2d product.
- **Natural Earth** (public domain): country outlines, rivers and seas for the map.
- **geoBoundaries** (open licence): Ukraine national boundary used to clip fire detections.
- Open-source software: the tools listed above.
- Method references: Newey & West (1987); Hamed & Rao (1998); Benjamini & Hochberg (1995); Allen et al. (1998), FAO-56.
- **[If we cite the published NO₂ study we replicated, add it here.]**
