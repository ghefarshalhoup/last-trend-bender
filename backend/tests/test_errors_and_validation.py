"""Validation gate and error responses."""

from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.catalog import AIR_KYIV_CHARTS
from backend.config import Settings
from backend.main import create_app
from backend.schemas import AirResultsContract


def _error(response):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


@pytest.mark.parametrize("chart_id", ["unknown", "air_no2_results", "no2_monthly.png", "..%2Fair_no2_results.json"])
def test_unknown_chart_rejected(client, chart_id):
    response = client.get(f"/api/air/kyiv/charts/{chart_id}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_unknown_chart_lists_allowlist(client):
    error = _error(client.get("/api/air/kyiv/charts/unknown"))
    assert error["code"] == "chart_not_found"
    assert error["details"] == {"allowed_chart_ids": list(AIR_KYIV_CHARTS)}


def test_unknown_route_and_method(client):
    assert _error(client.get("/api/nope"))["code"] == "not_found"
    response = client.post("/api/air/kyiv")
    assert response.status_code == 405
    assert _error(response)["code"] == "method_not_allowed"


def _assert_unavailable(api, problem_code):
    health = api.get("/api/health")
    assert health.status_code == 503
    air = health.json()["datasets"]["air_kyiv"]
    assert health.json()["status"] == "degraded" and air["ready"] is False
    assert problem_code in [p["code"] for p in air["problems"]]

    study = api.get("/api/air/kyiv")
    assert study.status_code == 503
    error = _error(study)
    assert error["code"] == "data_unavailable"
    assert problem_code in [p["code"] for p in error["details"]]

    chart = api.get("/api/air/kyiv/charts/monthly_timeline")
    assert chart.status_code == 503

    air_case = next(e for e in api.get("/api/cases").json()["cases"][0]["elements"] if e["element_id"] == "air")
    assert air_case["status"] == "unavailable" and air_case["reason"] == "data_not_ready"
    return air


def test_missing_results_file(make_client):
    air = _assert_unavailable(make_client(write_results=False), "results_missing")
    assert air["schema_version"] is None


def test_malformed_json(make_client):
    _assert_unavailable(make_client(text="{ not json"), "results_unreadable")


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_rejected(make_client, raw_contract, token):
    text = json.dumps(raw_contract).replace('"pct_change": -27.9594', f'"pct_change": {token}', 1)
    assert token in text
    _assert_unavailable(make_client(text=text), "results_unreadable")


def _drop_before_after(payload):
    del payload["statistics"]["before_after_seasonal_inference"]


def _fill_not_assessed_p_value(payload):
    payload["statistics"]["before_after_seasonal_inference"]["p_value"] = 0.03


def _claim_significance(payload):
    payload["statistics"]["before_after_seasonal_inference"]["statistical_significance_claimed"] = True


def _invert_bbox(payload):
    box = payload["region"]["user_bounding_box"]
    box["west"], box["east"] = box["east"], box["west"]


def _zero_fill_missing_month(payload):
    payload["monthly_series"][0]["valid_days"] = 0


def _withheld_pct_with_value(payload):
    payload["comparisons"]["primary_2015_2019_valid_day"]["pct_change_status"] = "withheld_missing_data"


def _computed_pct_without_value(payload):
    payload["comparisons"]["primary_2015_2019_valid_day"]["pct_change"] = None


def _unsupported_schema(payload):
    payload["schema_version"] = "2.0.0"


def _unordered_months(payload):
    series = payload["monthly_series"]
    series[0], series[1] = series[1], series[0]


def _drop_sensitivity_baseline(payload):
    del payload["comparisons"]["sensitivity_2019_2021_valid_day"]


def _string_boolean(payload):
    payload["monthly_series"][0]["flagged_below_50_pct"] = "false"


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_before_after,
        _fill_not_assessed_p_value,
        _claim_significance,
        _invert_bbox,
        _zero_fill_missing_month,
        _withheld_pct_with_value,
        _computed_pct_without_value,
        _unsupported_schema,
        _unordered_months,
        _drop_sensitivity_baseline,
        _string_boolean,
    ],
)
def test_contract_violations_rejected(make_client, mutate):
    air = _assert_unavailable(make_client(mutate=mutate), "results_invalid")
    problem = next(p for p in air["problems"] if p["code"] == "results_invalid")
    assert problem["details"], "validation errors should be listed"


def test_additive_contract_fields_pass_through(make_client):
    def add_field(payload):
        payload["new_section"] = {"note": "added by analysis"}

    api = make_client(mutate=add_field)
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/air/kyiv").json()["result"]["new_section"] == {"note": "added by analysis"}


def test_null_month_mean_is_preserved(make_client):
    def blank_month(payload):
        point = payload["monthly_series"][0]
        point.update(no2_mean_molec_cm2=None, valid_days=0, coverage_fraction=0.0)

    body = make_client(mutate=blank_month).get("/api/air/kyiv").json()
    point = body["result"]["monthly_series"][0]
    assert "no2_mean_molec_cm2" in point and point["no2_mean_molec_cm2"] is None


