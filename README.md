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
- `src/` — reusable Python analysis and processing scripts
- `notebooks/` — exploratory analysis and reproducible figures
- `docs/` — study specification, methods, sources, and findings

## First milestone
Reproduce one credible NO₂ comparison using matched calendar months before/during the 2022 invasion, with dataset provenance, then evaluate reference-region differences.

## Getting started
```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Data sources: [NASA Giovanni](https://giovanni.gsfc.nasa.gov/) and [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/).
Reference study: [Ialongo et al. (2023), Scientific Reports](https://www.nature.com/articles/s41598-023-42118-w).
