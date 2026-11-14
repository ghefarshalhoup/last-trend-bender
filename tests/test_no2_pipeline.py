"""Focused unit and integration tests for Giovanni NO2 parsing, reindexing, and aggregation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.no2_pipeline import (
    MONTHLY_COLUMNS,
    aggregate_monthly,
    parse_giovanni_csv,
    reindex_daily_calendar,
    run_pipeline,
    validate_accounting,
)


def _write_fixture(path: Path, extra_header_lines: list[str] | None = None) -> Path:
    header = [
        'Title:,"Time Series, Area-Averaged of NO2 Tropospheric Column (30% Cloud Screened) daily 0.25 deg."',
        "User Start Date:,2022-02-26T00:00:00Z",
        "User End Date:,2022-04-04T23:59:59Z",
        'User Bounding Box:,"30.273,50.2,30.773,50.7"',
        'Data Bounding Box:,"30.375,50.375,30.625,50.625"',
        'URL to Reproduce Results:,"https://giovanni.gsfc.nasa.gov/giovanni/#data=OMNO2d_004_ColumnAmountNO2TropCloudScreened"',
        "Fill Value (mean_OMNO2d_004_ColumnAmountNO2TropCloudScreened):, -1.267651e+30",
    ]
    if extra_header_lines:
        header.extend(extra_header_lines)
    header.append("")
    header.append("time, mean_OMNO2d_004_ColumnAmountNO2TropCloudScreened")

    rows = [
        # Feb 2022: 3 calendar days (2022-02-26..28), 2 valid (incl. negative noise), 1 fill
        "2022-02-26,2.000000e+15",
        "2022-02-27,-4.000000e+14",
        "2022-02-28,-1.267651e+30",
        # Mar 2022: all fill values -> 0 valid days, mean must stay NaN (not 0.0!)
        "2022-03-01,-1.267651e+30",
        "2022-03-15,-1.267651e+30",
        # (29 days absent inside Mar 2022!)
        # Apr 2022: 2022-04-01 absent; 2022-04-02..04 valid
        "2022-04-02,1.000000e+15",
        "2022-04-03,2.000000e+15",
        "2022-04-04,3.000000e+15",
    ]
    path.write_text("\n".join(header + rows) + "\n", encoding="utf-8")
    return path


class TestGiovanniNo2Pipeline(unittest.TestCase):
    def test_dynamic_header_discovery_and_negative_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _write_fixture(
                Path(tmpdir) / "sample_extra_meta.csv",
                extra_header_lines=[
                    "# Extra comment line 1",
                    "Instrument:,OMI/Aura",
                    "Notes:,Variable-length preamble test",
                ],
            )
            daily_raw, meta = parse_giovanni_csv(csv_path)
            self.assertEqual(meta["header_line_number_1based"], 12)
            self.assertEqual(meta["dataset"], "OMNO2d v004")
            self.assertEqual(meta["declared_fill_value"], -1.267651e30)
            self.assertEqual(meta["raw_dated_rows"], 8)

            # Negative observation (-4e14) must be preserved, fill value (-1.267651e+30) masked to NaN
            feb27 = daily_raw.loc[daily_raw["date"] == pd.Timestamp("2022-02-27"), "value"].iloc[0]
            feb28 = daily_raw.loc[daily_raw["date"] == pd.Timestamp("2022-02-28"), "value"].iloc[0]
            self.assertAlmostEqual(feb27, -4.0e14, places=1)
            self.assertTrue(pd.isna(feb28))

    def test_absent_dates_reindexing_and_monthly_aggregation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _write_fixture(Path(tmpdir) / "sample.csv")
            daily_raw, meta = parse_giovanni_csv(csv_path)
            daily_full, counts = reindex_daily_calendar(daily_raw, meta)

            # 2022-02-26..28 (3d) + Mar (31d) + Apr 1..4 (4d) = 38 calendar days
            self.assertEqual(counts["calendar_days"], 38)
            self.assertEqual(counts["raw_dated_rows"], 8)
            self.assertEqual(counts["fill_value_rows"], 3)
            self.assertEqual(counts["absent_dates_count"], 30)
            self.assertEqual(counts["valid_observations"], 5)
            self.assertEqual(counts["negative_valid_observations"], 1)
            self.assertIn("2022-04-01", counts["absent_dates"])

            # Absent date must be NaN, never zero
            apr1 = daily_full.loc[daily_full["date"] == pd.Timestamp("2022-04-01"), "value"].iloc[0]
            self.assertTrue(pd.isna(apr1))

            monthly_df, monthly_qc = aggregate_monthly(daily_full, sparse_min_valid_days=3)
            self.assertEqual(list(monthly_df.columns), MONTHLY_COLUMNS)
            checks = validate_accounting(counts, monthly_df)
            self.assertTrue(all(checks.values()))

            feb = monthly_df[monthly_df["month"] == "2022-02"].iloc[0]
            mar = monthly_df[monthly_df["month"] == "2022-03"].iloc[0]
            apr = monthly_df[monthly_df["month"] == "2022-04"].iloc[0]

            # Feb mean of [2e15, -4e14] = 0.8e15 over 2 valid days (3 calendar days in window)
            self.assertAlmostEqual(feb["no2_mean_molec_cm2"], 8.0e14, places=1)
            self.assertEqual(feb["valid_days"], 2)
            self.assertEqual(feb["calendar_days"], 3)
            self.assertAlmostEqual(feb["coverage_fraction"], round(2 / 3, 4))

            # Mar has 0 valid days -> mean must stay NaN (not 0.0!) and appear in sparse/zero lists
            self.assertTrue(pd.isna(mar["no2_mean_molec_cm2"]))
            self.assertEqual(mar["valid_days"], 0)
            self.assertIn("2022-03", monthly_qc["months_with_zero_valid_obs"])

            # Apr has 3 valid days -> meets threshold 3, mean = 2e15
            self.assertAlmostEqual(apr["no2_mean_molec_cm2"], 2.0e15, places=1)
            self.assertEqual(apr["valid_days"], 3)
            self.assertEqual(monthly_qc["sparse_months_count"], 2)  # 2022-02 (2d) and 2022-03 (0d)

    def test_end_to_end_run_pipeline_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = _write_fixture(tmp / "input.csv")
            out_csv = tmp / "reports" / "no2_monthly.csv"
            out_png = tmp / "reports" / "no2_monthly.png"
            out_json = tmp / "reports" / "data_quality.json"

            report = run_pipeline(
                input_csv=csv_path,
                output_csv=out_csv,
                output_chart=out_png,
                output_quality=out_json,
                sparse_min_valid_days=3,
            )

            self.assertTrue(out_csv.exists())
            self.assertTrue(out_png.exists() and out_png.stat().st_size > 10_000)
            self.assertTrue(out_json.exists())

            loaded_csv = pd.read_csv(out_csv)
            self.assertEqual(list(loaded_csv.columns), MONTHLY_COLUMNS)
            loaded_json = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded_json["daily_counts"]["valid_observations"], 5)
            self.assertTrue(all(report["validation_checks"].values()))


if __name__ == "__main__":
    unittest.main()