def test_missing_chart_degrades_only_that_chart(make_client):
    api = make_client(drop_charts=("matched_months",))
    health = api.get("/api/health")
    assert health.status_code == 503
    air = health.json()["datasets"]["air_kyiv"]
    assert air["charts"]["matched_months"] is False and air["charts"]["monthly_timeline"] is True
    assert "chart_missing" in [p["code"] for p in air["problems"]]

    assert api.get("/api/air/kyiv").status_code == 200
    assert api.get("/api/air/kyiv/charts/monthly_timeline").status_code == 200
    missing = api.get("/api/air/kyiv/charts/matched_months")
    assert missing.status_code == 503
    assert _error(missing)["code"] == "chart_unavailable"


def test_chart_path_mismatch_detected(make_client):
    def repoint(payload):
        payload["charts"]["monthly_timeline"]["png_path"] = "reports/other.png"

    air = make_client(mutate=repoint).get("/api/health").json()["datasets"]["air_kyiv"]
    assert air["charts"]["monthly_timeline"] is False
    assert "chart_contract_mismatch" in [p["code"] for p in air["problems"]]


def test_non_png_chart_detected(make_client, tmp_path):
    make_client()  # stage a valid copy of the reports in tmp_path
    reports = tmp_path / "reports"
    (reports / "no2_monthly.png").write_bytes(b"not an image")
    api = TestClient(create_app(Settings(reports_dir=reports, air_kyiv_results=reports / "air_no2_results.json")))
    air = api.get("/api/health").json()["datasets"]["air_kyiv"]
    assert "chart_invalid" in [p["code"] for p in air["problems"]]
    assert api.get("/api/air/kyiv/charts/monthly_timeline").status_code == 503


# --- Regression: chart entry missing from the contract (review finding 1) ---


def test_missing_chart_entry_omits_chart_instead_of_500(make_client):
    def drop_entry(payload):
        del payload["charts"]["matched_months"]

    api = make_client(mutate=drop_entry)  # TestClient re-raises server errors, so a 500 fails here
    study = api.get("/api/air/kyiv")
    assert study.status_code == 200
    assert [link["chart_id"] for link in study.json()["charts"]] == ["monthly_timeline", "seasonal_comparison"]

    air = api.get("/api/health").json()["datasets"]["air_kyiv"]
    assert air["charts"]["matched_months"] is False
    assert "chart_contract_mismatch" in [p["code"] for p in air["problems"]]

    missing = api.get("/api/air/kyiv/charts/matched_months")
    assert missing.status_code == 503 and _error(missing)["code"] == "chart_unavailable"
    assert api.get("/api/air/kyiv/charts/monthly_timeline").status_code == 200


def test_unavailable_charts_never_linked(make_client):
    def drop_all(payload):
        payload["charts"] = {}

    study = make_client(mutate=drop_all).get("/api/air/kyiv")
    assert study.status_code == 200
    assert study.json()["charts"] == []


# --- Regression: strict types, no coercion (review finding 2) ---


def _numeric_leaves(obj, path=()):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield path
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from _numeric_leaves(value, path + (key,))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _numeric_leaves(value, path + (index,))


def _set(obj, path, value):
    for step in path[:-1]:
        obj = obj[step]
    obj[path[-1]] = value


def _get(obj, path):
    for step in path:
        obj = obj[step]
    return obj


@pytest.mark.parametrize("as_type", ["string", "bool"])
def test_every_numeric_value_rejects_coercible_substitutes(raw_contract, as_type):
    """Each numeric value in the real artifact must be declared and strictly typed.

    Replacing any one of them with its string form (e.g. "123") or a boolean
    must fail validation; otherwise it would be served unchanged as a string.
    """
    leaves = list(_numeric_leaves(raw_contract))
    assert len(leaves) > 300
    accepted = []
    for path in leaves:
        payload = copy.deepcopy(raw_contract)
        original = _get(payload, path)
        _set(payload, path, str(original) if as_type == "string" else True)
        try:
            AirResultsContract.model_validate(payload)
        except ValidationError:
            continue
        accepted.append(".".join(map(str, path)))
    assert accepted == [], f"{as_type} substitutes accepted at: {accepted[:10]}"


def _numeric_string_measurement(payload):
    payload["monthly_series"][0]["no2_mean_molec_cm2"] = "123"


def _numeric_string_count(payload):
    payload["monthly_series"][0]["valid_days"] = "19"


def _fractional_count(payload):
    payload["monthly_series"][0]["valid_days"] = 19.5


def _numeric_string_in_baseline(payload):
    payload["matched_months"][0]["primary_2015_2019"]["mean_molec_cm2"] = "3030000852351754.5"


def _numeric_string_in_trend_detail(payload):
    trend = payload["statistics"]["multi_year_seasonality_aware_trend"]["full_record"]
    trend["nonparametric_sensitivity"]["hamed_rao_mk"]["p_value_hamed_rao"] = "0.15"


@pytest.mark.parametrize(
    "mutate",
    [
        _numeric_string_measurement,
        _numeric_string_count,
        _fractional_count,
        _numeric_string_in_baseline,
        _numeric_string_in_trend_detail,
    ],
)
def test_numeric_strings_never_reach_frontend(make_client, mutate):
    _assert_unavailable(make_client(mutate=mutate), "results_invalid")


def test_integers_still_accepted_for_float_fields(make_client):
    def integer_measurement(payload):
        payload["monthly_series"][0]["no2_mean_molec_cm2"] = 4610816836105263

    api = make_client(mutate=integer_measurement)
    assert api.get("/api/air/kyiv").json()["result"]["monthly_series"][0]["no2_mean_molec_cm2"] == 4610816836105263
