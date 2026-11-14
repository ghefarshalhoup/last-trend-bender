from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest
from fastapi.testclient import TestClient

from backend.catalog import AIR_KYIV_CHARTS
from backend.config import REPO_ROOT, Settings
from backend.main import create_app

REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_FILE = REPORTS_DIR / "air_no2_results.json"


@pytest.fixture(scope="session")
def raw_contract() -> Dict[str, Any]:
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def client() -> TestClient:
    """App bound to the committed artifact in reports/."""
    return TestClient(create_app(Settings(reports_dir=REPORTS_DIR, air_kyiv_results=RESULTS_FILE)))


@pytest.fixture
def make_client(tmp_path: Path, raw_contract: Dict[str, Any]) -> Callable[..., TestClient]:
    """Build an app over a temp copy of the reports, optionally altered.

    ``mutate`` edits a deep copy of the contract; ``text`` replaces the file
    body verbatim; ``drop_charts`` removes PNGs; ``write_results=False``
    leaves the JSON absent.
    """

    def _make(
        mutate: Optional[Callable[[Dict[str, Any]], None]] = None,
        text: Optional[str] = None,
        drop_charts: tuple = (),
        write_results: bool = True,
    ) -> TestClient:
        reports = tmp_path / "reports"
        reports.mkdir(exist_ok=True)
        for spec in AIR_KYIV_CHARTS.values():
            if spec.chart_id not in drop_charts:
                shutil.copy(REPORTS_DIR / spec.filename, reports / spec.filename)
        results = reports / "air_no2_results.json"
        if write_results:
            if text is not None:
                results.write_text(text, encoding="utf-8")
            else:
                payload = copy.deepcopy(raw_contract)
                if mutate:
                    mutate(payload)
                results.write_text(json.dumps(payload), encoding="utf-8")
        return TestClient(create_app(Settings(reports_dir=reports, air_kyiv_results=results)))

    return _make
