# Frontend handoff (map-first Air journey)

Run and structure: `frontend/README.md`. Screenshots: `docs/screenshots/frontend/`.

## Built
Ukraine map → choose Air → Kyiv study box revealed → select Kyiv → NO₂ evidence panel, in a parchment/gilt, Avatar-inspired interface (art-direction only; the map is real geography from React Leaflet).
Neutral state, element controls (Air available; Fire, Earth, Water "Coming later" from the catalog), "L Legend", guide bubble, Reset Ukraine view, Explore Kyiv (button, boundary click, keyboard marker), Close panel, Clear element.
Panel: location/variable/period, map note, baseline selector, seasonal headline, persistent coverage warnings and scientific notices, interactive chart (+ table), month buttons, month inspector, guide narration, expandable sources/methods/limitations/statistics, supplementary figures.

## API use
| Need | Field |
|---|---|
| Availability and study endpoint | `/api/cases` → `elements[].status`, `studies[0].endpoint` (study loaded only when Air is first selected) |
| Kyiv boundary, marker, focus bounds | `map.study_boundary`, `map.center`, `map.bounds` (never redrawn) |
| Headline | `result.comparisons[<baseline id>]` |
| Chart, inspector, label on the box | `result.matched_months[]` |
| Warnings and notices | `highlights.*` |
| Figures | `charts[]` only |

## Verified (this branch)
`npm run typecheck`, `npm run build`, `npm test` (31), `npm run test:e2e` against the real backend (14): neutral state and Ukraine framing (checked from the map tiles requested: Crimea's south to Ukraine's west/east extremes), Air selection and Kyiv discovery, marker click and keyboard Enter, panel open/close, both baselines, April 8/30 warning, missing values, study and catalog failure with retry, missing/failed figures, desktop and mobile layout (no sideways scroll, 44px targets).

## Known limitations
- Basemap tiles need internet (Esri street map with OSM fallback; set `VITE_TILE_URL` for a keyed provider). In the sandbox they were blocked, so screenshots show a grey basemap; the outline, label and UI are real. **Look at it once locally with tiles before presenting.**
- Basemap is a standard light map, not the illustrated basemap or a 3D globe (out of scope).
- Kyiv box is small at country scale; the marker, label and Explore Kyiv button make it discoverable.
- Mobile uses a stacked panel under the map, not a bottom sheet.
- Guide is a placeholder mark with short API-derived text; no AI chat.
- Element label "Earth" is a frontend display mapping of the catalog's `land`; decide whether the catalog should say Earth.
- Bundle ≈ 930 kB (280 kB gzip); code splitting is a follow-up.
- Decoration is CSS-only; the generated illustration is not used as an asset.
- E2E uses system Chrome.

## Backend notes
None blocking; no backend changes.
