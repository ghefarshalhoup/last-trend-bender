"""FastAPI application for milestone 1 (read-only).

Run from the repository root::

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import json
import re
from typing import Literal, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend import __version__
from backend.atlas_repository import AtlasArtifact, AtlasStore, load_atlas_store
from backend.catalog import AIR_KYIV_CHARTS, FIRE_VALID_REGION_IDS
from backend.config import Settings
from backend.errors import ApiError, install_error_handlers
from backend.presenters import build_air_study, build_cases, filter_fire_cells
from backend.repository import AirKyivData, display_path, load_air_kyiv
from backend.schemas import AirStudyResponse, CasesResponse, ErrorResponse, HealthResponse

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

TRENDS_FILE = "trend_results.json"
NO2_REGIONAL_FILE = "atlas_no2_regional.json"
COMPARISON_WEATHER_FILE = "atlas_comparison_weather.json"
SERVICE_NAME = "war-environment-tracker-backend"
_ERRORS = {
    404: {"model": ErrorResponse, "description": "Unknown resource"},
    503: {"model": ErrorResponse, "description": "Data not ready"},
}


def _air(request: Request) -> AirKyivData:
    return request.app.state.air_kyiv


def _atlas(request: Request) -> AtlasStore:
    return request.app.state.atlas_store


def _require_results(data: AirKyivData) -> None:
    if not data.results_ready:
        raise ApiError(
            503,
            "data_unavailable",
            "Kyiv air results are not available. See /api/health for details.",
            [problem.as_dict() for problem in data.problems],
        )


def _require_artifact(artifact: AtlasArtifact, label: str) -> dict:
    if not artifact.ready or artifact.raw is None:
        raise ApiError(
            503,
            "data_unavailable",
            f"{label} results are not available. See /api/health for details.",
            [problem.as_dict() for problem in artifact.problems],
        )
    return artifact.raw


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Environmental Fingerprints of War — API",
        version=__version__,
        description="Read-only access to validated four-element Ukraine study results and 25-metric catalog.",
    )
    app.state.settings = settings
    app.state.air_kyiv = load_air_kyiv(settings.air_kyiv_results, settings.reports_dir)
    app.state.atlas_store = load_atlas_store(settings)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET"],
            allow_credentials=False,
        )
    install_error_handlers(app)

    @app.get("/api/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
    def health(request: Request):
        data = _air(request)
        atlas = _atlas(request)
        datasets = {
            "air_kyiv": {
                "ready": data.ready,
                "source_file": display_path(data.source),
                "schema_version": data.raw["schema_version"] if data.raw else None,
                "loaded_at": data.loaded_at,
                "charts": {chart_id: data.chart_ready.get(chart_id, False) for chart_id in AIR_KYIV_CHARTS},
                "problems": [problem.as_dict() for problem in data.problems],
            },
            **{
                key: {
                    "ready": artifact.ready,
                    "source_file": display_path(artifact.source_file),
                    "schema_version": artifact.schema_version,
                    "loaded_at": artifact.loaded_at,
                    "charts": {},
                    "problems": [problem.as_dict() for problem in artifact.problems],
                }
                for key, artifact in atlas.all_artifacts().items()
            },
        }
        all_ready = data.ready and all(a.ready for a in atlas.all_artifacts().values())
        body = {
            "status": "ok" if all_ready else "degraded",
            "service": SERVICE_NAME,
            "version": __version__,
            "datasets": datasets,
        }
        return JSONResponse(status_code=200 if all_ready else 503, content=body)

    @app.get("/api/cases", response_model=CasesResponse)
    def cases(request: Request):
        return JSONResponse(content=build_cases(_air(request), _atlas(request)))

    @app.get("/api/variables", responses={400: _ERRORS[404], 404: _ERRORS[404], 503: _ERRORS[503]})
    def variables_catalog(
        request: Request,
        element_id: Optional[str] = None,
        metric_id: Optional[str] = None,
    ):
        raw = _require_artifact(_atlas(request).catalog, "Atlas variable catalog")
        variables = raw["variables"]
        if element_id is not None:
            normalized_element = "land" if element_id.lower() == "earth" else element_id.lower()
            if normalized_element not in {"air", "fire", "land", "water"}:
                raise ApiError(
                    400,
                    "invalid_filter",
                    f"Unsupported element_id '{element_id}'.",
                    {"allowed_element_ids": ["air", "fire", "land", "water"]},
                )
            variables = [v for v in variables if v["element_id"] == normalized_element]
        if metric_id is not None:
            variables = [v for v in variables if v["metric_id"] == metric_id]
            if not variables:
                raise ApiError(
                    404,
                    "variable_not_found",
                    f"Unknown metric_id '{metric_id}'.",
                )
        if element_id is None and metric_id is None:
            return JSONResponse(content=raw)
        return JSONResponse(
            content={
                **raw,
                "metric_count": len(variables),
                "variables": variables,
            }
        )

    @app.get("/api/trends")
    def trends(request: Request):
        """Trend verdicts per region x metric x analysis window, written by the analysis
        pipeline to ``reports/trend_results.json`` (see docs/trend-results-schema.md).
        Missing file -> an empty list, so the UI shows "not assessed" instead of failing."""
        path = request.app.state.settings.reports_dir / TRENDS_FILE
        if not path.is_file():
            return JSONResponse(content={"schema_version": "1.0.0", "status": "not_available", "results": []})
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ApiError(503, "data_unavailable", f"Trend results could not be read: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ApiError(503, "data_unavailable", "Trend results file has no 'results' list.")
        payload.setdefault("status", "available")
        return JSONResponse(content=payload)

    @app.get("/api/air/no2")
    def air_no2_regional(request: Request):
        """Monthly NO2 per study box beyond Kyiv, written by ``python -m src.trend_results``.
        Missing file -> no regions, so the UI offers NO2 for Kyiv only."""
        path = request.app.state.settings.reports_dir / NO2_REGIONAL_FILE
        if not path.is_file():
            return JSONResponse(
                content={"schema_version": "1.0.0", "status": "not_available", "regions": {}, "extra_places": []}
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ApiError(503, "data_unavailable", f"Regional NO2 could not be read: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("regions"), dict):
            raise ApiError(503, "data_unavailable", "Regional NO2 file has no 'regions' object.")
        payload.setdefault("extra_places", [])
        return JSONResponse(content=payload)

    @app.get("/api/weather/comparison")
    def comparison_weather(request: Request):
        """Temperature, sunlight and evaporation demand for the comparison cities (same shape as the
        fire file's ``context_weather_regions``). Missing file -> no regions."""
        empty = {"schema_version": "1.0.0", "status": "not_available", "result": {"context_weather_regions": {}}}
        path = request.app.state.settings.reports_dir / COMPARISON_WEATHER_FILE
        if not path.is_file():
            return JSONResponse(content=empty)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ApiError(503, "data_unavailable", f"Comparison weather could not be read: {exc}") from exc
        result = payload.get("result") if isinstance(payload, dict) else None
        regions = result.get("context_weather_regions") if isinstance(result, dict) else None
        if not isinstance(regions, dict):
            raise ApiError(503, "data_unavailable", "Comparison weather file has no regions object.")
        return JSONResponse(content=payload)

    @app.get("/api/air/weather", responses={503: _ERRORS[503]})
    def air_weather(request: Request):
        raw = _require_artifact(_atlas(request).air_weather, "Air regional weather context")
        return JSONResponse(content=raw)

    @app.get("/api/fire/ukraine", responses={503: _ERRORS[503]})
    def fire_ukraine(request: Request):
        raw = _require_artifact(_atlas(request).fire_ukraine, "Ukraine fire VIIRS")
        return JSONResponse(content=raw)

    @app.get("/api/fire/ukraine/cells", responses={400: _ERRORS[404], 503: _ERRORS[503]})
    def fire_ukraine_cells(
        request: Request,
        month: Optional[str] = None,
        year: Optional[int] = None,
        calendar_month: Optional[int] = None,
        region_id: Optional[str] = None,
        type_mode: Literal["all", "type0", "type2", "type3"] = "all",
        confidence_mode: Literal["all", "nominal_high"] = "all",
        inside_ukr_only: bool = False,
    ):
        if month is not None and not _MONTH_RE.fullmatch(month):
            raise ApiError(400, "invalid_filter", f"month '{month}' must match YYYY-MM.")
        if region_id is not None and region_id not in FIRE_VALID_REGION_IDS:
            raise ApiError(
                400,
                "invalid_filter",
                f"Unknown region_id '{region_id}'.",
                {"allowed_region_ids": list(FIRE_VALID_REGION_IDS)},
            )
        if year is not None and (year < 2019 or year > 2022):
            raise ApiError(400, "invalid_filter", f"year must be between 2019 and 2022; got {year}.")
        if calendar_month is not None and calendar_month not in {3, 4, 5, 6, 7, 8}:
            raise ApiError(400, "invalid_filter", f"calendar_month must be in 3..8 (March-August); got {calendar_month}.")
        raw = _require_artifact(_atlas(request).fire_ukraine_cells, "Ukraine fire spatial cells")
        payload = filter_fire_cells(
            raw,
            month=month,
            year=year,
            calendar_month=calendar_month,
            region_id=region_id,
            type_mode=type_mode,
            confidence_mode=confidence_mode,
            inside_ukr_only=inside_ukr_only,
        )
        return JSONResponse(content=payload)

    @app.get("/api/water/ukraine", responses={503: _ERRORS[503]})
    def water_ukraine(request: Request):
        raw = _require_artifact(_atlas(request).water_ukraine, "Ukraine water regional context")
        return JSONResponse(content=raw)

    @app.get("/api/land/ukraine", responses={503: _ERRORS[503]})
    def land_ukraine(request: Request):
        raw = _require_artifact(_atlas(request).land_ukraine, "Ukraine earth/land regional context")
        return JSONResponse(content=raw)

    @app.get("/api/air/kyiv", response_model=AirStudyResponse, responses={503: _ERRORS[503]})
    def air_kyiv(request: Request):
        data = _air(request)
        _require_results(data)
        # JSONResponse serialises the parsed artifact directly, so nulls,
        # integers and key order are exactly what the analysis produced.
        return JSONResponse(content=build_air_study(data))

    @app.get(
        "/api/air/kyiv/charts/{chart_id}",
        response_class=FileResponse,
        responses={200: {"content": {"image/png": {}}}, **_ERRORS},
    )
    def air_kyiv_chart(chart_id: str, request: Request):
        if chart_id not in AIR_KYIV_CHARTS:
            raise ApiError(
                404,
                "chart_not_found",
                f"Unknown chart '{chart_id}'.",
                {"allowed_chart_ids": list(AIR_KYIV_CHARTS)},
            )
        data = _air(request)
        _require_results(data)
        path = data.chart_files.get(chart_id)
        if path is None or not path.is_file():
            raise ApiError(503, "chart_unavailable", f"Chart '{chart_id}' is not available. See /api/health.")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
