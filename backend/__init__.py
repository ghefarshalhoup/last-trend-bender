"""Read-only FastAPI backend for Environmental Fingerprints of War.

Milestone 1 serves the existing Ukraine → Air/NO₂ → Kyiv analysis artifact
produced by ``python -m src.air_analysis``. The backend never recomputes
the science; it loads, validates and exposes the result contract.
"""

__version__ = "0.1.0"
