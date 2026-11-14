"""Settings resolution is independent of the working directory."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.config import DEFAULT_CORS_ORIGINS, REPO_ROOT, Settings, parse_origins


def test_defaults_point_at_repo_reports():
    settings = Settings.from_env({})
    assert settings.reports_dir == (REPO_ROOT / "reports").resolve()
    assert settings.air_kyiv_results == (REPO_ROOT / "reports" / "air_no2_results.json").resolve()
    assert settings.cors_origins == DEFAULT_CORS_ORIGINS


def test_relative_paths_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env({"WAR_TRACKER_REPORTS_DIR": "reports"})
    assert settings.reports_dir == (REPO_ROOT / "reports").resolve()
    assert settings.air_kyiv_results.is_file()


def test_results_relative_to_reports_dir_and_absolute_override(tmp_path):
    settings = Settings.from_env(
        {"WAR_TRACKER_REPORTS_DIR": str(tmp_path), "WAR_TRACKER_AIR_KYIV_RESULTS": "custom.json"}
    )
    assert settings.reports_dir == tmp_path.resolve()
    assert settings.air_kyiv_results == (tmp_path / "custom.json").resolve()

    absolute = tmp_path / "elsewhere" / "results.json"
    settings = Settings.from_env({"WAR_TRACKER_AIR_KYIV_RESULTS": str(absolute)})
    assert settings.air_kyiv_results == absolute.resolve()


def test_parse_origins():
    assert parse_origins(" https://a.example/ , ,http://localhost:5173") == (
        "https://a.example",
        "http://localhost:5173",
    )
    assert parse_origins("") == ()
    assert parse_origins("*") == ("*",)
    with pytest.raises(ValueError):
        parse_origins("*,https://a.example")


def test_app_starts_from_other_directory(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("WAR_TRACKER_")]:
        monkeypatch.delenv(key)
    api = TestClient(create_app())
    assert api.get("/api/health").status_code == 200


def test_cors_origins_from_env(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    monkeypatch.setenv("WAR_TRACKER_CORS_ORIGINS", "https://demo.example")
    api = TestClient(create_app())
    allowed = api.get("/api/health", headers={"Origin": "https://demo.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://demo.example"
    other = api.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in other.headers
