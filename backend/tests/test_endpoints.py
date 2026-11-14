"""Endpoint behaviour against the committed Kyiv artifact."""

from __future__ import annotations

from backend.catalog import AIR_KYIV_CHARTS
from backend.repository import PNG_SIGNATURE


def test_health_ready(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    air = body["datasets"]["air_kyiv"]
    assert air["ready"] is True
    assert air["schema_version"] == "1.0.0"
    assert air["source_file"] == "reports/air_no2_results.json"
    assert air["charts"] == {chart_id: True for chart_id in AIR_KYIV_CHARTS}
    assert air["problems"] == []


def test_cases_ukraine_air_available_others_unavailable(client):
    body = client.get("/api/cases").json()
    [ukraine] = body["cases"]
    assert ukraine["case_id"] == "ukraine"
    elements = {e["element_id"]: e for e in ukraine["elements"]}
    assert elements["air"]["status"] == "available"
    assert elements["air"]["studies"] == [{"study_id": "kyiv", "name": "Kyiv, Ukraine", "endpoint": "/api/air/kyiv"}]
    others = [e for key, e in elements.items() if key != "air"]
    assert others, "pending elements should be listed explicitly"
    for element in others:
        assert element["status"] == "unavailable"
        assert element["reason"] == "not_yet_integrated"
        assert element["studies"] == []


def test_air_kyiv_serves_contract_unchanged(client, raw_contract):
    body = client.get("/api/air/kyiv").json()
    assert body["result"] == raw_contract
    assert list(body["result"]) == list(raw_contract)
    assert body["schema_version"] == raw_contract["schema_version"]
    assert (body["case_id"], body["element_id"], body["study_id"]) == ("ukraine", "air", "kyiv")


def test_air_kyiv_preserves_nulls_and_not_assessed(client):
    body = client.get("/api/air/kyiv").json()
    before_after = body["result"]["statistics"]["before_after_seasonal_inference"]
    assert before_after["status"] == "not_assessed"
    for key in ("p_value", "ci_95_lower_molec_cm2", "ci_95_upper_molec_cm2"):
        assert key in before_after and before_after[key] is None
    assert before_after["statistical_significance_claimed"] is False
    assert body["result"]["status"]["before_after_significance"] == "not_assessed"
    assert any("Before/after significance not assessed" in notice for notice in body["highlights"]["notices"])
    assert body["highlights"]["seasonal_differences"]["significance_status"] == "not_assessed"


def test_air_kyiv_keeps_april_coverage_warning(client):
    body = client.get("/api/air/kyiv").json()
    april = next(m for m in body["result"]["monthly_series"] if m["month"] == "2022-04")
    assert (april["valid_days"], april["calendar_days"]) == (8, 30)
    assert april["flagged_below_50_pct"] is True
    assert body["highlights"]["coverage_warnings"] == [
        {"month": "2022-04", "valid_days": 8, "calendar_days": 30, "coverage_fraction": 0.2667}
    ]


def test_air_kyiv_both_baselines_and_separated_statistics(client):
    body = client.get("/api/air/kyiv").json()
    result = body["result"]
    assert {"primary_2015_2019_valid_day", "sensitivity_2019_2021_valid_day"} <= set(result["comparisons"])
    seasonal = body["highlights"]["seasonal_differences"]
    trend = body["highlights"]["multi_year_trend"]
    assert seasonal["headline_comparison_id"] == "primary_2015_2019_valid_day"
    assert set(seasonal["comparison_ids"]) == set(result["comparisons"])
    assert trend["window_ids"] == ["pre_invasion", "full_record"]
    # Trend results stay in statistics; seasonal differences never carry a p-value.
    assert not any("p_value" in comparison for comparison in result["comparisons"].values())
    assert result["statistics"]["multi_year_seasonality_aware_trend"]["full_record"]["p_value"] == 0.124486


def test_air_kyiv_map_is_study_boundary(client, raw_contract):
    payload = client.get("/api/air/kyiv").json()["map"]
    box = raw_contract["region"]["user_bounding_box"]
    assert payload["rendering"] == "boundary_only"
    assert "not a pollution heatmap" in payload["note"]
    assert payload["bounds"] == [[box["south"], box["west"]], [box["north"], box["east"]]]
    feature = payload["study_boundary"]
    assert feature["type"] == "Feature" and feature["geometry"]["type"] == "Polygon"
    ring = feature["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] == [box["west"], box["south"]]
    assert {tuple(p) for p in ring} == {
        (box["west"], box["south"]),
        (box["east"], box["south"]),
        (box["east"], box["north"]),
        (box["west"], box["north"]),
    }
    grid = payload["sampled_grid_center_extent"]
    assert grid["properties"]["note"] == raw_contract["region"]["spatial_note"]
    assert payload["center"] == raw_contract["region"]["center"]


def test_air_kyiv_chart_links(client, raw_contract):
    links = client.get("/api/air/kyiv").json()["charts"]
    assert [link["chart_id"] for link in links] == list(AIR_KYIV_CHARTS)
    for link in links:
        assert link["url"] == f"/api/air/kyiv/charts/{link['chart_id']}"
        assert link["contract"] == raw_contract["charts"][link["chart_id"]]
        image = client.get(link["url"])
        assert image.status_code == 200


def test_charts_served_as_png(client):
    for chart_id in AIR_KYIV_CHARTS:
        response = client.get(f"/api/air/kyiv/charts/{chart_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(PNG_SIGNATURE)


def test_cors_allows_configured_origin_only(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_openapi_lists_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/health", "/api/cases", "/api/air/kyiv", "/api/air/kyiv/charts/{chart_id}"} <= set(paths)
