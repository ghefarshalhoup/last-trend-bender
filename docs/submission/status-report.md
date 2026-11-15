# Submission status report (15 November 2026)

Deadline: **Sunday 15 November, 23:59 local time**. Press "Submit for Judging" before then; you can resubmit until the deadline.

## What was prepared

| File | What it is |
| --- | --- |
| `docs/submission/project-page.md` | Text for every field of the project form, ready to paste |
| `docs/submission/demo-deck.pptx` / `.pdf` | The 7-slide demo (the allowed maximum) |
| `docs/submission/demo-deck.md` | Slide script and a 30-second video script |
| `docs/decisions.md` | Every analysis decision (D1–D13), who made it, what it changed |
| `docs/data-availability.md` | What each place has, and how each gap would be filled |
| `docs/base-map.md` | How the painted map was fitted to true geography |
| `README.md` | Atlas section, online version, and the required AI-use statement |
| **Live app** | https://ghefarshalhoup.github.io/war-environment-tracker/#/atlas |

## The challenge, line by line

| The challenge asks for | Status | Where |
| --- | --- | --- |
| Select variables from Earth science missions or models | Done | 25 variables from OMI, VIIRS, MERRA-2 and CERES, in four groups |
| Acquire them for a particular region | Done | 7 places in Ukraine, chosen on the map, plus Kraków or Prague side by side |
| Visualise a time series over a long enough period | Done | Monthly series 2015–2022 on every card; fire 2019–2022 |
| Rate of change over time | Done | Rate per year with a 95% range |
| Test significance (t-test, Mann-Kendall, confidence intervals) | Done | Regression t-test with robust errors, confidence interval, Mann-Kendall stored as a check, correction for many tests |
| What, where, how much, is it significant | Done | The four parts of each card |
| Simple definitions of the variables | Done | 25 definitions, reviewed by Husam (#18), on card backs and in the Field guide |
| Demonstration examples the user can watch | Partly | "Show me around" tours of both screens; the demo deck walks through Kyiv. No playable example in the app |
| Trends that differ between regions | Done | Prague falls significantly; Ukrainian places do not |
| Non-significant trends are still interesting | Done | Shown with their rate and an explanation |
| Seasonal cycle removed | Done | One offset per calendar month |
| Short questions that lead the user to variables | Partly | Place → period → group → variable; not phrased as questions |
| AI to suggest variables or regions (optional) | Not done | Optional in the challenge |

## Judging criteria

- **Impact:** a method for asking "did this event change the environment?" that refuses to overclaim. Reusable for other conflicts and disasters.
- **Creativity:** an illustrated atlas with cards instead of a dashboard; "too little data" shown as a finding; the shock-versus-trend story.
- **Validity:** seasonal adjustment, robust errors, coverage flags, multiple-testing correction, a decisions log, about 200 automated tests, published Kyiv numbers reproduced exactly.
- **Relevance:** every objective of the challenge is covered (table above), with NASA data only.
- **Presentation:** live link, deck, screenshots and page text are ready. The weakest point: the demo is slides, not a video.

## Complete

- Data pipeline for NO₂ (8 places), fire, and 22 weather, water and earth variables.
- Trend verdicts for all 392 place × variable × period combinations (368 tested, 24 with too little data).
- Atlas web app: two-step flow, cards, compare view, portrait insights, field guide, "Show me around" tour.
- Online at https://ghefarshalhoup.github.io/war-environment-tracker/#/atlas (GitHub Pages, static snapshot of the API).
- Tests on `main`: 122 Python, 52 frontend unit, 25 browser. All pass.

## Not complete

1. **A playable example in the app** (removed in favour of the tour; the deck covers it).
2. **Husam's review** of decisions D4–D13 (the analysis ones, D4–D8, matter most).
3. **An "after the invasion" view** and **one picker for all variables**: offered, not built.
4. **Kharkiv city** has NO₂ only.
5. **The portrait** is a drawn placeholder; an original image can go in `frontend/public/guide-portrait.png`.

## Needs the team (cannot be done by Claude)

1. **Team name and member names** for slide 1 and the form (the deck shows `[Team name] · [Member names]`).
2. **The demo:** the deck PDF in the repository is a public link; or a 30-second video with English subtitles.
3. **Two placeholders in `project-page.md`:** the tool that made the painted map, and the portrait.
4. **Confirm the AI-use list** (which tools Husam used).
5. **Check that all members are registered at the same Local Event.**
6. **Add the citation** of the published NO₂ study that was replicated, if we name it.
7. **Paste the fields, tick the two boxes, press "Submit for Judging".**
8. **Read the whole text once.** It is a draft written for you, and the claims carry your names.
