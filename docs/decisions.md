# Decisions log

Every analysis or product choice that changes what a user sees, with who decided and what it changed.
Newest first. Husam has not yet reviewed the entries marked **needs review**.

## 2026-11-15

### D13. Wide painted map and a "Show me around" tour
- **Decided by:** G.
- **Map:** a new wide painting with grey-blue neighbours and no labels, fitted to the true border (median about 3 atlas units; `docs/base-map.md`). The map window widened so it fills wide screens; our own labels sit at true coordinates.
- **Tour:** "Show me around" (Driver.js) highlights one control at a time with Next, Back, Close and Escape. It never changes a selection or loads data, and it skips controls not on screen. Seven stops before Investigate, seven after. It replaces "Start guided example", which was removed (G).
- **Later:** a zoom on each card's chart (visual only; the verdict stays on the tested period).

### D12. Name, painted base map, portrait slot
- **Decided by:** G.
- **Name:** the app is "The Last Trend Bender" (title centred). The repository keeps its name.
- **Base map:** a painted illustration, AI-generated and marked as such on the map, warped onto the true projection (`docs/base-map.md`). Boxes and pins stay on true coordinates.
- **Portrait:** shows `frontend/public/guide-portrait.png` when present, otherwise the drawn placeholder. The portrait must be an original character, not one from an existing franchise.

### D11. The guide becomes a portrait; the letter becomes a field guide
- **Decided by:** G.
- **What:** the guide is a portrait in the corner with a badge counting insights. Pressing it opens one insight per open card, built only from that card's fields (test, then "Separately…" for 2022, then coverage). The letter ("Field guide") lists the chosen element's variables with plain definitions and follows the element; its second tab keeps "How to read".

### D10. Compare with a city outside the war
- **Decided by:** G.
- **What:** Kraków and Prague are no longer places on their own. "Compare with" splits the screen: the Ukrainian place on the left, the city on the right, the same variables in the same order. Each card keeps its own test; nothing tests the difference between the two.
- **Also:** at most 3 cards per side, larger charts.

### D9. February 2022 counts as "before the invasion"
- **Decided by:** Claude.
- **What:** the data are monthly, so the pre-invasion test ends with February 2022, which includes 24–28 February. The label says so instead of changing the calculation the night before submission.

### D8. Temperature, sunlight and evaporation demand for the comparison cities
- **Decided by:** Claude. **Needs review.**
- **What:** the five variables existed in `reports/four_elements_monthly_panel.csv` for Kraków and Prague but were exported for Ukraine only. They are now exported with the same seasonal rule (a test reproduces Husam's numbers for a Ukraine box). Their trend tests join each variable's correction family (16 tests instead of 12). No verdict changed.

### D7. Fire tests verified with the raw download
- **Decided by:** G (supplied the files), Claude (ran them).
- **What:** the four FIRMS archives (`DL_FIRE_SV-C2_848848/848862/848867/848869.zip`) from G's Downloads were placed in `data/raw/firms_viirs/` (not committed, by design). All 47 analysis tests pass, including the four that failed without the raw files.
- **Effect:** none on screen. The failures were missing input, not a bug.

### D6. Kharkiv city stays outside the 25-variable catalog for now
- **Decided by:** Claude. **Needs review.**
- **What:** Kharkiv city is a NO₂-only place, added to the atlas from `reports/atlas_no2_regional.json` (`extra_places`).
- **Why not the catalog:** adding a study box means new NASA POWER downloads and re-running the whole weather, water and earth pipeline. That is a rebuild of every published number, too risky the night before submission.
- **Follow-up (Husam):** add the box to `STUDY_BOXES` in `src/weather_power_pipeline.py` and regenerate.

### D5. Correct for multiple tests within each variable
- **Decided by:** G. **Needs review.**
- **What:** Benjamini-Hochberg is applied per variable (its places × periods, 12–16 tests), not across all 348 tests.
- **Alternative rejected:** one family of 348 (stricter; used in the first version).
- **Why:** a user reads one variable card at a time and compares places; the family they see is that variable.
- **Effect:** together with D4, Prague NO₂ becomes a significant fall. Kraków NO₂ is just above the line (adjusted p = 0.052). No weather, water or earth verdict changes (smallest adjusted p = 0.11; 0.144 after D8 added the comparison cities).

### D4. NO₂ in cloudy places is confirmed on April–September only
- **Decided by:** G. **Needs review.**
- **What:** a NO₂ trend is called significant only if it is confirmed (same direction, p < 0.05) on months where the satellite saw the place on at least half the days. Where winter is too poorly observed for an all-year check (Kyiv, Kharkiv city, Kraków, Prague), the confirmation uses well-observed April–September months.
- **Alternatives rejected:** trust the raw result (ignores a known sampling problem); reject it outright (first version: Prague showed "Too little data").
- **Effect:** Prague's decline is confirmed (April–September p = 0.002) and shown as significant. It is significant before the invasion too, so it is background, not a war signal.

### D3. One trend test for every variable
- **Decided by:** Claude, following Husam's Kyiv NO₂ method.
- **What:** month-fixed-effects OLS with Newey-West HAC standard errors (lags ≤ 6 months), for the full record and for months up to February 2022. Seasonal Theil-Sen and Hamed-Rao Mann-Kendall are stored as checks.
- **Why:** it removes the seasonal cycle and allows for month-to-month memory, which the challenge names as the main trap.
- **Effect:** the Kyiv NO₂ result is reproduced exactly (−4.18×10¹³ molecules/cm² per year, p = 0.1245).

### D2. Fire gets no trend verdict
- **Decided by:** Husam (earlier), kept by Claude.
- **What:** four comparable fire seasons (2019–2022) are too few for a trend test. Cards say "Too little data" and show the 2022 change against 2019–2021 as a description.

### D1. No "after the invasion" trend period
- **Decided by:** Claude, agreed by G.
- **What:** the data ends 6–10 months after 24 February 2022. A trend test on that span cannot separate a real change from the seasonal cycle.
- **Instead:** every card shows March–August 2022 against the same months of earlier years, labelled as a description, not a test.

## Open

- Husam's review of D4, D5 and D6.
- An "After the invasion" view, a single picker for all 25 variables, and a second guided example (cities compared): offered, not decided.
