from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from src.fire_analysis import (
    _safe_pct_change,
    assess_pre2022_comparability,
    compute_monthly_fire_table,
    compute_regional_comparisons,
    compute_satellite_month_coverage,
    main as fire_main,
    run_fire_analysis,
)
from src.fire_pipeline import (
    REQUIRED_FIRMS_COLUMNS,
    RegionSpec,
    discover_fire_inputs,
    load_and_validate_firms_archives,
    summarize_repeated_detections,
)


def _assert_no_nonfinite_json_values(obj: object, path: str = "root") -> None:
    """Recursively ensure every float in parsed JSON is finite (strict RFC 8259)."""
    if isinstance(obj, float):
        assert math.isfinite(obj), f"Non-finite float {obj!r} at {path}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_nonfinite_json_values(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            _assert_no_nonfinite_json_values(v, f"{path}[{idx}]")


def _strict_json_loads(text: str) -> object:
    def _reject_constant(token: str) -> None:
        raise AssertionError(f"Non-standard JSON constant {token!r} is forbidden")

    parsed = json.loads(text, parse_constant=_reject_constant)
    _assert_no_nonfinite_json_values(parsed)
    return parsed


def _make_firms_row(
    *,
    latitude: float = 48.90,
    longitude: float = 38.10,
    brightness: object = 335.4,
    scan: float = 0.4,
    track: float = 0.4,
    acq_date: str = "2022-05-10",
    acq_time: str = "1015",
    satellite: str = "SNPP",
    instrument: str = "SNPP",
    confidence: str = "n",
    version: str = "2",
    bright_t31: float = 290.1,
    frp: object = 12.5,
    daynight: str = "D",
    fire_type: object = 0,
) -> dict[str, object]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "brightness": brightness,
        "scan": scan,
        "track": track,
        "acq_date": acq_date,
        "acq_time": acq_time,
        "satellite": satellite,
        "instrument": instrument,
        "confidence": confidence,
        "version": version,
        "bright_t31": bright_t31,
        "frp": frp,
        "daynight": daynight,
        "type": fire_type,
    }


def _write_firms_zip(zip_path: Path, csv_name: str, rows: list[dict[str, object]]) -> None:
    df = pd.DataFrame(rows, columns=REQUIRED_FIRMS_COLUMNS)
    with ZipFile(zip_path, "w") as zf:
        zf.writestr(csv_name, df.to_csv(index=False))
        zf.writestr("Readme.txt", "Synthetic FIRMS SV-C2 fixture")


