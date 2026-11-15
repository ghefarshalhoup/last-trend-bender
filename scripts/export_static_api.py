"""Save every API response the frontend needs as static files, for GitHub Pages.

The atlas reads a fixed set of endpoints whose answers come from committed result
files, so a snapshot of the responses serves exactly what the FastAPI service would.

    python scripts/export_static_api.py frontend/dist

writes  <out>/api/<path>.json  for JSON endpoints and  <out>/api/<path>.png  for charts.
The frontend maps request paths the same way when built with VITE_STATIC_API=1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.main import create_app  # noqa: E402

JSON_ENDPOINTS = [
    "/api/cases",
    "/api/variables",
    "/api/trends",
    "/api/air/kyiv",
    "/api/air/no2",
    "/api/air/weather",
    "/api/weather/comparison",
    "/api/fire/ukraine",
    "/api/water/ukraine",
    "/api/land/ukraine",
]


def _endpoints_in(payload: object) -> set[str]:
    """Any further `/api/...` paths a payload points to (e.g. a case's study endpoint)."""
    found: set[str] = set()
    if isinstance(payload, dict):
        for value in payload.values():
            found |= _endpoints_in(value)
    elif isinstance(payload, list):
        for value in payload:
            found |= _endpoints_in(value)
    elif isinstance(payload, str) and payload.startswith("/api/") and "{" not in payload:
        found.add(payload)
    return found


def export(out: Path) -> list[str]:
    client = TestClient(create_app())
    queue, done, written = list(JSON_ENDPOINTS), set(), []
    while queue:
        path = queue.pop(0)
        if path in done:
            continue
        done.add(path)
        response = client.get(path)
        if response.status_code != 200:
            raise SystemExit(f"{path}: HTTP {response.status_code}")
        is_png = response.headers.get("content-type", "").startswith("image/png")
        target = out / (path.lstrip("/") + (".png" if is_png else ".json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if is_png:
            target.write_bytes(response.content)
        else:
            payload = response.json()
            target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            queue.extend(sorted(_endpoints_in(payload) - done))
        written.append(f"{path} -> {target.relative_to(out)} ({target.stat().st_size // 1024} KB)")
    return written


if __name__ == "__main__":
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/dist")
    for line in export(out_dir):
        print(line)
