"""API and strict contract tests for the four-element illustrated atlas endpoints."""

from __future__ import annotations

import json
import shutil

from fastapi.testclient import TestClient

from backend.config import ATLAS_ARTIFACT_FILENAMES, REPO_ROOT, Settings
from backend.catalog import AIR_KYIV_CHARTS
from backend.main import create_app


def _stage_full_reports(tmp_path) -> tuple:
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    src = REPO_ROOT / "reports"
    shutil.copy(src / "air_no2_results.json", reports / "air_no2_results.json")
    for spec in AIR_KYIV_CHARTS.values():
        shutil.copy(src / spec.filename, reports / spec.filename)
    for fname in ATLAS_ARTIFACT_FILENAMES:
        shutil.copy(src / fname, reports / fname)
    return reports, Settings(reports_dir=reports, air_kyiv_results=reports / "air_no2_results.json")


def test_health_exposes_all_atlas_datasets(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    expected = {
        "air_kyiv",
        "atlas_catalog",
        "fire_ukraine",
        "fire_ukraine_cells",
        "water_ukraine",
        "land_ukraine",
        "air_weather",
    }
    assert expected.issubset(body["datasets"].keys())
    for key in expected:
        assert body["datasets"][key]["ready"] is True
        assert body["datasets"][key]["problems"] == []


def test_variables_catalog_endpoints_and_filters(client):
    full = client.get("/api/variables")
    assert full.status_code == 200
    body = full.json()
    assert body["metric_count"] == 25
    assert len(body["variables"]) == 25
    assert all(
        isinstance(v.get("plain_definition"), str) and len(v["plain_definition"].strip()) > 20
        for v in body["variables"]
    )

    earth_filtered = client.get("/api/variables?element_id=earth")
    assert earth_filtered.status_code == 200
    ebody = earth_filtered.json()
    assert ebody["metric_count"] == 6
    assert [v["metric_id"] for v in ebody["variables"]][0] == "gwettop"

    rain = client.get("/api/variables?metric_id=prectotcorr")
    assert rain.status_code == 200
    assert rain.json()["variables"][0]["units"] == "mm/day"

    bad_elem = client.get("/api/variables?element_id=plasma")
    assert bad_elem.status_code == 400
    assert bad_elem.json()["error"]["code"] == "invalid_filter"

    missing_var = client.get("/api/variables?metric_id=nonexistent_var")
    assert missing_var.status_code == 404
    assert missing_var.json()["error"]["code"] == "variable_not_found"


def test_fire_ukraine_study_separates_methods_and_disables_2015_baseline(client):
    res = client.get("/api/fire/ukraine")
    assert res.status_code == 200
    body = res.json()
    assert body["element_id"] == "fire"
    assert body["primary_indicator"] == "fire_type0_per_1k_km2_day"
    assert body["cells_endpoint"] == "/api/fire/ukraine/cells"

    baselines = {b["baseline_id"]: b for b in body["supported_baselines"]}
    assert baselines["2015-2019"]["supported"] is False
    assert baselines["2015-2019"]["status"] == "withheld_insufficient_baseline"
    assert baselines["2019-2021"]["supported"] is True

    assert body["quality_flags"]["unsupported_baseline_2015_2019"] is True
    assert body["quality_flags"]["cmr_orbit_outage_2022"]["missing_dates_count_2022"] == 16

    donbas = body["result"]["regions"]["donbas_kharkiv_east"]["seasonal_comparisons_mar_aug"]["type0_vegetation_nominal_high"]
    assert donbas["primary_metric"]["vs_2019_2021"]["pct_change"] == 64.86
    assert donbas["primary_metric"]["vs_2015_2019"]["pct_change"] is None
    assert donbas["matched_dates_169d_ukr_adm0_sensitivity"]["pct_change_matched_dates_169d"] == 104.3
    assert donbas["legacy_unnormalized_rate"]["vs_2019_2021"]["pct_change"] == 64.86
    assert len(body["result"]["seasonal_spatial_cells_025deg"]) == 1305
    assert len(body["result"]["fire_dryness_scatter"]) == 144


def test_fire_cells_endpoint_and_filters(client):
    res = client.get(
        "/api/fire/ukraine/cells",
        params={
            "month": "2022-08",
            "region_id": "donbas_kharkiv_east",
            "type_mode": "type0",
            "confidence_mode": "nominal_high",
            "inside_ukr_only": "true",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["applied_filters"]["month"] == "2022-08"
    assert len(body["cmr_month_coverage"]) == 1
    assert body["cmr_month_coverage"][0]["satellite_observed_days"] == 21
    assert len(body["monthly_cells"]) > 0
    assert all(row["month"] == "2022-08" for row in body["monthly_cells"])
    assert all(row["type0_nh_count"] > 0 for row in body["monthly_cells"])
    assert all(row["in_ukr_adm0"] is True for row in body["monthly_cells"])

    bad_month = client.get("/api/fire/ukraine/cells?month=2022-8")
    assert bad_month.status_code == 400
    assert bad_month.json()["error"]["code"] == "invalid_filter"

    bad_reg = client.get("/api/fire/ukraine/cells?region_id=mars")
    assert bad_reg.status_code == 400
    assert bad_reg.json()["error"]["code"] == "invalid_filter"


def test_water_land_and_air_weather_endpoints(client):
    water = client.get("/api/water/ukraine")
    assert water.status_code == 200
    wb = water.json()
    assert wb["element_id"] == "water"
    assert wb["primary_indicator"] == "prectotcorr"
    assert "do not rule out localized drought" in wb["map"]["note"].lower()
    p_pet = wb["result"]["regions"]["kyiv_no2_box"]["metrics"]["precip_minus_pet_mm_day"]["seasonal_mar_aug"]["vs_2015_2019"]
    assert p_pet["pct_change"] is None
    assert p_pet["pct_change_status"] == "withheld_interval_scale"

    land = client.get("/api/land/ukraine")
    assert land.status_code == 200
    lb = land.json()
    assert lb["element_id"] == "land"
    assert lb["element_label"] == "Earth"
    assert lb["primary_indicator"] == "gwettop"
    assert len(lb["map"]["study_boxes"]["features"]) == 6

    weather = client.get("/api/air/weather")
    assert weather.status_code == 200
    ab = weather.json()
    assert ab["element_id"] == "air"
    assert ab["result"]["kyiv_no2_companion_endpoint"] == "/api/air/kyiv"
    assert "kyiv_no2_sensitivities" in ab["result"]
    assert "krakow_prague_2022_comparison" in ab["result"]
    assert ab["result"]["krakow_prague_2022_comparison"]["metrics_count"] == 22


def test_corrupt_or_missing_atlas_artifact_degrades_cleanly(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    (reports / "atlas_fire_ukraine.json").unlink()
    water_path = reports / "atlas_water_ukraine.json"
    water_obj = json.loads(water_path.read_text(encoding="utf-8"))
    water_obj["result"]["regions"]["kyiv_no2_box"]["metrics"]["precip_minus_pet_mm_day"]["seasonal_mar_aug"]["vs_2015_2019"]["pct_change"] = 5.0
    water_path.write_text(json.dumps(water_obj), encoding="utf-8")

    api = TestClient(create_app(settings))
    health = api.get("/api/health")
    assert health.status_code == 503
    hbody = health.json()
    assert hbody["datasets"]["air_kyiv"]["ready"] is True
    assert hbody["datasets"]["fire_ukraine"]["ready"] is False
    assert hbody["datasets"]["water_ukraine"]["ready"] is False
    assert hbody["datasets"]["land_ukraine"]["ready"] is True

    # Air still works cleanly while missing Fire & invalid Water return structured 503s
    assert api.get("/api/air/kyiv").status_code == 200
    assert api.get("/api/land/ukraine").status_code == 200
    assert api.get("/api/fire/ukraine").status_code == 503
    assert api.get("/api/water/ukraine").status_code == 503

    cases = {e["element_id"]: e for e in api.get("/api/cases").json()["cases"][0]["elements"]}
    assert cases["air"]["status"] == "available"
    assert cases["land"]["status"] == "available"
    assert cases["fire"]["status"] == "unavailable"
    assert cases["fire"]["reason"] == "data_not_ready"
    assert cases["water"]["status"] == "unavailable"


def test_cors_allowed_on_atlas_routes(client):
    for route in ("/api/variables", "/api/fire/ukraine", "/api/water/ukraine", "/api/land/ukraine", "/api/air/weather"):
        res = client.get(route, headers={"Origin": "http://localhost:5173"})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_trends_missing_file_is_empty_not_an_error(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    body = TestClient(create_app(settings)).get("/api/trends").json()
    assert body["status"] == "not_available"
    assert body["results"] == []


def test_trends_are_served_unchanged(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    row = {
        "region_id": "donbas_kharkiv_east", "metric_id": "t2m", "window_id": "full_record", "status": "assessed",
        "start_month": "2015-01", "end_month": "2022-12", "n_months": 96, "slope_per_year": 0.05,
        "ci_low": -0.01, "ci_high": 0.11, "p_value": 0.09, "p_value_fdr": 0.3, "significant": False,
        "method": "Month-fixed-effects OLS, Newey-West HAC", "caveats": [],
    }
    (reports / "trend_results.json").write_text(json.dumps({"schema_version": "1.0.0", "results": [row]}))
    body = TestClient(create_app(settings)).get("/api/trends").json()
    assert body["status"] == "available"
    assert body["results"] == [row]


def test_trends_malformed_file_is_503(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    (reports / "trend_results.json").write_text('{"rows": []}')
    assert TestClient(create_app(settings)).get("/api/trends").status_code == 503


def test_regional_no2_missing_file_offers_no_regions(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    (reports / "atlas_no2_regional.json").unlink(missing_ok=True)
    body = TestClient(create_app(settings)).get("/api/air/no2").json()
    assert body["status"] == "not_available"
    assert body["regions"] == {} and body["extra_places"] == []


def test_regional_no2_served_and_malformed_is_503(tmp_path):
    reports, settings = _stage_full_reports(tmp_path)
    payload = {"schema_version": "1.0.0", "status": "available", "regions": {"poland_krakow": {"monthly_series": []}}}
    (reports / "atlas_no2_regional.json").write_text(json.dumps(payload))
    api = TestClient(create_app(settings))
    assert api.get("/api/air/no2").json()["regions"] == payload["regions"]
    (reports / "atlas_no2_regional.json").write_text("[]")
    assert api.get("/api/air/no2").status_code == 503
