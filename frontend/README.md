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
src/api/          typed client (ApiError kinds, retry-able), contract types, shape check, useApiResource
src/adapters/     pure helpers: formatting, baselines, month rows, chart points, "absence" kinds
src/components/   shared pieces (AbsenceMark, Disclosure)
src/features/air/ the Air screen, one component per concern, each with a CSS Module
src/styles/       tokens.css (colour, type, space) + global.css
e2e/              Playwright smoke test
```

For the Figma pass: colours, type scale, spacing and radii live in `src/styles/tokens.css`; layout lives in `features/air/AirScreen.module.css`; each component owns its own module.

## Scientific behaviour (what the UI guarantees)

- Every number is read from the API. Nothing is recalculated, and no headline is hard-coded.
- Baseline switch selects the exported comparison (`primary_2015_2019_valid_day` / `sensitivity_2019_2021_valid_day`) **and** the matching `matched_months` fields, so headline and chart move together.
- Month selection opens detail only; the seasonal headline never changes with it.
- `null` is never drawn as zero and chart lines are not joined across it. Three absences are named differently: *No valid measurement* (missing data), *Not assessed* (statistic not computed), *Unavailable* (figure withheld).
- Seasonal before/after status and the multi-year trend are shown in separate blocks. "Causal attribution: not established" stays visible.
- The shaded band is min–max across baseline years (variability), labelled as not a confidence interval.
- The map is a study-area outline, not a heatmap; panning changes the view only.
