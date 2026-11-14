# Frontend handoff (milestone 1)

Run and structure: see `frontend/README.md`. Screenshots: `docs/screenshots/frontend/`.

## What is built
One screen, Ukraine → Air/NO₂ → Kyiv: header and breadcrumb, the opening question, the study-boundary map, the seasonal summary with a baseline selector, a March–August 2022-vs-baseline chart (with a table view), a keyboard- and touch-usable month inspector, permanent coverage and scientific notices, an evidence area (sources, methods, limitations, statistical status), supplementary figures, and a placeholder guide whose narration follows the selected element, baseline and month.

## How it consumes the API
| Need | Field |
|---|---|
| Is Air available? Which endpoint? | `/api/cases` → `elements[air].studies[0].endpoint` |
| Map frame and outline | `map.bounds`, `map.study_boundary`, `map.sampled_grid_center_extent`, `map.note` |
| Seasonal headline | `result.comparisons[<baseline id>]` |
| "Excluding low-coverage months" line | `result.coverage_sensitivity.excluding_target_flagged_months[<baseline id>]` |
| Chart and inspector | `result.matched_months[]` (`target_2022`, `<baseline>`, `vs_<baseline>`) |
| Coverage warnings, notices | `highlights.coverage_warnings`, `highlights.notices` |
| Statistics | `result.statistics.*` (before/after and multi-year trend kept apart) |
| Figures | `charts[]` only; image URL = `chart.url` |

## Known limitations
- The basemap is CARTO light tiles via OpenStreetMap data. It needs internet at runtime; with tiles blocked the outline still shows on a plain background. Attribution is shown.
- The production bundle is about 930 kB (280 kB gzipped) because Leaflet and Recharts are in one chunk. Route-level code splitting is a follow-up.
- Only Air/Kyiv exists. Fire, Land and Water show as "not yet available" from the catalog.
- The guide is a placeholder abstract mark; final character art is pending.
- Visual design is a considered draft, not yet matched to Figma.
- Playwright uses system Chrome (`channel: 'chrome'`), not a bundled browser.
- The map has no keyboard-driven data layer: it carries no per-location data by design.

## Backend notes (flagged, not changed)
None blocking. The contract matched `docs/backend-api.md` throughout.
