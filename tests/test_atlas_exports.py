"""Unit and scientific contract tests for src.atlas_exports."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.atlas_exports import (
    CATALOG_VARIABLES,
    FIRE_LEGACY_METHOD_ID,
    FIRE_MATCHED_SENSITIVITY_METHOD_ID,
    FIRE_PRIMARY_METHOD_ID,
    generate_atlas_exports,
)


class AtlasExportsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmpdir.name) / "reports"
        # Stage required source reports into temporary directory cleanly
        src_reports = Path(__file__).resolve().parents[1] / "reports"
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "four_elements_monthly_panel.csv",
            "fire_viirs_results.json",
            "kyiv_four_elements_results.json",
            "air_no2_results.json",
        ):
            (cls.out_dir / name).write_bytes((src_reports / name).read_bytes())
        regional_no2 = src_reports / "atlas_no2_regional.json"
        if regional_no2.exists():
            (cls.out_dir / "atlas_no2_regional.json").write_bytes(regional_no2.read_bytes())
        cls.paths = generate_atlas_exports(cls.out_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def _load(self, key: str):
        raw = self.paths[key].read_text(encoding="utf-8")
        return json.loads(raw)

    def test_catalog_contains_25_complete_variable_contracts(self) -> None:
        cat = self._load("atlas_catalog")
        self.assertEqual(cat["metric_count"], 25)
        self.assertEqual(len(CATALOG_VARIABLES), 25)
        self.assertEqual(len(cat["variables"]), 25)

        counts = {k: len(v) for k, v in cat["variable_ids_by_element"].items()}
        self.assertEqual(counts, {"air": 6, "fire": 7, "land": 6, "water": 6})

        required_fields = {
            "metric_id",
            "element_id",
            "element_label",
            "label",
            "plain_definition",
            "units",
            "dates",
            "supported_baselines",
            "spatial_support",
            "method_id",
            "uncertainty_and_status",
            "sources",
            "limitations",
        }
        for var in cat["variables"]:
            self.assertTrue(required_fields.issubset(var.keys()), var.get("metric_id"))
            self.assertIsInstance(var["plain_definition"], str)
            self.assertGreater(len(var["plain_definition"].strip()), 20)
            self.assertTrue(var["sources"])
            self.assertTrue(var["limitations"])
            baselines = {b["baseline_id"]: b for b in var["supported_baselines"]}
            if var["metric_id"].startswith("fire_"):
                self.assertFalse(baselines["2015-2019"]["supported"])
                self.assertEqual(baselines["2015-2019"]["status"], "withheld_insufficient_baseline")
                self.assertTrue(baselines["2019-2021"]["supported"])
            else:
                self.assertTrue(baselines["2015-2019"]["supported"])
                self.assertTrue(baselines["2019-2021"]["supported"])

    def test_fire_primary_separation_outage_flags_and_cells(self) -> None:
        fire = self._load("atlas_fire_ukraine")
        self.assertEqual(fire["element_id"], "fire")
        self.assertEqual(fire["primary_indicator"], "fire_type0_per_1k_km2_day")
        baselines = {b["baseline_id"]: b for b in fire["supported_baselines"]}
        self.assertFalse(baselines["2015-2019"]["supported"])
        self.assertTrue(fire["quality_flags"]["unsupported_baseline_2015_2019"])
        self.assertEqual(fire["quality_flags"]["cmr_orbit_outage_2022"]["missing_dates_count_2022"], 16)

        donbas = fire["result"]["regions"]["donbas_kharkiv_east"]["seasonal_comparisons_mar_aug"]["type0_vegetation_nominal_high"]
        self.assertEqual(donbas["primary_metric"]["method_id"], FIRE_PRIMARY_METHOD_ID)
        self.assertEqual(donbas["matched_dates_169d_ukr_adm0_sensitivity"]["method_id"], FIRE_MATCHED_SENSITIVITY_METHOD_ID)
        self.assertTrue(donbas["matched_dates_169d_ukr_adm0_sensitivity"]["sensitivity_only"])
        self.assertEqual(donbas["legacy_unnormalized_rate"]["method_id"], FIRE_LEGACY_METHOD_ID)
        self.assertTrue(donbas["legacy_unnormalized_rate"]["legacy_only"])

        self.assertAlmostEqual(donbas["primary_metric"]["vs_2019_2021"]["pct_change"], 64.86, places=2)
        self.assertAlmostEqual(donbas["matched_dates_169d_ukr_adm0_sensitivity"]["pct_change_matched_dates_169d"], 104.3, places=2)
        self.assertIsNone(donbas["primary_metric"]["vs_2015_2019"]["pct_change"])
        self.assertEqual(donbas["primary_metric"]["vs_2015_2019"]["pct_change_status"], "withheld_insufficient_baseline")

        # Complete monthly cell package + registry check
        cells = self._load("atlas_fire_cells")
        self.assertEqual(len(cells["cell_registry"]), 1305)
        self.assertEqual(len(cells["monthly_cells"]), 15751)
        self.assertEqual(len(cells["cmr_month_coverage"]), 24)
        aug22 = next(m for m in cells["cmr_month_coverage"] if m["month"] == "2022-08")
        self.assertEqual(aug22["satellite_observed_days"], 21)
        self.assertTrue(aug22["has_cmr_outage_gap"])

    def test_water_and_earth_context_geometries_and_interval_withholding(self) -> None:
        water = self._load("atlas_water_ukraine")
        earth = self._load("atlas_earth_ukraine")
        self.assertEqual(water["element_id"], "water")
        self.assertEqual(water["primary_indicator"], "prectotcorr")
        self.assertEqual(earth["element_id"], "land")
        self.assertEqual(earth["element_label"], "Earth")
        self.assertEqual(earth["primary_indicator"], "gwettop")

        self.assertEqual(len(water["map"]["study_boxes"]["features"]), 6)
        self.assertEqual(len(earth["map"]["study_boxes"]["features"]), 6)
        self.assertIn("do not rule out localized drought", water["map"]["note"].lower())

        kyiv_water = water["result"]["regions"]["kyiv_no2_box"]["metrics"]
        p_pet = kyiv_water["precip_minus_pet_mm_day"]["seasonal_mar_aug"]["vs_2015_2019"]
        self.assertIsNone(p_pet["pct_change"])
        self.assertEqual(p_pet["pct_change_status"], "withheld_interval_scale")
        self.assertIsNotNone(p_pet["abs_diff"])

        kyiv_earth = earth["result"]["regions"]["kyiv_no2_box"]["metrics"]
        ts_cmp = kyiv_earth["ts"]["seasonal_mar_aug"]["vs_2015_2019"]
        self.assertIsNone(ts_cmp["pct_change"])
        self.assertEqual(ts_cmp["pct_change_status"], "withheld_interval_scale")

    def test_air_weather_includes_kyiv_sensitivities_and_krakow_prague(self):
        import json

        air_weather = json.loads((self.out_dir / "atlas_air_weather_ukraine.json").read_text(encoding="utf-8"))
        res = air_weather["result"]
        self.assertIn("kyiv_no2_sensitivities", res)
        self.assertIn("krakow_prague_2022_comparison", res)

        sens = res["kyiv_no2_sensitivities"]
        self.assertEqual(sens["n_flagged_below_50_pct"], 37)
        self.assertEqual(sens["dropped_calendar_months_completely_excluded"], [11, 12])
        self.assertTrue(sens["coverage_exclusion_sensitivity"]["unflagged_ge50pct_full_record"]["significant"])
        self.assertFalse(sens["coverage_exclusion_sensitivity"]["unflagged_ge50pct_pre_invasion"]["significant"])

        kp = res["krakow_prague_2022_comparison"]
        self.assertEqual(kp["metrics_count"], 22)
        if (self.out_dir / "atlas_no2_regional.json").exists():
            self.assertEqual(kp["no2_cross_city_comparison"]["status"], "available")
        else:
            self.assertEqual(kp["no2_cross_city_comparison"]["status"], "not_available")


if __name__ == "__main__":
    unittest.main()
