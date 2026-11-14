"""Load and validate the Kyiv air result artifact.

The artifact is loaded once when the app is created. A failed load does
not stop the server: ``/api/health`` reports the problems and the data
endpoints answer 503 until the file is fixed and the server restarted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from backend.catalog import AIR_KYIV_CHARTS, ChartSpec
from backend.config import REPO_ROOT
from backend.schemas import AirResultsContract

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_REPORTED_VALIDATION_ERRORS = 20


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    details: Optional[Any] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass
class AirKyivData:
    """Outcome of loading the artifact. ``raw`` is set only when it is valid."""

    source: Path
    raw: Optional[Dict[str, Any]] = None
    contract: Optional[AirResultsContract] = None
    chart_files: Dict[str, Path] = field(default_factory=dict)
    chart_ready: Dict[str, bool] = field(default_factory=dict)
    problems: List[Problem] = field(default_factory=list)
    loaded_at: Optional[str] = None

    @property
    def results_ready(self) -> bool:
        """The JSON contract loaded and validated; study data can be served."""
        return self.raw is not None

    @property
    def ready(self) -> bool:
        """Contract valid and every allowlisted chart present."""
        return self.results_ready and not self.problems


def display_path(path: Path) -> str:
    """Show repository files relative to the repo root; elsewhere only the name."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _reject_constant(token: str) -> None:
    raise ValueError(f"non-finite number {token!r} is not allowed (schema requires null)")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=_reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _summarise_validation(exc: ValidationError) -> List[Dict[str, str]]:
    return [
        {"loc": ".".join(str(part) for part in err["loc"]), "msg": err["msg"]}
        for err in exc.errors()[:MAX_REPORTED_VALIDATION_ERRORS]
    ]


def _check_chart(spec: ChartSpec, contract: AirResultsContract, reports_dir: Path) -> Optional[Problem]:
    entry = contract.charts.get(spec.chart_id)
    if entry is None:
        return Problem("chart_contract_mismatch", f"Chart '{spec.chart_id}' is missing from the result contract.")
    if Path(entry.png_path).name != spec.filename:
        return Problem(
            "chart_contract_mismatch",
            f"Chart '{spec.chart_id}' points to '{entry.png_path}', expected file '{spec.filename}'.",
        )
    path = reports_dir / spec.filename
    if not path.is_file():
        return Problem("chart_missing", f"Chart file '{display_path(path)}' was not found.")
    with path.open("rb") as handle:
        if handle.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            return Problem("chart_invalid", f"Chart file '{display_path(path)}' is not a PNG image.")
    return None


def load_air_kyiv(results_file: Path, reports_dir: Path) -> AirKyivData:
    data = AirKyivData(source=results_file)

    if not results_file.is_file():
        data.problems.append(
            Problem(
                "results_missing",
                f"Result file '{display_path(results_file)}' was not found. "
                "Run `python -m src.air_analysis` or set WAR_TRACKER_AIR_KYIV_RESULTS.",
            )
        )
        return data

    try:
        raw = _read_json(results_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        data.problems.append(Problem("results_unreadable", f"Result file could not be parsed: {exc}"))
        return data

    try:
        contract = AirResultsContract.model_validate(raw)
    except ValidationError as exc:
        data.problems.append(
            Problem(
                "results_invalid",
                f"Result file does not match schema 1.x ({exc.error_count()} error(s)).",
                _summarise_validation(exc),
            )
        )
        return data

    for spec in AIR_KYIV_CHARTS.values():
        problem = _check_chart(spec, contract, reports_dir)
        data.chart_ready[spec.chart_id] = problem is None
        if problem is None:
            data.chart_files[spec.chart_id] = reports_dir / spec.filename
        else:
            data.problems.append(problem)

    data.raw = raw
    data.contract = contract
    data.loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return data
