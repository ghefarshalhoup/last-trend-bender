from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.air_analysis import (
    _evaluate_trend_window,
    _safe_pct_change,
    assess_statistics,
    compute_annual_seasonal_series,
    compute_baseline_comparison,
    compute_coverage_exclusion_sensitivities,
    compute_matched_month_comparisons,
)
from src.no2_pipeline import (
    aggregate_monthly,
    main as no2_main,
    parse_giovanni_csv,
    reindex_daily_calendar,
)


def _assert_no_nonfinite_json_values(obj: object, path: str = "root") -> None:
    """Recursively ensure every float in parsed JSON is finite (no NaN or Infinity)."""
    if isinstance(obj, float):
        assert math.isfinite(obj), f"Non-finite float {obj!r} at {path}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_nonfinite_json_values(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            _assert_no_nonfinite_json_values(v, f"{path}[{idx}]")


def _build_synthetic_daily_full(
    years: list[int],
    months: list[int],
    per_year_month_spec: dict[tuple[int, int], tuple[int, float]],
) -> pd.DataFrame:
    """
    Build a full calendar daily DataFrame matching aggregate_monthly's expected schema.
    per_year_month_spec[(year, month)] = (valid_days, constant_valid_value)
    Remaining days in each month are marked 'fill_missing' with NaN value.
    """
    rows: list[dict[str, object]] = []
    for yr in years:
        for mo in months:
            start = pd.Timestamp(year=yr, month=mo, day=1)
            end = start + pd.offsets.MonthEnd(1)
            dates = pd.date_range(start, end, freq="D")
            valid_n, val = per_year_month_spec.get((yr, mo), (0, np.nan))
            for idx, dt in enumerate(dates):
                if idx < valid_n:
                    rows.append({"date": dt, "value": float(val), "status": "valid"})
                else:
                    rows.append({"date": dt, "value": np.nan, "status": "fill_missing"})
    return pd.DataFrame(rows)


