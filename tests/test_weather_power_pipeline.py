"""Offline unit tests for src/weather_power_pipeline.py."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from src.fire_analysis import PROPOSED_REGIONS
from src.weather_power_pipeline import (
    KYIV_DAILY_PARAMETERS,
    RAW_MONTHLY_PARAMETERS,
    STUDY_BOXES,
    aggregate_multipoint_with_spherical_weights,
    generate_box_grid_points,
    parse_daily_power_cache,
    parse_monthly_power_cache,
)


def _sample_monthly_params(year_start: int = 2015, year_end: int = 2022) -> dict:
    ym_keys = [f"{y:04d}{m:02d}" for y in range(year_start, year_end + 1) for m in range(1, 13)]
    # Include YYYY13 annual summary key to verify parser ignores it
    ym_keys_with_annual = ym_keys + [f"{y:04d}13" for y in range(year_start, year_end + 1)]
    defaults = {
        "PRECTOTCORR": 2.0,
        "QV2M": 6.5,
        "RH2M": 70.0,
        "EVPTRNS": 2.45,
        "GWETTOP": 0.62,
        "GWETROOT": 0.58,
        "GWETPROF": 0.56,
        "ALLSKY_SRF_ALB": 0.18,
        "TS": 12.5,
        "T2M": 11.0,
        "T2M_RANGE": 10.0,
        "T2M_MAX": 32.0,
        "T2M_MIN": -2.0,
        "ALLSKY_SFC_SW_DWN": 14.0,
        "CLRSKY_SFC_SW_DWN": 20.0,
        "CLOUD_AMT": 52.0,
        "WS10M": 3.4,
        "PS": 99.5,
    }
    params = {}
    for name in RAW_MONTHLY_PARAMETERS:
        series = {k: defaults[name] for k in ym_keys_with_annual}
        # Inject one NASA POWER sentinel fill to ensure NaN preservation
        series["202002"] = -999.0
        params[name] = series
    return params


class WeatherPowerPipelineTests(unittest.TestCase):
    def test_study_boxes_align_with_fire_regions(self) -> None:
        fire_by_id = {r.region_id: r for r in PROPOSED_REGIONS}
        power_by_id = {b.region_id: b for b in STUDY_BOXES}
        for rid in (
            "kyiv_no2_box",
            "kyiv_north_belt",
            "donbas_kharkiv_east",
            "south_steppe_belt",
            "central_interior_cand",
            "west_ukraine_cand",
        ):
            self.assertIn(rid, power_by_id)
            self.assertAlmostEqual(power_by_id[rid].south, fire_by_id[rid].south)
            self.assertAlmostEqual(power_by_id[rid].north, fire_by_id[rid].north)
            self.assertAlmostEqual(power_by_id[rid].west, fire_by_id[rid].west)
            self.assertAlmostEqual(power_by_id[rid].east, fire_by_id[rid].east)
        self.assertIn("poland_krakow", power_by_id)
        self.assertIn("czechia_prague", power_by_id)

    def test_grid_generation_and_spherical_aggregation(self) -> None:
        pts = generate_box_grid_points(50.2, 50.7, 30.273, 30.773, nx=3, ny=3)
        self.assertEqual(len(pts), 9)
        self.assertEqual(pts[0], (50.2, 30.273))
        self.assertEqual(pts[-1], (50.7, 30.773))

        agg = aggregate_multipoint_with_spherical_weights(
            [
                (0.0, {"T2M": {"202203": 10.0, "202204": -999.0, "202205": -999.0}}),
                (60.0, {"T2M": {"202203": 20.0, "202204": 15.0, "202205": -999.0}}),
            ]
        )
        self.assertAlmostEqual(agg["T2M"]["202203"], 40.0 / 3.0, places=4)
        self.assertAlmostEqual(agg["T2M"]["202204"], 15.0, places=4)
        self.assertEqual(agg["T2M"]["202205"], -999.0)

    def test_parse_monthly_and_daily_power_caches_and_derivations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            m_path = Path(tmp) / "monthly.json"
            m_payload = {
                "schema_version": "1.0.0",
                "source_api": "https://power.larc.nasa.gov/api/temporal/monthly/point",
                "spatial_sampling": "spherical_cosine_lat_weighted_3x3_grid",
                "regions": {
                    "kyiv_no2_box": {
                        "metadata": {
                            "region_id": "kyiv_no2_box",
                            "name": "Kyiv Air-Matched Box",
                            "role": "primary_urban_study",
                            "center_lat": 50.45,
                            "center_lon": 30.523,
                            "elevation_m": 179.0,
                        },
                        "parameters": _sample_monthly_params(2015, 2022),
                    }
                },
            }
            m_path.write_text(json.dumps(m_payload), encoding="utf-8")
            m_df, m_meta = parse_monthly_power_cache(m_path)
            self.assertEqual(len(m_df), 8 * 12)
            self.assertIn("kyiv_no2_box", m_meta["regions"])
            feb20 = m_df[m_df["month"] == "2020-02"].iloc[0]
            self.assertTrue(math.isnan(feb20["t2m"]))
            self.assertTrue(math.isnan(feb20["vpd_kpa"]))
            mar22 = m_df[m_df["month"] == "2022-03"].iloc[0]
            self.assertGreater(mar22["vpd_kpa"], 0.0)
            self.assertLess(mar22["vpd_kpa"], 0.7)  # Regression guard: extreme monthly T2M_MAX=32C must not inflate VPD
            self.assertGreater(mar22["pet_fao56_mm_day"], 0.0)
            self.assertAlmostEqual(mar22["ts_minus_t2m_c"], 1.5, places=4)
            self.assertAlmostEqual(mar22["dtr_c"], 10.0, places=4)
            self.assertGreater(mar22["cloud_radiative_attenuation_wm2"], 60.0)

            d_path = Path(tmp) / "daily.json"
            daily_params = {
                p: {"20220301": 2.1, "20220302": -999.0}
                for p in KYIV_DAILY_PARAMETERS
            }
            daily_params["TS"] = {"20220301": 5.0, "20220302": 4.0}
            daily_params["T2M"] = {"20220301": 3.0, "20220302": 2.0}
            daily_params["CLRSKY_SFC_SW_DWN"] = {"20220301": 18.0, "20220302": 18.0}
            daily_params["ALLSKY_SFC_SW_DWN"] = {"20220301": 12.0, "20220302": 12.0}
            d_path.write_text(
                json.dumps({"metadata": {"region_id": "kyiv_no2_box"}, "parameters": daily_params, "parameter_metadata": {}}),
                encoding="utf-8",
            )
            d_df, _ = parse_daily_power_cache(d_path)
            self.assertEqual(len(d_df), 2)
            self.assertAlmostEqual(d_df.iloc[0]["ts_minus_t2m_c"], 2.0, places=4)
            self.assertTrue(math.isnan(d_df.iloc[1]["ws10m"]))


if __name__ == "__main__":
    unittest.main()
