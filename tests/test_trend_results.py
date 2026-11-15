import json
from pathlib import Path

import pytest

from src import trend_results as tr

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    out = tmp_path_factory.mktemp("no2_regional")
    return tr.build(REPO / "reports", REPO / "data" / "frozen" / "no2_regional", out)


def _row(payload, region, metric, window):
    return next(
        r for r in payload["results"]
        if (r["region_id"], r["metric_id"], r["window_id"]) == (region, metric, window)
    )


def test_kyiv_no2_matches_published_result(payload):
    published = json.loads((REPO / "reports" / "air_no2_results.json").read_text(encoding="utf-8"))
    ref = published["statistics"]["multi_year_seasonality_aware_trend"]["full_record"]
    row = _row(payload, "kyiv_no2_box", "no2_mean_molec_cm2", "full_record")
    assert row["slope_per_year"] == pytest.approx(ref["slope_molec_cm2_per_year"])
    assert row["p_value"] == pytest.approx(ref["p_value"])
    assert row["significant"] is False


def test_every_row_follows_the_contract(payload):
    keys = set()
    for r in payload["results"]:
        key = (r["region_id"], r["metric_id"], r["window_id"])
        assert key not in keys
        keys.add(key)
        assert r["window_id"] in tr.WINDOWS
        assert r["caveats"] and len(r["caveats"]) <= 5
        if r["status"] == "assessed":
            assert r["ci_low"] <= r["slope_per_year"] <= r["ci_high"]
            assert 0 <= r["p_value"] <= r["p_value_fdr"] <= 1
            assert r["significant"] == (r["p_value_fdr"] < tr.ALPHA) or "coverage_sensitivity" in r
        else:
            assert r["slope_per_year"] is None and r["p_value"] is None and r["significant"] is None


def test_fire_is_insufficient_evidence(payload):
    row = _row(payload, "donbas_kharkiv_east", "fire_type0_per_1k_km2_day", "full_record")
    assert row["status"] == "insufficient_evidence"


def test_coverage_rule_blocks_unconfirmable_no2_verdicts(payload):
    for r in payload["results"]:
        sens = r.get("coverage_sensitivity")
        if sens and r["status"] == "assessed" and r["significant"]:
            assert sens["robust"] is True
    prague = _row(payload, "czechia_prague", "no2_mean_molec_cm2", "full_record")
    assert prague["status"] == "insufficient_evidence"
    assert prague["unconfirmed_estimate"]["p_value_fdr"] < tr.ALPHA


def test_regional_no2_monthly_shape(tmp_path):
    monthly = tr.build_regional_no2(REPO / "data" / "frozen" / "no2_regional", tmp_path)
    assert set(monthly) == set(tr.NO2_REGIONAL_FILES)
    for df in monthly.values():
        assert len(df) == 90 and df["month"].iloc[0] == "2015-03" and df["month"].iloc[-1] == "2022-08"


def test_no2_atlas_payload_matches_monthly_files_and_adds_kharkiv():
    payload = tr.build_no2_atlas_payload(REPO / "data" / "frozen" / "no2_regional")
    assert set(payload["regions"]) == set(tr.NO2_REGIONAL_FILES)
    assert [f["properties"]["region_id"] for f in payload["extra_places"]] == ["kharkiv_city"]
    for region in payload["regions"].values():
        assert len(region["monthly_series"]) == 90
        cmp = region["seasonal_mar_aug"]["vs_2015_2019"]
        assert cmp["abs_diff"] == pytest.approx(cmp["target_mean"] - cmp["baseline_mean"])
        for p in region["monthly_series"]:
            assert p["flagged_below_50_pct"] == (p["valid_days"] / p["calendar_days"] < 0.5)
