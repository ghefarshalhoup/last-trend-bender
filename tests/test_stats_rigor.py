"""Unit tests for src/stats_rigor.py mathematical and physical rigor guarantees."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.stats_rigor import (
    bbox_area_km2,
    bh_q_values,
    by_q_values,
    compute_baseline_climatology_anomalies,
    compute_fao56_vpd_and_pet_series,
    compute_lagged_monthly_impulse_coupling,
    duality_locked_ci_from_slopes,
    fit_box_tiao_step_intervention,
    hamed_rao_modified_mk,
    hirsch_slack_seasonal_mk_and_slope,
    kendall_tau_b_bivariate,
    partial_trend_controlling_covariate,
    spherical_area_weighted_mean,
    structural_hinge_breakpoint_analysis,
    write_strict_json,
)


class StatsRigorTests(unittest.TestCase):
    def test_bbox_area_and_spherical_mean(self) -> None:
        # 0.5 deg x 0.5 deg Kyiv box centered at 50.45N should be ~1,972 km^2
        area = bbox_area_km2(30.273, 50.200, 30.773, 50.700)
        self.assertGreater(area, 1900.0)
        self.assertLess(area, 2050.0)
        wmean = spherical_area_weighted_mean([0.0, 60.0], [10.0, 20.0])
        # cos(0)=1, cos(60)=0.5 -> (10 + 10) / 1.5 = 13.3333...
        self.assertAlmostEqual(wmean, 40.0 / 3.0, places=6)

    def test_strict_json_rejects_nonfinite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            with self.assertRaises(ValueError):
                write_strict_json(path, {"bad": float("nan")})
            good_path = Path(tmp) / "good.json"
            write_strict_json(good_path, {"ok": 1.5, "missing": None})
            parsed = json.loads(good_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed, {"ok": 1.5, "missing": None})

    def test_test_ci_duality_holds_across_synthetic_series(self) -> None:
        rng = np.random.default_rng(42)
        yrs = [float(y) for y in range(2000, 2024)]
        for slope in (0.0, 0.08, -0.12):
            vals = [slope * (y - 2000.0) + float(rng.normal(0.0, 0.25)) for y in yrs]
            s, _, _, _, _, p_hr, vif, _, _ = hamed_rao_modified_mk(yrs, vals)
            slopes_yr = sorted(
                (vals[j] - vals[i]) / (yrs[j] - yrs[i])
                for i in range(len(yrs) - 1)
                for j in range(i + 1, len(yrs))
            )
            var0 = (len(yrs) * (len(yrs) - 1) * (2 * len(yrs) + 5)) / 18.0
            _, ci_lo, ci_hi, _, p_dual = duality_locked_ci_from_slopes(
                slopes_yr, s, var0 * vif, var0_baseline=var0
            )
            ci_excludes_zero = (ci_lo > 0.0) or (ci_hi < 0.0)
            self.assertEqual(p_dual < 0.05, ci_excludes_zero)
            self.assertTrue(math.isfinite(p_hr))

    def test_hamed_rao_controls_ar1_red_noise_false_positives(self) -> None:
        rng = np.random.default_rng(123)
        yrs = [float(i) for i in range(48)]
        false_pos_classic = 0
        false_pos_hr = 0
        n_trials = 60
        for _ in range(n_trials):
            eps = rng.normal(0.0, 1.0, size=48)
            x = [0.0] * 48
            for t in range(1, 48):
                x[t] = 0.72 * x[t - 1] + eps[t]
            _, _, _, p_cls, _, p_hr, _, _, _ = hamed_rao_modified_mk(yrs, x)
            if p_cls < 0.05:
                false_pos_classic += 1
            if p_hr < 0.05:
                false_pos_hr += 1
        self.assertLessEqual(false_pos_hr, false_pos_classic)

    def test_box_tiao_orthogonal_step_intervention(self) -> None:
        # Pure secular linear trend MUST yield ~0.0 step shift at t_b (0% trend conflation)
        yrs = [2015.0 + (i + 0.5) / 12.0 for i in range(96)]
        pure_trend = [10.0 - 0.5 * (t - 2015.0) for t in yrs]
        res_linear = fit_box_tiao_step_intervention(yrs, pure_trend, intervention_year=2022.0 + 2.0 / 12.0)
        self.assertEqual(res_linear["status"], "assessed")
        self.assertAlmostEqual(float(res_linear["delta_step"]), 0.0, places=6)

        # True -2.5 step jump superimposed on trend + wind speed covariate
        rng = np.random.default_rng(7)
        ws = [4.0 + float(rng.normal(0.0, 0.8)) for _ in yrs]
        y_step = [
            (10.0 - 0.3 * (t - 2015.0) - 0.6 * w + (-2.5 if t >= 2022.0 + 2.0 / 12.0 else 0.0))
            for t, w in zip(yrs, ws)
        ]
        res_cov = fit_box_tiao_step_intervention(
            yrs, y_step, intervention_year=2022.0 + 2.0 / 12.0, covariates={"ws10m": ws}
        )
        self.assertAlmostEqual(float(res_cov["delta_step"]), -2.5, places=4)
        self.assertAlmostEqual(float(res_cov["covariate_betas"]["ws10m"]), -0.6, places=4)

    def test_hirsch_slack_and_bh_by_fdr(self) -> None:
        years: list[int] = []
        months: list[int] = []
        vals: list[float] = []
        for y in range(2015, 2023):
            for m in range(1, 13):
                years.append(y)
                months.append(m)
                vals.append(math.sin(m) + 0.1 * (y - 2015))
        res = hirsch_slack_seasonal_mk_and_slope(years, months, vals, min_years_per_month=4)
        self.assertAlmostEqual(float(res["sen_slope_per_decade"]), 1.0, places=3)
        self.assertLess(float(res["p_value_seasonal"]), 0.05)

        pvals = [0.001, 0.02, 0.50, 0.90]
        q_bh = bh_q_values(pvals)
        q_by = by_q_values(pvals)
        self.assertEqual(len(q_bh), 4)
        self.assertTrue(all(a <= b for a, b in zip(q_bh, q_by)))
        self.assertLess(q_bh[0], 0.01)

    def test_fao56_vpd_pet_and_lagged_coupling(self) -> None:
        n = 48
        t2m = [20.0 + 8.0 * math.sin(2.0 * math.pi * i / 12.0) for i in range(n)]
        tmax = [t + 5.0 for t in t2m]
        tmin = [t - 5.0 for t in t2m]
        rh = [65.0] * n
        sw = [16.0 + 6.0 * math.sin(2.0 * math.pi * i / 12.0) for i in range(n)]
        ws = [3.2] * n
        mos = [(i % 12) + 1 for i in range(n)]
        out = compute_fao56_vpd_and_pet_series(t2m, tmax, tmin, rh, sw, ws, lat_deg=50.45, elevation_m=179.0, months=mos)
        self.assertEqual(len(out["vpd_kpa"]), n)
        self.assertTrue(all(v > 0.0 for v in out["vpd_kpa"]))
        self.assertTrue(all(p > 0.0 for p in out["pet_mm_day"]))

        # Lag-1 physical coupling X(t) -> Y(t+1)
        rng = np.random.default_rng(99)
        yrs_c = [2015 + i // 12 for i in range(72)]
        mos_c = [(i % 12) + 1 for i in range(72)]
        x_sig = rng.normal(0.0, 1.0, size=72)
        y_sig = np.zeros(72)
        for i in range(1, 72):
            y_sig[i] = 0.85 * x_sig[i - 1] + float(rng.normal(0.0, 0.25))
        coupling = compute_lagged_monthly_impulse_coupling(
            yrs_c, mos_c, x_sig.tolist(), yrs_c, mos_c, y_sig.tolist(),
            max_lag_months=2, baseline_start=2015, baseline_end=2019, min_common_months=24,
        )
        self.assertEqual(coupling["optimal_lag_months"], 1)
        self.assertGreater(float(coupling["optimal_lag_pw_tau"]), 0.4)
        self.assertLess(float(coupling["optimal_lag_sidak_p"]), 0.01)

    def test_baseline_climatology_anomalies_and_partial_trend(self) -> None:
        yrs = [y for y in range(2015, 2023) for _ in (3, 4, 5)]
        mos = [m for _ in range(2015, 2023) for m in (3, 4, 5)]
        vals = [10.0 + m + 0.0 * y for y, m in zip(yrs, mos)]
        anoms, _, clim, _, active = compute_baseline_climatology_anomalies(
            yrs, mos, vals, baseline_start=2015, baseline_end=2019
        )
        self.assertEqual(active, [3, 4, 5])
        self.assertTrue(all(abs(a) < 1e-9 for a in anoms))
        self.assertAlmostEqual(clim[3], 13.0)

        rng = np.random.default_rng(5)
        t = [2015.0 + i * 0.25 for i in range(24)]
        cov = rng.normal(0.0, 1.0, size=24).tolist()
        y = [1.5 * cov[i] - 0.4 * (t[i] - 2015.0) for i in range(24)]
        slope_dec, p_val, gamma = partial_trend_controlling_covariate(t, y, cov)
        self.assertAlmostEqual(slope_dec, -4.0, places=4)
        self.assertAlmostEqual(gamma, 1.5, places=4)
        self.assertLess(p_val, 0.001)

    def test_breakpoint_returns_structured_dict(self) -> None:
        t = [2015.0 + i / 12.0 for i in range(48)]
        y = [float(i) if i < 24 else float(48 - i) for i in range(48)]
        bp = structural_hinge_breakpoint_analysis(t, y, min_segment=6)
        self.assertTrue(bp.detected)
        self.assertTrue(bp.regime_reversal)
        self.assertLess(bp.davies_p_value, 0.01)

    def test_scale_invariance_across_sixteen_orders_of_magnitude(self) -> None:
        rng = np.random.default_rng(77)
        t = [2015.0 + i / 12.0 for i in range(48)]
        yrs = [2015 + i // 12 for i in range(48)]
        mos = [(i % 12) + 1 for i in range(48)]
        x = [0.2 * (ti - 2015.0) + float(rng.normal(0.0, 0.4)) for ti in t]
        cov = rng.normal(0.0, 1.0, size=48).tolist()
        y = [x[i] + 0.3 * cov[i] for i in range(48)]

        ref_tau = kendall_tau_b_bivariate(x, y)
        ref_hr = hamed_rao_modified_mk(t, x)
        ref_hs = hirsch_slack_seasonal_mk_and_slope(yrs, mos, x)
        ref_bt = fit_box_tiao_step_intervention(t, x, intervention_year=2018.0, covariates={"c": cov})
        ref_pt = partial_trend_controlling_covariate(t, x, cov)
        ref_bp = structural_hinge_breakpoint_analysis(t, x, min_segment=6)
        _, ref_z, _, _, ref_act = compute_baseline_climatology_anomalies(yrs, mos, x, baseline_start=2015, baseline_end=2017)

        for scale in (1e-8, 1e8):
            xs = [v * scale for v in x]
            ys = [v * scale for v in y]
            cs = [v * scale for v in cov]
            self.assertEqual(kendall_tau_b_bivariate(xs, ys), ref_tau)
            self.assertAlmostEqual(hamed_rao_modified_mk(t, xs)[5], ref_hr[5], places=10)
            hs = hirsch_slack_seasonal_mk_and_slope(yrs, mos, xs)
            self.assertAlmostEqual(hs["p_value_seasonal"], ref_hs["p_value_seasonal"], places=10)
            self.assertAlmostEqual(hs["van_belle_hughes"]["chi2_homogeneity"], ref_hs["van_belle_hughes"]["chi2_homogeneity"], places=6)
            bt = fit_box_tiao_step_intervention(t, xs, intervention_year=2018.0, covariates={"c": cs})
            self.assertAlmostEqual(bt["p_value_ar1"], ref_bt["p_value_ar1"], places=5)
            self.assertAlmostEqual(bt["delta_step"] / scale, ref_bt["delta_step"], places=6)
            pt = partial_trend_controlling_covariate(t, xs, cs)
            self.assertAlmostEqual(pt[1], ref_pt[1], places=10)
            bp = structural_hinge_breakpoint_analysis(t, xs, min_segment=6)
            self.assertAlmostEqual(bp.f_statistic, ref_bp.f_statistic, places=3)
            _, zs, _, _, act = compute_baseline_climatology_anomalies(yrs, mos, xs, baseline_start=2015, baseline_end=2017)
            self.assertEqual(act, ref_act)
            self.assertAlmostEqual(zs[0], ref_z[0], places=6)

    def test_baseline_climatology_withholds_missing_baseline_and_fao56_uses_023_albedo(self) -> None:
        # 2019-2022 series has only 1 year in 2015-2019 -> min_baseline_years=2 must withhold!
        yrs = [y for y in range(2019, 2023) for _ in (3, 4)]
        mos = [m for _ in range(2019, 2023) for m in (3, 4)]
        vals = [10.0, 20.0, 12.0, 22.0, 11.0, 21.0, 30.0, 40.0]
        anoms, zs, clim_m, clim_s, _ = compute_baseline_climatology_anomalies(
            yrs, mos, vals, baseline_start=2015, baseline_end=2019, min_baseline_years=2
        )
        self.assertTrue(all(math.isnan(clim_m[m]) for m in range(1, 13)))
        self.assertTrue(all(math.isnan(clim_s[m]) for m in range(1, 13)))
        self.assertTrue(all(math.isnan(a) for a in anoms))
        self.assertTrue(all(math.isnan(z) for z in zs))

        # FAO-56 ET0 must enforce reference grass albedo 0.23 and Eq. 37 R_so by default
        n = 6
        base = compute_fao56_vpd_and_pet_series(
            [18.0] * n, [24.0] * n, [12.0] * n, [60.0] * n, [18.0] * n, [2.5] * n,
            lat_deg=50.45, elevation_m=179.0, months=[3, 4, 5, 6, 7, 8],
        )
        with_ext = compute_fao56_vpd_and_pet_series(
            [18.0] * n, [24.0] * n, [12.0] * n, [60.0] * n, [18.0] * n, [2.5] * n,
            lat_deg=50.45, elevation_m=179.0, months=[3, 4, 5, 6, 7, 8],
            clrsky_sw_dwn_mj_m2_day=[28.0] * n, albedo_series=[0.05] * n,
        )
        self.assertEqual(base["pet_mm_day"], with_ext["pet_mm_day"])

    def test_reference_benchmark_matches_scipy_and_documents_ulp_sensitivity(self) -> None:
        from pathlib import Path
        import json
        from src.reference_benchmark import run_benchmark

        bench_path = Path(__file__).resolve().parents[1] / "reports" / "stats_reference_benchmark.json"
        self.assertTrue(bench_path.is_file(), f"Missing {bench_path}")
        committed = json.loads(bench_path.read_text(encoding="utf-8"))
        b = committed["benchmarks"]
        self.assertEqual(b["kendall_tau_b_vs_scipy_max_abs_diff"], 0.0)
        self.assertEqual(b["kendall_tau_b_scale_invariance_1e8_max_diff"], 0.0)
        self.assertEqual(b["theil_sen_slope_vs_scipy_max_abs_diff_per_yr"], 0.0)
        self.assertEqual(b["bh_fdr_vs_scipy_max_abs_diff"], 0.0)
        self.assertEqual(b["by_fdr_vs_scipy_max_abs_diff"], 0.0)
        self.assertLess(b["student_t_two_sided_p_max_abs_diff"], 1e-12)
        self.assertLess(b["box_tiao_step_vs_ols_max_abs_diff"], 1e-12)
        # Re-running live against temporary path produces matching benchmark values
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fresh = run_benchmark(out_json=Path(tmpdir) / "bench.json")
            self.assertEqual(fresh["benchmarks"], committed["benchmarks"])


if __name__ == "__main__":
    unittest.main()