def _build_synthetic_multiyear_zips(raw_dir: Path) -> list[Path]:
    """Create minimal 2019-2022 March-August synthetic FIRMS .zip fixtures across regions."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    configs = {
        # East Frontline (48.9, 38.1), Central Interior (48.8, 31.5), North/Kyiv (51.0, 30.5),
        # Kyiv NO2 box (50.45, 30.52), West (49.5, 24.5), South (46.5, 33.0)
        2019: {3: 4, 4: 4, 5: 3, 6: 3, 7: 5, 8: 5},
        2020: {3: 5, 4: 6, 5: 2, 6: 2, 7: 4, 8: 4},
        2021: {3: 3, 4: 3, 5: 2, 6: 2, 7: 3, 8: 3},
        2022: {3: 6, 4: 3, 5: 4, 6: 4, 7: 6, 8: 6},
    }
    region_coords = [
        ("east", 48.90, 38.10),
        ("south", 46.50, 33.00),
        ("north", 51.00, 31.20),
        ("kyiv_box", 50.45, 30.52),
        ("central", 48.80, 31.50),
        ("west", 49.50, 24.50),
    ]
    paths: list[Path] = []
    for yr, month_counts in configs.items():
        rows: list[dict[str, object]] = []
        for m, base_n in month_counts.items():
            # Give day 1 across months, but intentionally leave gaps in 2022 Aug to test rate adjustment
            for r_idx, (r_name, lat, lon) in enumerate(region_coords):
                # Make East surge in 2022 while Central falls; spring vs summer differences pre-2022
                n_det = base_n
                if r_name == "east" and m >= 6:
                    n_det = base_n + (6 if yr == 2022 else 2)
                elif r_name == "central" and yr == 2022:
                    n_det = 1
                elif r_name in {"north", "west"} and m in {3, 4}:
                    n_det = base_n + 2
                for k in range(n_det):
                    day = 1 + (k % 15)
                    # Simulate a deliberate S-NPP gap in 2022 Aug (only days 1..10 present)
                    if yr == 2022 and m == 8 and day > 10:
                        day = 1 + (k % 10)
                    conf = "l" if k % 5 == 0 else ("h" if k % 4 == 0 else "n")
                    rows.append(
                        _make_firms_row(
                            latitude=lat + 0.001 * (k % 3),
                            longitude=lon + 0.001 * (r_idx % 2),
                            acq_date=f"{yr}-{m:02d}-{day:02d}",
                            acq_time=f"{(10 + k) % 24:02d}15",
                            confidence=conf,
                            daynight="D" if k % 2 == 0 else "N",
                            frp=5.0 + k,
                            fire_type=0,
                        )
                    )
            # Add static type=2 plant in East that drops sharply in 2022
            n_ind = 1 if yr == 2022 else 4
            for k in range(n_ind):
                rows.append(
                    _make_firms_row(
                        latitude=47.10,
                        longitude=37.60,
                        acq_date=f"{yr}-{m:02d}-02",
                        acq_time=f"{k:02d}30",
                        confidence="n",
                        daynight="N",
                        frp=2.5,
                        fire_type=2,
                    )
                )
        zp = raw_dir / f"DL_FIRE_SV-C2_{yr}.zip"
        _write_firms_zip(zp, f"fire_archive_SV-C2_{yr}.csv", rows)
        paths.append(zp)
    return paths


class TestFirePipelineAndAnalysis(unittest.TestCase):
    def test_ingestion_zip_and_csv_validation_quarantine_and_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_dir = root / "zips"
            csv_dir = root / "csvs"
            zip_dir.mkdir()
            csv_dir.mkdir()

            valid_row = _make_firms_row(
                latitude=48.901, longitude=38.101, acq_date="2022-06-15", acq_time="0115", frp=10.0, fire_type=0
            )
            exact_dup = _make_firms_row(
                latitude=48.901, longitude=38.101, acq_date="2022-06-15", acq_time="0115", frp=12.0, fire_type=0
            )
            same_cell_later = _make_firms_row(
                latitude=48.902, longitude=38.102, acq_date="2022-06-15", acq_time="1315", frp=0.0, daynight="N", fire_type=0
            )
            bad_lat = _make_firms_row(latitude=120.0, longitude=38.0, acq_date="2022-06-15", acq_time="1000")
            bad_lon = _make_firms_row(latitude=49.0, longitude=-190.0, acq_date="2022-06-15", acq_time="1000")
            bad_date = _make_firms_row(acq_date="2022-99-99", acq_time="1000")
            bad_time = _make_firms_row(acq_date="2022-06-15", acq_time="2460")
            bad_type = _make_firms_row(acq_date="2022-06-15", acq_time="1000", fire_type=9)
            bad_conf = _make_firms_row(acq_date="2022-06-15", acq_time="1100", confidence="x")
            bad_num = _make_firms_row(acq_date="2022-06-15", acq_time="1200", frp="not_a_num")
            out_of_win = _make_firms_row(acq_date="2022-09-01", acq_time="1000")

            zp = zip_dir / "sample_2022.zip"
            rows = [
                valid_row,
                exact_dup,
                same_cell_later,
                bad_lat,
                bad_lon,
                bad_date,
                bad_time,
                bad_type,
                bad_conf,
                bad_num,
                out_of_win,
            ]
            _write_firms_zip(zp, "sample_2022.csv", rows)
            orig_bytes = zp.read_bytes()

            cp = csv_dir / "sample_2021.csv"
            pd.DataFrame(
                [_make_firms_row(acq_date="2021-05-05", acq_time="0900", confidence="h", fire_type=2)],
                columns=REQUIRED_FIRMS_COLUMNS,
            ).to_csv(cp, index=False)

            discovered_zips = discover_fire_inputs(zip_dir)
            discovered_csvs = discover_fire_inputs(csv_dir)
            self.assertEqual(discovered_zips, [zp])
            self.assertEqual(discovered_csvs, [cp])

            clean_df, qreport = load_and_validate_firms_archives(
                [zp, cp], years_expected=(2021, 2022), months_expected=(5, 6)
            )
            # Ensure original zip untouched
            self.assertEqual(zp.read_bytes(), orig_bytes)

            acc = qreport["accounting"]
            self.assertEqual(acc["raw_rows_total"], 12)
            self.assertEqual(acc["invalid_coordinate_rows_dropped"], 2)
            self.assertEqual(acc["invalid_date_rows_dropped"], 1)
            self.assertEqual(acc["invalid_time_rows_dropped"], 1)
            self.assertEqual(acc["invalid_type_rows_dropped"], 1)
            self.assertEqual(acc["invalid_confidence_rows"], 1)
            self.assertEqual(acc["invalid_numeric_rows"], 1)
            # valid_row + exact_dup + bad_conf(frp=12.5) + same_cell_later(frp=0.0) + out_of_win + bad_* have 1 nonpositive frp
            self.assertEqual(acc["nonpositive_frp_rows_retained"], 1)
            self.assertEqual(acc["exact_duplicates_removed"], 1)
            self.assertEqual(acc["out_of_study_window_rows_dropped"], 1)
            # Surviving: valid_row, same_cell_later, bad_conf, bad_num, 2021 row => 5 clean rows
            self.assertEqual(acc["clean_rows_retained"], 5)
            self.assertEqual(len(clean_df), 5)

            # Check repeated detection metrics around 0.01 deg cell (48.90, 38.10)
            rep = summarize_repeated_detections(clean_df)
            # In clean_df, valid_row (48.901, 38.101 -> 48.90, 38.10), same_cell_later (48.902, 38.102 -> 48.90, 38.10),
            # bad_conf & bad_num (48.90, 38.10 -> 48.90, 38.10) all fall inside (48.90, 38.10)
            t0 = rep["type0_vegetation_overall"]
            self.assertEqual(t0["detections"], 4)
            self.assertEqual(t0["unique_0_01deg_cells"], 1)
            self.assertEqual(t0["multi_detection_cells"], 1)
            self.assertAlmostEqual(t0["multi_detection_cell_share"], 1.0)
            self.assertGreater(t0["mean_detections_per_cell_day"], 1.0)

    def test_missing_required_columns_and_empty_dir_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_dir = Path(tmp) / "empty"
            empty_dir.mkdir()
            with self.assertRaises(FileNotFoundError):
                discover_fire_inputs(empty_dir)

            bad_csv = empty_dir / "bad.csv"
            pd.DataFrame([{"latitude": 50.0, "longitude": 30.0}]).to_csv(bad_csv, index=False)
            with self.assertRaises(ValueError):
                load_and_validate_firms_archives([bad_csv], years_expected=(2022,), months_expected=(3,))

    def test_filter_modes_outage_rate_safe_pct_and_comparability_guards(self) -> None:
        # Guardrail tests for _safe_pct_change
        diff0, pct0, st0 = _safe_pct_change(10.0, 0.0)
        self.assertEqual(diff0, 10.0)
        self.assertIsNone(pct0)
        self.assertEqual(st0, "withheld_nonpositive_baseline")

        diff_neg, pct_neg, st_neg = _safe_pct_change(5.0, -2.0)
        self.assertEqual(diff_neg, 7.0)
        self.assertIsNone(pct_neg)
        self.assertEqual(st_neg, "withheld_nonpositive_baseline")

        diff_na, pct_na, st_na = _safe_pct_change(float("nan"), 10.0)
        self.assertIsNone(diff_na)
        self.assertIsNone(pct_na)
        self.assertEqual(st_na, "withheld_missing_data")

        # Synthetic filtering, gap-day coverage, and comparability checks
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp)
            paths = _build_synthetic_multiyear_zips(raw_dir)
            clean_df, _ = load_and_validate_firms_archives(paths)
            sat_cov = compute_satellite_month_coverage(clean_df)
            aug22 = sat_cov[sat_cov["month"] == "2022-08"].iloc[0]
            self.assertEqual(int(aug22["satellite_observed_days"]), 10)
            self.assertEqual(int(aug22["calendar_days"]), 31)
            self.assertAlmostEqual(float(aug22["satellite_coverage_fraction"]), round(10 / 31, 4))

            monthly_df = compute_monthly_fire_table(clean_df, sat_cov)
            _, reg_comp = compute_regional_comparisons(monthly_df)
            nat_all = reg_comp["ukraine_national"]["all_types_all_conf"]["mar_aug"]["target_2022"]["detections"]
            nat_t0 = reg_comp["ukraine_national"]["type0_vegetation_all_conf"]["mar_aug"]["target_2022"]["detections"]
            nat_nh = reg_comp["ukraine_national"]["type0_vegetation_nominal_high"]["mar_aug"]["target_2022"]["detections"]
            nat_t2 = reg_comp["ukraine_national"]["type2_static_industrial"]["mar_aug"]["target_2022"]["detections"]
            self.assertEqual(int(nat_all), int(nat_t0 + nat_t2))
            self.assertLess(nat_nh, nat_t0)  # low-confidence rows filtered out

            # Kyiv NO2 box has zero type=2 industrial detections -> must report withheld_nonpositive_baseline
            kyiv_t2 = reg_comp["kyiv_no2_box"]["type2_static_industrial"]["mar_aug"]["vs_baseline_2019_2021"]
            self.assertIsNone(kyiv_t2["detections_pct_change"])
            self.assertEqual(kyiv_t2["detections_pct_status"], "withheld_nonpositive_baseline")

            # Comparability zero-variance guard on an empty custom region
            flat_regions = (
                RegionSpec("study_flat", "Flat Study", "proposed_study_region", 55.0, 56.0, 10.0, 11.0, "empty"),
                RegionSpec("ref_active", "Active Ref", "proposed_reference_region", 48.0, 50.0, 30.0, 39.0, "populated"),
            )
            flat_monthly = compute_monthly_fire_table(clean_df, sat_cov, regions=flat_regions)
            _, flat_comp = assess_pre2022_comparability(flat_monthly, regions=flat_regions)
            self.assertEqual(len(flat_comp), 1)
            self.assertIsNone(flat_comp[0]["pre2022_pearson_r"])
            self.assertEqual(flat_comp[0]["comparability_tier"], "not_assessed_zero_variance")

    def test_end_to_end_pipeline_and_cli_strict_json_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            reports_dir = root / "reports"
            _build_synthetic_multiyear_zips(raw_dir)

            rc = fire_main(["--raw-dir", str(raw_dir), "--reports-dir", str(reports_dir)])
            self.assertEqual(rc, 0)

            expected_files = [
                reports_dir / "fire_monthly.csv",
                reports_dir / "fire_regional_summary.csv",
                reports_dir / "fire_comparability_matrix.csv",
                reports_dir / "fire_quality.json",
                reports_dir / "fire_viirs_results.json",
                reports_dir / "fire_location_map.png",
                reports_dir / "fire_monthly_comparison.png",
            ]
            for fp in expected_files:
                self.assertTrue(fp.exists(), f"Missing output artifact: {fp}")

            # Verify PNGs are genuine rendered figures
            self.assertGreater((reports_dir / "fire_location_map.png").stat().st_size, 10_000)
            self.assertGreater((reports_dir / "fire_monthly_comparison.png").stat().st_size, 10_000)

            # Verify strict RFC 8259 JSON without NaN/Infinity
            _strict_json_loads((reports_dir / "fire_quality.json").read_text(encoding="utf-8"))
            res = _strict_json_loads((reports_dir / "fire_viirs_results.json").read_text(encoding="utf-8"))
            assert isinstance(res, dict)

            self.assertEqual(res["schema_version"], "1.0.0")
            self.assertEqual(res["status"]["proposed_region_agreement"], "proposed_pending_team_agreement")
            self.assertEqual(res["status"]["causal_attribution"], "not_established")
            self.assertEqual(res["statistics"]["before_after_seasonal_inference"]["status"], "not_assessed")
            self.assertIsNone(res["statistics"]["before_after_seasonal_inference"]["p_value"])
            self.assertFalse(res["statistics"]["before_after_seasonal_inference"]["statistical_significance_claimed"])

            # Verify direct run_fire_analysis return matches serialized keys
            direct = run_fire_analysis(raw_dir=raw_dir, reports_dir=reports_dir)
            self.assertEqual(set(direct.keys()), set(res.keys()))


if __name__ == "__main__":
    unittest.main()
