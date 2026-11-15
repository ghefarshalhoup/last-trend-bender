# War Environment Tracker

A NASA Earth-observation hackathon project investigating how armed conflicts change environmental indicators before and during war.

## First case: Ukraine (2022)
- **Replicate:** A published NO₂ before/after comparison.
- **Contrast:** Compare trends with a candidate reference area and, if feasible, satellite fire detections.
- **Explain:** Clearly distinguish observed changes from possible conflict-related causes.

## Team
- **Husam — data core:** Data acquisition, preprocessing, analysis, reproducible charts.
- **G — coordination and presentation:** Repository organization, research documentation, integration, storytelling, and demo.

## Project layout
- `data/` — local raw/processed datasets; large files are intentionally excluded from Git
- `src/` — reusable Python analysis, statistical rigor, and processing modules (`no2_pipeline.py`, `fire_pipeline.py`, `fire_analysis.py`, `weather_power_pipeline.py`, `stats_rigor.py`, `four_elements_analysis.py`, `build_web_bundle.py`)
- `web/` — zero-backend interactive 4-Elements Trend Observatory (`index.html`, `app.css`, `app.js`, `data/ukraine_4elements_bundle.json`)
- `reports/` — reproducible validated CSV, strict JSON, and figure artifacts
- `docs/` — study specification, methods, findings, and schemas
- `backend/` — read-only FastAPI service (Milestone 1)

## Full 4-Elements Kyiv & Ukraine Observatory
Beyond the Milestone 1 NO₂ replication, the 4-Elements workflow fuses **Air** (`OMNO2d v004` + MERRA-2 wind/cloud), **Fire** (`FIRMS VIIRS S-NPP` `type0` vegetation vs `type2` industrial + FAO-56 PET), **Water** (`PRECTOTCORR`, Vapor Pressure Deficit, `P - PET`), and **Earth** (`GWETTOP`/`GWETROOT`, `Ts - T2m`, albedo) across 8 aligned regions (`2015–2022`).

```bash
# 1. Fetch & cache live NASA POWER MERRA-2/CERES data (only needed if data/raw/nasa_power is empty)
python -m src.weather_power_pipeline --fetch

# 2. Run 4-Elements statistical integration & charts
python -m src.four_elements_analysis

# 3. Compile interactive observatory JSON bundle & launch UI
python -m src.build_web_bundle
python3 -m http.server 8080 --directory web
```
See [docs/four-elements-methods.md](docs/four-elements-methods.md), [docs/four-elements-findings.md](docs/four-elements-findings.md), and [docs/four-elements-results-schema.md](docs/four-elements-results-schema.md).

## First milestone
Reproduce one credible NO₂ comparison using matched calendar months before/during the 2022 invasion, with dataset provenance, then evaluate reference-region differences.

## Getting started
```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Backend API
```bash
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload --port 8000
```
See [docs/backend-api.md](docs/backend-api.md) for configuration, endpoints and the frontend handoff.

Data sources: [NASA Giovanni](https://giovanni.gsfc.nasa.gov/) and [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/).
Reference study: [Ialongo et al. (2023), Scientific Reports](https://www.nature.com/articles/s41598-023-42118-w).

## Illustrated atlas (the submitted tool)

Choose a place and a period, then open NASA variables as cards with a trend verdict. See [frontend/README.md](frontend/README.md) to run it, [docs/decisions.md](docs/decisions.md) for every analysis decision, and [docs/submission/](docs/submission/) for the submission text.

```bash
python -m src.trend_results   # regional NO2 monthly series + reports/trend_results.json
```

## Use of AI

Parts of this repository were written with AI assistance: Claude (Anthropic, via Claude Code) for most of the frontend, parts of the backend and analysis scripts, tests and documentation; Codex / ChatGPT (OpenAI) for review and audits. Commits written with Claude carry a `Co-Authored-By: Claude` trailer. No images, video or audio in this repository are AI-generated: the atlas map is drawn by code from Natural Earth data and all charts come from the result files.