def _write_synthetic_giovanni_csv(path: Path) -> None:
    """
    Write a full March 2015 - August 2022 synthetic Giovanni CSV with:
    - Metadata preamble including FillValue = -1.267651e+30
    - Seasonal cycle + slight pre-war decline + 2022 step lower
    - Some missing fill values, a few absent dates, a negative valid value, and sparse Apr 2022 (8/30 valid days)
    """
    rng = np.random.default_rng(20220224)
    header = [
        '"Title: Area-Averaged Time Series (OMNO2d v004) Synthetic Test"',
        '"User Start Date: 2015-03-01"',
        '"User End Date: 2022-08-31"',
        '"User Bounding Box: 30.273,50.2,30.773,50.7"',
        '"Data Bounding Box: 30.375,50.375,30.625,50.625"',
        '"Dataset: OMNO2d v004"',
        '"Variable: NO2 Tropospheric Column (30% Cloud Screened)"',
        '"Units: molecules/cm^2"',
        '"FillValue: -1.267651e+30"',
        '"URL: https://example.org/giovanni-synthetic"',
        "time,MEAN_OMNO2d_004_ColumnAmountNO2TropCloudScreened",
    ]

    all_days = pd.date_range("2015-03-01", "2022-08-31", freq="D")
    lines = list(header)
    eps = 0.0
    for idx, dt in enumerate(all_days):
        # Leave 2 days absent cleanly to test absent-date handling
        if dt.strftime("%Y-%m-%d") in {"2016-05-10", "2021-07-15"}:
            continue

        yr = dt.year
        mo = dt.month
        # Force April 2022 to have exactly 8 valid days (<50%)
        if yr == 2022 and mo == 4:
            if dt.day > 8:
                lines.append(f"{dt.strftime('%Y-%m-%d')},-1.267651e+30")
                continue

        # Put one negative valid retrieval and some periodic cloud-screened fills
        if dt.strftime("%Y-%m-%d") == "2018-06-03":
            lines.append(f"{dt.strftime('%Y-%m-%d')},-1.500000e+14")
            continue

        if (idx % 5) == 4:
            lines.append(f"{dt.strftime('%Y-%m-%d')},-1.267651e+30")
            continue

        # Smooth seasonal wave + slight downward trend + 2022 post-Feb shift + AR(1) noise
        t_years = idx / 365.25
        seasonal = 2.4e15 + 0.5e15 * math.cos(2.0 * math.pi * (mo - 1) / 12.0)
        trend = -3.0e13 * t_years
        post_feb22 = -6.0e14 if dt >= pd.Timestamp("2022-03-01") else 0.0
        eps = 0.35 * eps + float(rng.normal(0.0, 2.0e14))
        val = seasonal + trend + post_feb22 + eps
        lines.append(f"{dt.strftime('%Y-%m-%d')},{val:.6e}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestAirAnalysis(unittest.TestCase):
    def test_hand_verifiable_baselines_weighting_and_matched_months(self) -> None:
        years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
        months = [3, 4, 5, 6, 7, 8]
        spec: dict[tuple[int, int], tuple[int, float]] = {}

        # Make valid days intentionally uneven in Mar vs Apr for 2015-2019 so
        # valid-day weighting != equal-month weighting:
        # Mar has 16 valid days at 1.0e15; Apr has 24 valid days at 4.0e15;
        # May..Aug each have 20 valid days at 2.0e15.
        for yr in [2015, 2016, 2017, 2018, 2019]:
            spec[(yr, 3)] = (16, 1.0e15)
            spec[(yr, 4)] = (24, 4.0e15)
            for mo in (5, 6, 7, 8):
                spec[(yr, mo)] = (20, 2.0e15)

        # 2020 and 2021 lower baseline (still 20 valid days/mo = 2.0e15 except Mar=1.0e15, Apr=2.0e15)
        for yr in [2020, 2021]:
            spec[(yr, 3)] = (20, 1.0e15)
            for mo in (4, 5, 6, 7, 8):
                spec[(yr, mo)] = (20, 2.0e15)

        # 2022 target: uniform 1.5e15 across all 6 months, except Apr sparse (8 valid days)
        for mo in months:
            spec[(2022, mo)] = (8 if mo == 4 else 20, 1.5e15)

        daily_full = _build_synthetic_daily_full(years, months, spec)
        monthly_df, _ = aggregate_monthly(daily_full, low_coverage_fraction=0.50)
        annual_df = compute_annual_seasonal_series(daily_full, monthly_df, months=months)

        # Hand calculation for any year in 2015..2019:
        # valid_day_mean = (16*1.0 + 24*4.0 + 80*2.0) / 120 * 1e15 = (16 + 96 + 160)/120 * 1e15 = 272/120 * 1e15
        # equal_month_mean = (1.0 + 4.0 + 4*2.0) / 6 * 1e15 = 13/6 * 1e15
        expected_prim_vd = (272.0 / 120.0) * 1.0e15
        expected_prim_em = (13.0 / 6.0) * 1.0e15
        self.assertNotAlmostEqual(expected_prim_vd, expected_prim_em, delta=1e12)

        comp_prim_vd = compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="prim_vd",
            label="primary vd",
            baseline_years=[2015, 2016, 2017, 2018, 2019],
            weighting="valid_day_annual_equal_weight",
        )
        comp_prim_em = compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="prim_em",
            label="primary em",
            baseline_years=[2015, 2016, 2017, 2018, 2019],
            weighting="equal_month_annual_equal_weight",
        )
        self.assertAlmostEqual(comp_prim_vd["baseline_mean_molec_cm2"], expected_prim_vd, delta=1.0)
        self.assertAlmostEqual(comp_prim_em["baseline_mean_molec_cm2"], expected_prim_em, delta=1.0)
        self.assertAlmostEqual(comp_prim_vd["target_mean_molec_cm2"], 1.5e15, delta=1.0)
        self.assertAlmostEqual(
            comp_prim_vd["pct_change"],
            ((1.5e15 - expected_prim_vd) / expected_prim_vd) * 100.0,
            places=3,
        )
        self.assertNotEqual(comp_prim_vd["pct_change"], comp_prim_em["pct_change"])

        # Sensitivity baseline 2019-2021 (valid-day equal annual average across 2019, 2020, 2021):
        # 2019 vd mean = expected_prim_vd; 2020 & 2021 vd mean = (1 + 5*2)/6 * 1e15 = 11/6 * 1e15
        expected_sens_vd = (expected_prim_vd + 2.0 * (11.0 / 6.0) * 1.0e15) / 3.0
        comp_sens_vd = compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="sens_vd",
            label="sens vd",
            baseline_years=[2019, 2020, 2021],
            weighting="valid_day_annual_equal_weight",
        )
        self.assertAlmostEqual(comp_sens_vd["baseline_mean_molec_cm2"], expected_sens_vd, delta=1.0)

        # Matched-month comparisons check
        matched = compute_matched_month_comparisons(monthly_df)
        by_month = {row["calendar_month"]: row for row in matched}
        self.assertEqual(by_month[4]["month_name"], "Apr")
        self.assertTrue(by_month[4]["target_2022"]["flagged_below_50_pct"])
        self.assertFalse(by_month[3]["target_2022"]["flagged_below_50_pct"])
        self.assertAlmostEqual(by_month[4]["primary_2015_2019"]["mean_molec_cm2"], 4.0e15, delta=1.0)
        self.assertAlmostEqual(by_month[4]["vs_primary_2015_2019"]["pct_change"], -62.5, places=3)

    def test_coverage_flagging_and_identical_month_exclusions(self) -> None:
        years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
        months = [3, 4, 5, 6, 7, 8]
        spec: dict[tuple[int, int], tuple[int, float]] = {
            (yr, mo): (20, 2.0e15) for yr in years for mo in months
        }
        # Sparse April 2022 (8/30 = 26.67% < 50%) and sparse March 2017 (10/31 = 32.26% < 50%)
        spec[(2022, 4)] = (8, 3.0e15)
        spec[(2017, 3)] = (10, 1.0e15)
        for mo in months:
            if mo != 4:
                spec[(2022, mo)] = (20, 1.0e15)

        daily_full = _build_synthetic_daily_full(years, months, spec)
        monthly_df, _ = aggregate_monthly(daily_full, low_coverage_fraction=0.50)

        sens = compute_coverage_exclusion_sensitivities(daily_full, monthly_df, low_coverage_threshold=0.50)

        # Excluding target-flagged months drops only April [3,5,6,7,8]
        excl_target = sens["excluding_target_flagged_months"]["primary_2015_2019_valid_day"]
        self.assertEqual(excl_target["months_included"], [3, 5, 6, 7, 8])
        self.assertEqual(excl_target["flagged_months_in_target"], [])

        # Strict all-years unflagged for 2015-2019 drops both March (2017 <50%) and April (2022 <50%)
        strict_prim = sens["strict_all_years_unflagged"]["primary_2015_2019_valid_day"]
        self.assertEqual(strict_prim["months_included"], [5, 6, 7, 8])
        self.assertEqual(strict_prim["flagged_months_in_baseline"], [])
        self.assertAlmostEqual(strict_prim["pct_change"], -50.0, places=3)

        # Edge case: if all months in 2022 fail <50% coverage, pct_change must be None (no crash / divide by zero)
        all_sparse_spec = dict(spec)
        for mo in months:
            all_sparse_spec[(2022, mo)] = (5, 1.0e15)
        daily_all_sparse = _build_synthetic_daily_full(years, months, all_sparse_spec)
        monthly_all_sparse, _ = aggregate_monthly(daily_all_sparse, low_coverage_fraction=0.50)
        empty_sens = compute_coverage_exclusion_sensitivities(
            daily_all_sparse, monthly_all_sparse, low_coverage_threshold=0.50
        )
        strict_empty = empty_sens["strict_all_years_unflagged"]["primary_2015_2019_valid_day"]
        self.assertEqual(strict_empty["months_included"], [])
        self.assertIsNone(strict_empty["pct_change"])
        self.assertEqual(strict_empty["pct_change_status"], "withheld_no_remaining_months")

    def test_invalid_percentage_denominators(self) -> None:
        # Zero baseline -> withheld
        diff, pct, status = _safe_pct_change(1.0e15, 0.0)
        self.assertEqual(diff, 1.0e15)
        self.assertIsNone(pct)
        self.assertEqual(status, "withheld_nonpositive_baseline")

        # Negative baseline -> withheld
        diff_neg, pct_neg, status_neg = _safe_pct_change(1.0e15, -5.0e14)
        self.assertEqual(diff_neg, 1.5e15)
        self.assertIsNone(pct_neg)
        self.assertEqual(status_neg, "withheld_nonpositive_baseline")

        # Missing baseline or target -> withheld
        self.assertEqual(_safe_pct_change(1.0e15, None), (None, None, "withheld_missing_data"))
        self.assertEqual(_safe_pct_change(None, 2.0e15), (None, None, "withheld_missing_data"))

        # Valid negative target over positive baseline IS allowed (percent change well-defined)
        diff_ok, pct_ok, status_ok = _safe_pct_change(-1.0e15, 2.0e15)
        self.assertEqual(status_ok, "computed")
        self.assertAlmostEqual(diff_ok, -3.0e15, places=2)
        self.assertAlmostEqual(pct_ok, -150.0, places=4)

        # End-to-end check inside compute_baseline_comparison with negative/zero baseline
        years = [2015, 2016, 2022]
        spec = {(2015, 3): (20, -1.0e14), (2016, 3): (20, 1.0e14), (2022, 3): (20, 5.0e14)}
        daily_zero = _build_synthetic_daily_full(years, [3], spec)
        monthly_zero, _ = aggregate_monthly(daily_zero)
        annual_zero = compute_annual_seasonal_series(daily_zero, monthly_zero, months=[3])
        comp = compute_baseline_comparison(
            annual_df=annual_zero,
            comparison_id="zero_denom",
            label="zero baseline",
            baseline_years=[2015, 2016],
            target_year=2022,
            months_included=[3],
        )
        self.assertAlmostEqual(comp["baseline_mean_molec_cm2"], 0.0, places=5)
        self.assertIsNone(comp["pct_change"])
        self.assertEqual(comp["pct_change_status"], "withheld_nonpositive_baseline")

    def test_statistical_guards_and_trend_estimation(self) -> None:
        # 1. Short window (< 24 months) must return not_assessed
        short_df = pd.DataFrame(
            {
                "month": pd.date_range("2020-01-01", periods=18, freq="MS").strftime("%Y-%m"),
                "mnum": [(i % 12) + 1 for i in range(18)],
                "no2_mean_molec_cm2": [2.0e15] * 18,
            }
        )
        res_short = _evaluate_trend_window(short_df, "short", "short")
        self.assertEqual(res_short["status"], "not_assessed")
        self.assertIsNone(res_short["p_value"])

        # 2. Constant / zero-variance series (>= 24 months) -> HAC variance == 0 -> not_assessed
        const_dates = pd.date_range("2018-01-01", periods=36, freq="MS")
        const_df = pd.DataFrame(
            {
                "month": const_dates.strftime("%Y-%m"),
                "mnum": const_dates.month,
                "no2_mean_molec_cm2": [2.0e15] * 36,
            }
        )
        res_const = _evaluate_trend_window(const_df, "const", "const")
        self.assertEqual(res_const["status"], "not_assessed")
        self.assertIsNone(res_const["slope_molec_cm2_per_year"])

        # 3. Realistic 2015-03..2022-08 synthetic Giovanni CSV recovers trend + blocks n=1 before/after inference
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "synthetic_giovanni.csv"
            _write_synthetic_giovanni_csv(csv_path)
            daily_raw, meta = parse_giovanni_csv(csv_path)
            daily_full, _ = reindex_daily_calendar(daily_raw, meta)
            monthly_df, _ = aggregate_monthly(daily_full)
            stats = assess_statistics(daily_full, monthly_df)

        ba = stats["before_after_seasonal_inference"]
        self.assertEqual(ba["status"], "not_assessed")
        self.assertIsNone(ba["p_value"])
        self.assertIsNone(ba["ci_95_lower_molec_cm2"])
        self.assertIsNone(ba["ci_95_upper_molec_cm2"])
        self.assertFalse(ba["statistical_significance_claimed"])

        pre_trend = stats["multi_year_seasonality_aware_trend"]["pre_invasion"]
        full_trend = stats["multi_year_seasonality_aware_trend"]["full_record"]
        self.assertEqual(pre_trend["status"], "assessed")
        self.assertEqual(full_trend["status"], "assessed")
        self.assertLess(pre_trend["slope_molec_cm2_per_year"], 0.0)
        self.assertGreaterEqual(pre_trend["p_value"], 0.0)
        self.assertLessEqual(pre_trend["p_value"], 0.05)
        self.assertGreaterEqual(full_trend["p_value"], 0.0)
        self.assertLessEqual(full_trend["p_value"], 1.0)
        self.assertLess(pre_trend["ci_95_lower_molec_cm2_per_year"], pre_trend["ci_95_upper_molec_cm2_per_year"])
        self.assertGreater(stats["daily_autocorrelation_diagnostics"]["lags"]["lag_1d"]["autocorr_r"], 0.0)

    def test_end_to_end_exports_cli_and_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw_csv = tmp / "synthetic_giovanni.csv"
            reports_dir = tmp / "reports"
            _write_synthetic_giovanni_csv(raw_csv)

            # Test unified CLI entrypoint via no2_pipeline.main (which delegates to src.air_analysis.main)
            rc = no2_main(["--input", str(raw_csv), "--reports-dir", str(reports_dir)])
            self.assertEqual(rc, 0)

            expected_files = [
                reports_dir / "no2_monthly.csv",
                reports_dir / "no2_monthly.png",
                reports_dir / "data_quality.json",
                reports_dir / "no2_seasonal_comparison.png",
                reports_dir / "no2_matched_months.png",
                reports_dir / "no2_seasonal_comparisons.csv",
                reports_dir / "no2_matched_months.csv",
                reports_dir / "air_no2_results.json",
            ]
            for path in expected_files:
                self.assertTrue(path.exists(), f"Missing output artifact: {path}")

            for png in (
                reports_dir / "no2_monthly.png",
                reports_dir / "no2_seasonal_comparison.png",
                reports_dir / "no2_matched_months.png",
            ):
                self.assertGreater(png.stat().st_size, 10_000)

            # Strict JSON parse: parse_constant raises ValueError on NaN/Infinity/-Infinity
            def _reject_nonfinite(val: str) -> None:
                raise ValueError(f"Illegal non-finite JSON token: {val}")

            air_payload = json.loads(
                (reports_dir / "air_no2_results.json").read_text(encoding="utf-8"),
                parse_constant=_reject_nonfinite,
            )
            quality_payload = json.loads(
                (reports_dir / "data_quality.json").read_text(encoding="utf-8"),
                parse_constant=_reject_nonfinite,
            )
            _assert_no_nonfinite_json_values(air_payload)
            _assert_no_nonfinite_json_values(quality_payload)

            self.assertEqual(air_payload["status"]["overall"], "validated_descriptive_with_limitations")
            self.assertEqual(air_payload["status"]["paper_replication_classification"], "related_comparison")
            self.assertEqual(air_payload["statistics"]["before_after_seasonal_inference"]["status"], "not_assessed")
            self.assertEqual(air_payload["charts"]["matched_months"]["flagged_target_months"], ["Apr"])
            self.assertTrue(air_payload["quality_rules"]["negative_valid_values_preserved"])
            self.assertTrue(air_payload["quality_rules"]["missing_values_never_zero_filled"])


if __name__ == "__main__":
    unittest.main()
