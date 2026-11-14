"""FastAPI application for milestone 1 (read-only).

Run from the repository root::

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend import __version__
from backend.catalog import AIR_KYIV_CHARTS
from backend.config import Settings
from backend.errors import ApiError, install_error_handlers
from backend.presenters import build_air_study, build_cases
from backend.repository import AirKyivData, display_path, load_air_kyiv
from backend.schemas import AirStudyResponse, CasesResponse, ErrorResponse, HealthResponse

SERVICE_NAME = "war-environment-tracker-backend"
_ERRORS = {
    404: {"model": ErrorResponse, "description": "Unknown resource"},
    503: {"model": ErrorResponse, "description": "Data not ready"},
}


def _air(request: Request) -> AirKyivData:
    return request.app.state.air_kyiv


def _require_results(data: AirKyivData) -> None:
    if not data.results_ready:
        raise ApiError(
            503,
            "data_unavailable",
            "Kyiv air results are not available. See /api/health for details.",
            [problem.as_dict() for problem in data.problems],
        )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Environmental Fingerprints of War — API",
        version=__version__,
        description="Read-only access to validated study results. Milestone 1: Ukraine → Air/NO₂ → Kyiv.",
    )
    app.state.settings = settings
    app.state.air_kyiv = load_air_kyiv(settings.air_kyiv_results, settings.reports_dir)

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
        body = {
            "status": "ok" if data.ready else "degraded",
            "service": SERVICE_NAME,
            "version": __version__,
            "datasets": {
                "air_kyiv": {
                    "ready": data.ready,
                    "source_file": display_path(data.source),
                    "schema_version": data.raw["schema_version"] if data.raw else None,
                    "loaded_at": data.loaded_at,
                    "charts": {chart_id: data.chart_ready.get(chart_id, False) for chart_id in AIR_KYIV_CHARTS},
                    "problems": [problem.as_dict() for problem in data.problems],
                }
            },
        }
        return JSONResponse(status_code=200 if data.ready else 503, content=body)

    @app.get("/api/cases", response_model=CasesResponse)
    def cases(request: Request):
        return JSONResponse(content=build_cases(_air(request)))

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
