"""Unit tests for Kyiv NO2 coverage/weather sensitivities and Krakow/Prague comparison."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from src.atlas_exports import CATALOG_VARIABLES
from src.kyiv_sensitivities import (
    KYIV_WEATHER_COVARIATES,
    build_krakow_prague_comparison,
    build_kyiv_no2_sensitivities,
    evaluate_monthly_fe_hac_trend,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"


class KyivSensitivitiesAndComparatorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.panel_df = pd.read_csv(REPORTS_DIR / "four_elements_monthly_panel.csv")
        cls.air_results = json.loads((REPORTS_DIR / "air_no2_results.json").read_text(encoding="utf-8"))
        cls.kyiv_four = json.loads((REPORTS_DIR / "kyiv_four_elements_results.json").read_text(encoding="utf-8"))
        regional_path = REPORTS_DIR / "atlas_no2_regional.json"
        cls.no2_regional = (
            json.loads(regional_path.read_text(encoding="utf-8"))
            if regional_path.is_file()
            else None
        )
        cls.power_specs = [
            s for s in CATALOG_VARIABLES
            if s.metric_id != "no2_mean_molec_cm2" and not s.metric_id.startswith("fire_")
        ]

    def test_fe_hac_matches_air_no2_full_record_and_guards_short_series(self) -> None:
        air_df = pd.DataFrame(self.air_results["monthly_series"])
        got = evaluate_monthly_fe_hac_trend(
            air_df,
            "no2_mean_molec_cm2",
            "full_record_test",
            "Kyiv full record",
        )
        canon = self.air_results["statistics"]["multi_year_seasonality_aware_trend"]["full_record"]
        self.assertEqual(got["status"], "assessed")
        self.assertEqual(got["n_months"], 90)
        self.assertEqual(got["degrees_of_freedom"], 77)
        self.assertAlmostEqual(got["slope_per_year"], canon["slope_molec_cm2_per_year"], delta=1.0)
        self.assertAlmostEqual(got["p_value"], canon["p_value"], places=5)
        self.assertFalse(got["significant"])
        self.assertAlmostEqual(
            got["nonparametric_sensitivity"]["hamed_rao_mk"]["p_value_hamed_rao"],
            canon["nonparametric_sensitivity"]["hamed_rao_mk"]["p_value_hamed_rao"],
            places=5,
        )

        too_short = evaluate_monthly_fe_hac_trend(
            air_df.head(20),
            "no2_mean_molec_cm2",
            "short",
            "Short window",
        )
        self.assertEqual(too_short["status"], "insufficient_evidence")
        self.assertIsNone(too_short["p_value"])

    def test_calendar_month_hac_respects_gaps_over_row_adjacency(self) -> None:
        # Removing months 11 & 12 leaves discontinuous rows; calendar-lag HAC differs from contiguous row order.
        air_df = pd.DataFrame(self.air_results["monthly_series"])
        air_df = air_df[~air_df["flagged_below_50_pct"].astype(bool)].copy()
        res = evaluate_monthly_fe_hac_trend(
            air_df,
            "no2_mean_molec_cm2",
            "unflagged",
            "Unflagged",
            allow_partial_calendar_months=True,
        )
        self.assertEqual(res["n_months"], 53)
        self.assertEqual(res["calendar_months_included"], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertGreater(res["p_value"], 0.01)
        self.assertLess(res["p_value"], 0.015)

    def test_kyiv_no2_coverage_and_weather_sensitivities(self) -> None:
        sens = build_kyiv_no2_sensitivities(
            air_results=self.air_results,
            panel_df=self.panel_df,
            kyiv_four_results=self.kyiv_four,
        )
        self.assertEqual(sens["n_total_months"], 90)
        self.assertEqual(sens["n_flagged_below_50_pct"], 37)
        self.assertEqual(sens["n_unflagged_months"], 53)
        self.assertEqual(sens["dropped_calendar_months_completely_excluded"], [11, 12])

        cov = sens["coverage_exclusion_sensitivity"]
        self.assertFalse(cov["all_months_full_record"]["significant"])
        self.assertTrue(cov["unflagged_ge50pct_full_record"]["significant"])
        self.assertFalse(cov["unflagged_ge50pct_pre_invasion"]["significant"])
        self.assertTrue(cov["verdict_flips_full_record"])
        self.assertFalse(cov["verdict_flips_pre_invasion"])

        wx = sens["weather_adjusted_fe_hac_trends"]
        self.assertEqual(wx["covariates"], list(KYIV_WEATHER_COVARIATES))
        self.assertFalse(wx["all_months_full_record"]["significant"])
        self.assertTrue(wx["unflagged_ge50pct_full_record"]["significant"])
        self.assertIsNotNone(wx["box_tiao_reference"]["weather_controlled_all_months"])

    def test_krakow_prague_comparison_with_and_without_regional_no2(self) -> None:
        comp_without = build_krakow_prague_comparison(
            self.panel_df,
            self.power_specs,
            air_results=self.air_results,
            no2_regional=None,
        )
        self.assertEqual(comp_without["metrics_count"], 22)
        self.assertEqual(comp_without["no2_cross_city_comparison"]["status"], "not_available")

        by_metric = {m["metric_id"]: m for m in comp_without["metrics"]}
        ws = by_metric["ws10m"]
        self.assertGreater(ws["kyiv_no2_box"]["diff_vs_2015_2019"], 0.0)
        self.assertLess(ws["poland_krakow"]["diff_vs_2015_2019"], 0.0)
        self.assertLess(ws["czechia_prague"]["diff_vs_2015_2019"], 0.0)
        self.assertFalse(ws["same_direction_as_krakow_vs_2015_2019"])
        self.assertFalse(ws["same_direction_as_prague_vs_2015_2019"])

        if self.no2_regional is not None:
            comp_with = build_krakow_prague_comparison(
                self.panel_df,
                self.power_specs,
                air_results=self.air_results,
                no2_regional=self.no2_regional,
            )
            no2 = comp_with["no2_cross_city_comparison"]
            self.assertEqual(no2["status"], "available")
            self.assertAlmostEqual(no2["kyiv_no2_box"]["pct_change"], -27.96, places=2)
            self.assertAlmostEqual(no2["kharkiv_city"]["pct_change"], -29.40, places=2)
            self.assertAlmostEqual(no2["poland_krakow"]["pct_change"], -11.01, places=2)
            self.assertAlmostEqual(no2["czechia_prague"]["pct_change"], -7.53, places=2)


if __name__ == "__main__":
    unittest.main()
