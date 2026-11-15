# Submission status report (15 November 2026)

Deadline: **Sunday 15 November, 23:59 local time**. Press "Submit for Judging" before then; you can resubmit until the deadline.

## What was prepared

| File | What it is |
| --- | --- |
| `docs/submission/project-page.md` | Text for every field of the project form, ready to paste |
| `docs/submission/demo-deck.pptx` / `.pdf` | The 7-slide demo (the allowed maximum) |
| `docs/submission/demo-deck.md` | Slide script and a 30-second video script |
| `docs/decisions.md` | Every analysis decision, who made it, what it changed |
| `README.md` | Atlas section and the required AI-use statement |

## The challenge, line by line

| The challenge asks for | Status | Where |
| --- | --- | --- |
| Select variables from Earth science missions or models | Done | 25 variables from OMI, VIIRS, MERRA-2 and CERES, in four groups |
| Acquire them for a particular region | Done | 9 places; the user chooses one on the map |
| Visualise a time series over a long enough period | Done | Monthly series 2015–2022 on every card; fire 2019–2022 |
| Rate of change over time | Done | Rate per year with a 95% range |
| Test significance (t-test, Mann-Kendall, confidence intervals) | Done | Regression t-test with robust errors, confidence interval, Mann-Kendall stored as a check, correction for many tests |
| What, where, how much, is it significant | Done | The four parts of each card |
| Simple definitions of the variables | Done, in draft | 25 definitions on the card backs; not yet reviewed by the team |
| Demonstration examples the user can watch | Partly | One guided example (Kyiv). The challenge says "a couple" |
| Trends that differ between regions | Done | Prague falls significantly; Ukrainian places do not |
| Non-significant trends are still interesting | Done | Shown with their rate and an explanation |
| Seasonal cycle removed | Done | One offset per calendar month |
| Short questions that lead the user to variables | Partly | Place → period → group → variable; not phrased as questions |
| AI to suggest variables or regions (optional) | Not done | Optional in the challenge |

## Judging criteria

- **Impact:** a method for asking "did this event change the environment?" that refuses to overclaim. Reusable for other conflicts and disasters.
- **Creativity:** an illustrated atlas with cards instead of a dashboard; "too little data" shown as a finding; the shock-versus-trend story.
- **Validity:** seasonal adjustment, robust errors, coverage flags, multiple-testing correction, a decisions log, 187 automated tests, published Kyiv numbers reproduced exactly.
- **Relevance:** every objective of the challenge is covered (table above), with NASA data only.
- **Presentation:** deck, screenshots and page text are ready. The weakest point today: no hosted link, so judges must run it themselves or rely on the deck.

## Complete

- Data pipeline for NO₂ (8 places), fire, and 22 weather, water and earth variables.
- Trend verdicts for all 372 place × variable × period combinations.
- Atlas web app: two-step flow, cards, guided example, "How to read" guide, mobile layout.
- Tests: 48 analysis, 66 backend, 50 frontend unit, 23 browser. All pass, including the fire tests with the raw download.

## Not complete

1. **Hosted demo link.** The app needs a backend, so it is not yet a single public URL.
2. **Second guided example** (the city comparison).
3. **Team review of the 25 definitions.**
4. **Husam's review** of decisions D4, D5 and D6.
5. **An "after the invasion" view** and **one picker for all variables**: offered, not built.
6. **Kharkiv city** has NO₂ only.

## Needs the team (cannot be done by Claude)

1. **Team name and member names** for slide 1 and the form (the deck shows `[Team name] · [Member names]`).
2. **Publish the demo:** the PDF in the repository is already a public link once this branch is merged. Open it in a private window to check.
3. **Confirm the repository is public.**
4. **Confirm the AI-use list** (which tools Husam used).
5. **Check that all members are registered at the same Local Event.**
6. **Add the citation** of the published NO₂ study that was replicated, if we name it.
7. **Paste the fields, tick the two boxes, press "Submit for Judging".**
8. **Read the whole text once.** It is a draft written for you, and the claims carry your names.
