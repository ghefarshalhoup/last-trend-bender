"""Unit and artifact verification tests for src/four_elements_analysis.py."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.four_elements_analysis import (
    build_unified_monthly_panel,
    compute_kyiv_daily_wind_cloud_sensitivity,
    compute_kyiv_intervention_and_weather_controls,
    compute_kyiv_monthly_four_element_summaries,
    compute_multi_element_trends_and_couplings,
    compute_regional_fire_water_earth_matrix,
)
from src.weather_power_pipeline import STUDY_BOXES

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"


def _reject_nonfinite(constant: str) -> None:
    raise ValueError(f"Non-standard JSON constant found: {constant}")


def _make_synthetic_panel() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for box in STUDY_BOXES:
        for year in range(2015, 2023):
            for mo in range(1, 13):
                season = math.sin(2.0 * math.pi * (mo - 1) / 12.0)
                t2m = 10.0 + 11.0 * season + rng.normal(0.0, 0.3)
                ws10m = 3.6 - 0.5 * season + rng.normal(0.0, 0.15)
                cloud = 58.0 - 14.0 * season + rng.normal(0.0, 1.5)
                ps = 99.6 + rng.normal(0.0, 0.2)
                precip = 2.0 + 0.6 * season + rng.normal(0.0, 0.1)
                vpd = max(0.15, 0.75 + 0.55 * season + (0.20 if (year == 2022 and box.region_id == "west_ukraine_cand") else 0.0))
                gwettop = max(0.25, min(0.85, 0.62 - 0.12 * season - (0.04 if (year == 2022 and box.region_id == "west_ukraine_cand") else 0.0)))
                is_war_ma = year == 2022 and 3 <= mo <= 8
                no2 = (2.1e15 - 0.15e15 * ws10m - (0.55e15 if is_war_ma else 0.0)) if box.region_id == "kyiv_no2_box" else None

                f0 = None
                f2 = None
                if box.role != "external_comparator_weather_only" and 2019 <= year <= 2022 and 3 <= mo <= 8:
                    if box.region_id == "donbas_kharkiv_east":
                        f0 = 0.85 if year == 2022 else 0.45
                        f2 = 0.03 if year == 2022 else 0.22
                    elif box.region_id in ("west_ukraine_cand", "central_interior_cand"):
                        f0 = 0.25 if year == 2022 else 0.50
                        f2 = 0.04 if year == 2022 else 0.08
                    else:
                        f0 = 0.40
                        f2 = 0.05

                rows.append(
                    {
                        "region_id": box.region_id,
                        "month": f"{year:04d}-{mo:02d}",
                        "year": year,
                        "month_num": mo,
                        "area_km2": box.area_km2,
                        "prectotcorr": precip,
                        "qv2m": 6.0 + 3.0 * season,
                        "rh2m": 70.0 - 8.0 * season,
                        "evptrns_mm_day": 1.8 + 1.1 * season,
                        "gwettop": gwettop,
                        "gwetroot": gwettop - 0.03,
                        "gwetprof": gwettop - 0.05,
                        "allsky_srf_alb": 0.18,
                        "ts": t2m + 0.8,
                        "t2m": t2m,
                        "t2m_max": t2m + 4.5,
                        "t2m_min": t2m - 4.0,
                        "dtr_c": 8.5,
                        "allsky_sfc_sw_dwn": 14.0 + 7.0 * season,
                        "clrsky_sfc_sw_dwn": 20.0 + 7.0 * season,
                        "cloud_amt": cloud,
                        "cloud_radiative_attenuation_wm2": 65.0,
                        "ws10m": ws10m,
                        "ps": ps,
                        "vpd_kpa": vpd,
                        "pet_fao56_mm_day": 2.5 + 1.8 * season,
                        "precip_minus_pet_mm_day": precip - (2.5 + 1.8 * season),
                        "ts_minus_t2m_c": 0.8,
                        "no2_mean_molec_cm2": no2,
                        "no2_valid_days": 22 if no2 is not None else np.nan,
                        "no2_calendar_days": 30 if no2 is not None else np.nan,
                        "no2_coverage_fraction": 0.73 if no2 is not None else np.nan,
                        "fire_type0_per_1k_km2_day": f0 if f0 is not None else np.nan,
                        "fire_type2_per_1k_km2_day": f2 if f2 is not None else np.nan,
                    }
                )
    return pd.DataFrame(rows)


class FourElementsUnitTests(unittest.TestCase):
    def test_synthetic_panel_summaries_respect_interval_scale_and_confounders(self) -> None:
        panel = _make_synthetic_panel()
        kyiv = panel[panel["region_id"] == "kyiv_no2_box"].copy()

        comps = compute_kyiv_monthly_four_element_summaries(kyiv)
        by_id = {c["metric_id"]: c for c in comps}
        self.assertEqual(by_id["t2m"]["vs_2015_2019_status"], "withheld_interval_scale")
        self.assertIsNone(by_id["t2m"]["vs_2015_2019_pct_change"])
        self.assertEqual(by_id["ts_minus_t2m_c"]["vs_2015_2019_status"], "withheld_interval_scale")
        self.assertIsNotNone(by_id["no2_mean_molec_cm2"]["vs_2015_2019_pct_change"])
        self.assertIsNone(by_id["fire_type0_per_1k_km2_day"]["baseline_2015_2019_mean"])
        self.assertEqual(by_id["fire_type0_per_1k_km2_day"]["vs_2015_2019_status"], "withheld_insufficient_baseline")
        self.assertIsNone(by_id["fire_type2_per_1k_km2_day"]["baseline_2015_2019_mean"])
        self.assertEqual(by_id["fire_type2_per_1k_km2_day"]["vs_2015_2019_status"], "withheld_insufficient_baseline")

        interv = compute_kyiv_intervention_and_weather_controls(kyiv)
        self.assertLess(interv["box_tiao_weather_controlled_all_months"]["delta_step"], -2.0e14)
        self.assertIn("no_step_counterfactual_no2_anomaly_molec_cm2", interv["weather_residual_monthly_series"][0])
        self.assertIn("no_step_counterfactual_ci95_half_molec_cm2", interv["weather_residual_monthly_series"][0])
        self.assertEqual(
            interv["box_tiao_weather_controlled_excl_apr2022"]["n_obs"],
            interv["box_tiao_weather_controlled_all_months"]["n_obs"] - 1,
        )

        fwe_rows, _ = compute_regional_fire_water_earth_matrix(panel)
        fwe_map = {r["region_id"]: r for r in fwe_rows}
        self.assertGreater(fwe_map["donbas_kharkiv_east"]["fire_type0_pct_change"], 40.0)
        self.assertLess(fwe_map["donbas_kharkiv_east"]["fire_type2_pct_change"], -50.0)
        self.assertGreater(fwe_map["west_ukraine_cand"]["vpd_diff_kpa"], 0.1)
        self.assertLess(fwe_map["west_ukraine_cand"]["fire_type0_pct_change"], -10.0)

        mt = compute_multi_element_trends_and_couplings(panel)
        self.assertTrue(len(mt["kyiv_seasonal_trends"]) >= 10)
        self.assertEqual(len(mt["prewhitened_cross_element_couplings"]), 8)

    def test_daily_wind_cloud_stratification_unit(self) -> None:
        dates = pd.date_range("2018-03-01", "2022-08-31", freq="D")
        ma = [d for d in dates if 3 <= d.month <= 8]
        ws_vals = [2.2 if (i % 2 == 0) else 4.2 for i in range(len(ma))]
        daily_no2 = pd.DataFrame(
            {
                "date": ma,
                "value": [1.2e15 if d.year == 2022 else (2.0e15 - 1e13 * (i % 3)) for i, d in enumerate(ma)],
            }
        )
        daily_power = pd.DataFrame(
            {
                "date": ma,
                "ws10m": ws_vals,
                "cloud_amt": [35.0 if (i % 3 == 0) else 75.0 for i in range(len(ma))],
                "t2m": [18.0] * len(ma),
                "ps": [100.0] * len(ma),
            }
        )
        _, summary = compute_kyiv_daily_wind_cloud_sensitivity(daily_no2, daily_power)
        by_s = {s["stratum_id"]: s for s in summary["strata"]}
        self.assertLess(by_s["low_wind_lt_3ms"]["vs_2019_2021_pct_change"], -35.0)
        self.assertLess(by_s["clear_moderate_cloud_lt_60pct"]["vs_2019_2021_pct_change"], -35.0)

    def test_build_unified_panel_preserves_zero_fill_free_fire_cols(self) -> None:
        panel = _make_synthetic_panel()
        power_sub = panel.drop(
            columns=[
                "area_km2",
                "no2_mean_molec_cm2",
                "no2_valid_days",
                "no2_calendar_days",
                "no2_coverage_fraction",
                "fire_type0_per_1k_km2_day",
                "fire_type2_per_1k_km2_day",
            ]
        ).copy()
        no2_df = panel.loc[panel["region_id"] == "kyiv_no2_box", ["month", "no2_mean_molec_cm2"]].copy()
        no2_df["valid_days"] = 20
        no2_df["calendar_days"] = 30
        no2_df["coverage_fraction"] = 0.6667
        fire_df = pd.DataFrame(
            [
                {
                    "region_id": "donbas_kharkiv_east",
                    "month": "2022-06",
                    "filter_mode": "type0_vegetation_nominal_high",
                    "detections": 100,
                    "detections_per_observed_day": 5.0,
                    "frp_sum_mw": 400.0,
                    "satellite_coverage_fraction": 0.9,
                }
            ]
        )
        merged = build_unified_monthly_panel(power_sub, no2_df, fire_df)
        self.assertEqual(len(merged), len(power_sub))
        self.assertTrue(merged.loc[merged["region_id"] == "poland_krakow", "no2_mean_molec_cm2"].isna().all())


class CommittedFourElementsReportTests(unittest.TestCase):
    def test_committed_json_reports_strict_finite_and_honest_guardrails(self) -> None:
        results_path = REPORTS_DIR / "kyiv_four_elements_results.json"
        quality_path = REPORTS_DIR / "four_elements_quality.json"
        self.assertTrue(results_path.is_file(), f"Missing {results_path}")
        self.assertTrue(quality_path.is_file(), f"Missing {quality_path}")

        results = json.loads(results_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)
        json.loads(quality_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)

        self.assertEqual(results["status"]["before_after_significance"], "not_assessed")
        self.assertEqual(results["status"]["causal_attribution"], "not_established")

        bt = results["kyiv_intervention_and_weather_controls"]
        r2_unadj = bt["box_tiao_unadjusted_all_months"]["r_squared"]
        r2_wth = bt["box_tiao_weather_controlled_all_months"]["r_squared"]
        self.assertGreater(r2_wth, 3.0 * r2_unadj)
        self.assertEqual(
            bt["box_tiao_weather_controlled_excl_apr2022"]["n_obs"],
            bt["box_tiao_weather_controlled_all_months"]["n_obs"] - 1,
        )
        # Counterfactual series includes full no-step trend + weather + 95% AR(1) uncertainty
        row0 = bt["weather_residual_monthly_series"][0]
        self.assertIn("no_step_counterfactual_no2_anomaly_molec_cm2", row0)
        self.assertIn("no_step_counterfactual_ci95_half_molec_cm2", row0)
        self.assertIn("weather_only_no2_anomaly_molec_cm2", row0)
        self.assertGreater(row0["no_step_counterfactual_ci95_half_molec_cm2"], 0.0)
        self.assertIn("box_tiao_weather_controlled_mar_aug_only", bt)

    def test_committed_daily_stratification_matches_csv(self) -> None:
        results = json.loads((REPORTS_DIR / "kyiv_four_elements_results.json").read_text(encoding="utf-8"))
        daily_df = pd.read_csv(REPORTS_DIR / "kyiv_daily_air_weather.csv")
        daily_df["date"] = pd.to_datetime(daily_df["date"])
        ma = daily_df[daily_df["date"].dt.month.isin([3, 4, 5, 6, 7, 8]) & daily_df["no2_molec_cm2"].notna()]
        calm = ma[ma["ws10m"] < 3.0]
        m15 = calm[calm["date"].dt.year.between(2015, 2019)]["no2_molec_cm2"].mean()
        m22 = calm[calm["date"].dt.year == 2022]["no2_molec_cm2"].mean()
        pct_recalc = 100.0 * (m22 - m15) / m15

        strata = {s["stratum_id"]: s for s in results["kyiv_daily_wind_cloud_sensitivity"]["strata"]}
        self.assertAlmostEqual(strata["low_wind_lt_3ms"]["vs_2015_2019_pct_change"], pct_recalc, places=1)
        self.assertLess(strata["low_wind_lt_3ms"]["vs_2015_2019_pct_change"], -15.0)

    def test_committed_regional_contrast_and_charts_exist(self) -> None:
        results = json.loads((REPORTS_DIR / "kyiv_four_elements_results.json").read_text(encoding="utf-8"))
        reg_map = {r["region_id"]: r for r in results["regional_fire_water_earth_contrast"]["regions"]}
        self.assertGreater(reg_map["donbas_kharkiv_east"]["fire_type0_pct_change"], 50.0)
        self.assertLess(reg_map["donbas_kharkiv_east"]["fire_type2_pct_change"], -70.0)
        self.assertGreater(reg_map["west_ukraine_cand"]["vpd_diff_kpa"], 0.10)
        self.assertLess(reg_map["west_ukraine_cand"]["fire_type0_pct_change"], -10.0)

        # Ensure T2M_RANGE diurnal temperature range is physical (<16 C), not monthly extreme spread (>20 C)
        kyiv_comps = {c["metric_id"]: c for c in results["kyiv_four_element_comparisons"]}
        self.assertLess(kyiv_comps["dtr_c"]["target_2022_mean"], 15.0)
        self.assertGreater(kyiv_comps["dtr_c"]["target_2022_mean"], 5.0)
        self.assertLess(kyiv_comps["vpd_kpa"]["target_2022_mean"], 0.90)
        self.assertIsNone(kyiv_comps["fire_type0_per_1k_km2_day"]["baseline_2015_2019_mean"])
        self.assertEqual(kyiv_comps["fire_type0_per_1k_km2_day"]["vs_2015_2019_status"], "withheld_insufficient_baseline")
        self.assertIsNone(kyiv_comps["fire_type2_per_1k_km2_day"]["baseline_2015_2019_mean"])
        self.assertIn("firms_cmr_matched_outage_sensitivity", results["regional_fire_water_earth_contrast"])
        self.assertIn("spatial_mask_audit", results["regional_fire_water_earth_contrast"])

        for chart in results["charts"].values():
            p = REPO_ROOT / chart["png_path"]
            self.assertTrue(p.is_file(), f"Missing chart {p}")
            self.assertGreater(p.stat().st_size, 20_000)


if __name__ == "__main__":
    unittest.main()
