# Frontend: Environmental Fingerprints of War

React + TypeScript + Vite single-page app for milestone 1: **Ukraine → Air/NO₂ → Kyiv**.
It reads everything from the FastAPI backend (`/api/cases`, `/api/air/kyiv`, chart PNGs). It never imports the result JSON.

Requires Node ≥ 20.19 and, for the backend, Python with `pip install -r backend/requirements.txt` (see `docs/backend-api.md`).

## Install

```bash
cd frontend
npm ci
```

## Run frontend and backend together

Two terminals.

```bash
# 1. backend, from the REPO ROOT
uvicorn backend.main:app --reload --port 8000

# 2. frontend, from frontend/
npm run dev            # http://127.0.0.1:5173
```

Vite proxies `/api` (JSON **and** chart PNGs) to `http://127.0.0.1:8000`, so the browser sees one origin and CORS is not involved.
Use another backend address with `VITE_API_PROXY_TARGET=http://host:port npm run dev`.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | dev server with `/api` proxy |
| `npm run build` | typecheck + production build into `dist/` |
| `npm run preview` | serve `dist/` on :4173 with the same `/api` proxy |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm test` | Vitest + Testing Library component/adapter tests |
| `npm run test:e2e` | Playwright smoke test against the **real** backend (starts uvicorn and Vite itself, reuses them if already running; needs Chrome installed) |

## Production API routing

The built app calls relative `/api/...` URLs. Pick one:

1. **Same origin (recommended).** Serve `dist/` and route `/api/*` to FastAPI at the reverse proxy (nginx, Caddy, a platform rewrite). Nothing to configure.
2. **Different origin.** Build with `VITE_API_BASE_URL=https://api.example.org npm run build` (no trailing slash), and add the frontend origin to the backend's `WAR_TRACKER_CORS_ORIGINS`. Chart image URLs use the same base.

## Layout

```
src/api/               typed client (ApiError kinds, retry-able), contract types, shape check, useApiResource (lazy via `enabled`)
src/adapters/          pure helpers: formatting, baselines, month rows, chart points, "absence" kinds
src/components/        shared pieces: AbsenceMark, Disclosure, AvatarMark, DecorativeFrame
src/features/explorer/ map-first shell: AirExplorer (state), UkraineMap, ElementControls, MapLegend, GuideBubble, TitleBadge, elements.ts, kyivLabel.ts
src/features/air/      Kyiv · NO₂ study panel and its parts (chart, picker, inspector, warnings, evidence, figures, guide)
src/styles/            tokens.css (palette, type, space) + global.css
e2e/                   Playwright smoke test
```

For the Figma pass: parchment/ink/element colours, type scale and spacing live in `src/styles/tokens.css`; each component owns a CSS Module. Buttons, labels, avatar and frame are separate components (`ElementControls`, `GuideBubble`, `AvatarMark`, `DecorativeFrame`).

## Interaction model

Journey: **Ukraine map → choose Air → Kyiv study box revealed → select Kyiv → explore NO₂ results.**
Four pieces of state are independent: selected element, panel open/closed, baseline + month, and map camera (a command, never data).

| Action | Effect |
|---|---|
| open | catalog loaded (`/api/cases`); Ukraine framed; nothing scientific shown; study not requested |
| choose Air | study package loaded from the catalog's endpoint; Kyiv boundary, marker and label shown; view stays on Ukraine |
| click boundary / marker, press Enter on the marker, or **Explore Kyiv** | camera focuses on the API bounds; panel opens |
| **Close panel** | panel hides; Air, baseline, month, camera stay |
| **Reset Ukraine view** | camera only |
| **Clear element** | back to the neutral state (camera returns to Ukraine) |

Element labels: the catalog calls the fourth element `land`; the UI shows it as **Earth** (label mapping in `elements.ts`; availability always comes from the catalog).

## Scientific behaviour (what the UI guarantees)

- Every number is read from the API. Nothing is recalculated, and no headline is hard-coded.
- Baseline switch selects the exported comparison (`primary_2015_2019_valid_day` / `sensitivity_2019_2021_valid_day`) **and** the matching `matched_months` fields, so headline and chart move together.
- Month selection opens detail only; the seasonal headline never changes with it.
- `null` is never drawn as zero and chart lines are not joined across it. Three absences are named differently: *No valid measurement* (missing data), *Not assessed* (statistic not computed), *Unavailable* (figure withheld).
- Seasonal before/after status and the multi-year trend are shown in separate blocks. "Causal attribution: not established" stays visible.
- The shaded band is min–max across baseline years (variability), labelled as not a confidence interval.
- The map is a study-area outline, not a heatmap; panning, zooming and reset change the view only. The label on the Kyiv box shows the seasonal headline (labelled March–August) until a month is chosen, then that month, labelled as the month.
