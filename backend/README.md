# backend

Read-only FastAPI service for the frontend. Milestone 1 serves the validated
Kyiv NO₂ artifact from `reports/` without recomputing anything.

```bash
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload --port 8000   # from the repo root
python -m pytest backend/tests -q
```

| File | Role |
|---|---|
| `config.py` | Environment settings; paths anchored at the repo root |
| `schemas.py` | Pydantic models: result-contract validation and API envelopes |
| `repository.py` | Loads and validates the artifact and chart files |
| `catalog.py` | Cases, pending elements and the chart allowlist |
| `presenters.py` | Builds map GeoJSON, chart links and highlights (no science) |
| `errors.py` | Uniform `{"error": {...}}` responses |
| `main.py` | App factory and routes |

Full documentation, examples and the frontend handoff:
[`docs/backend-api.md`](../docs/backend-api.md).
