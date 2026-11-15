"""Build reports/trend_results.json: one trend verdict per region x variable x period.

Also runs the regional OMI NO2 Giovanni exports (data/frozen/no2_regional) through the
same daily-to-monthly pipeline as Kyiv and writes reports/no2_regional/.

The trend test is the one already used for Kyiv NO2 (air_analysis._evaluate_trend_window):
month-fixed-effects OLS with Newey-West HAC standard errors, with seasonal Theil-Sen and
Hamed-Rao modified Mann-Kendall as nonparametric checks. p-values are adjusted with
Benjamini-Hochberg across every assessed row; the verdict uses the adjusted p-value.

Run:  python -m src.trend_results
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from src.air_analysis import _evaluate_trend_window, compute_annual_seasonal_series, compute_baseline_comparison
from src.no2_pipeline import (
    DEFAULT_LOW_COVERAGE_FRACTION,
    aggregate_monthly,
    parse_giovanni_csv,
    reindex_daily_calendar,
    run_pipeline,
)
from src.stats_rigor import bh_q_values, write_strict_json

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
NO2_RAW_DIR = REPO_ROOT / "data" / "frozen" / "no2_regional"
NO2_OUT_DIR = REPORTS_DIR / "no2_regional"

ALPHA = 0.05
NO2_METRIC = "no2_mean_molec_cm2"
INVASION_LAST_PRE_MONTH = "2022-02"
WINDOWS = ("full_record", "pre_invasion")
METHOD = "Month-fixed-effects OLS with Newey-West HAC standard errors"

# region_id -> raw Giovanni export. Kyiv is processed by src.air_analysis (reports/no2_monthly.csv).
NO2_REGIONAL_FILES = {
    "donbas_kharkiv_east": "no2_donbas_kharkiv_east_OMNO2d_v004_2015-03_2022-08.csv",
    "south_steppe_belt": "no2_south_steppe_belt_OMNO2d_v004_2015-03_2022-08.csv",
    "central_interior_cand": "no2_central_interior_cand_OMNO2d_v004_2015-03_2022-08.csv",
    "west_ukraine_cand": "no2_west_ukraine_cand_OMNO2d_v004_2015-03_2022-08.csv",
    "poland_krakow": "no2_poland_krakow_OMNO2d_v004_2015-03_2022-08.csv",
    "czechia_prague": "no2_czechia_prague_OMNO2d_v004_2015-03_2022-08.csv",
    # Extra candidate; not one of the 8 atlas study boxes yet.
    "kharkiv_city": "no2_kharkiv_city_OMNO2d_v004_2015-03_2022-08.csv",
}
# Places that exist only in the NO2 exports (not in the 25-variable catalog). The atlas adds them as pins.
EXTRA_PLACES = {
    "kharkiv_city": {
        "name": "Kharkiv city",
        "role": "extra_no2_city_box",
        "is_ukraine_study_area": True,
        "description": "0.5° box over Kharkiv city. NO₂ only; inside the East front box.",
    },
}
NO2_ATLAS_FILE = "atlas_no2_regional.json"
SMALL_NO2_BOXES = {"kyiv_no2_box", "poland_krakow", "czechia_prague", "kharkiv_city"}

MONTHLY_ATLAS_FILES = (
    "atlas_air_weather_ukraine.json",
    "atlas_water_ukraine.json",
    "atlas_earth_ukraine.json",
)
FIRE_FILE = "atlas_fire_ukraine.json"
FIRE_METRICS = {
    "fire_type0_per_1k_km2_day": "type0_vegetation_nominal_high",
    "fire_type2_per_1k_km2_day": "type2_static_industrial",
}

CAVEAT_NOT_WAR = (
    "A steady rate over 2015–2022 mixes pre-war variability, COVID-19 in 2020 and the war; "
    "it is not a war effect by itself."
)
CAVEAT_PRE = "Uses months up to February 2022 only, so it describes the background before the invasion."
CAVEAT_POWER = "Average over the study box from NASA POWER (MERRA-2 / CERES); not a local measurement."
CAVEAT_NO2_COLUMN = "Satellite column of NO₂ above the box; not street-level air quality."
CAVEAT_SMALL_BOX = "Small 0.5° box (about four satellite grid cells), so single cloudy days matter a lot."


# --------------------------------------------------------------------------- NO2 monthly

def build_regional_no2(raw_dir: Path = NO2_RAW_DIR, out_dir: Path = NO2_OUT_DIR) -> Dict[str, pd.DataFrame]:
    """Run each regional export through the Kyiv daily-to-monthly pipeline. Missing files are skipped."""
    out_dir.mkdir(parents=True, exist_ok=True)
    monthly: Dict[str, pd.DataFrame] = {}
    summary: List[Dict[str, object]] = []
    for region_id, filename in NO2_REGIONAL_FILES.items():
        src = raw_dir / filename
        if not src.exists():
            continue
        csv_out = out_dir / f"{region_id}_monthly.csv"
        quality = run_pipeline(
            input_csv=src,
            output_csv=csv_out,
            output_chart=out_dir / f"{region_id}_monthly.png",
            output_quality=out_dir / f"{region_id}_quality.json",
        )
        if not all(quality["validation_checks"].values()):
            raise ValueError(f"Accounting checks failed for {region_id}: {quality['validation_checks']}")
        df = pd.read_csv(csv_out, dtype={"month": str})
        monthly[region_id] = df
        qc = quality["monthly_summary"]
        summary.append(
            {
                "region_id": region_id,
                "input_file": filename,
                "input_sha256": quality["provenance"]["input_sha256"],
                "user_bounding_box": quality["provenance"]["user_bounding_box"],
                "data_bounding_box": quality["provenance"]["data_bounding_box"],
                "months": int(len(df)),
                "months_with_a_mean": int(df[NO2_METRIC].notna().sum()),
                "low_coverage_months": int(qc["low_coverage_months_count"]),
                "sparse_months_under_10_days": int(qc["sparse_months_count"]),
                "very_sparse_months_under_5_days": int(qc["very_sparse_months_count"]),
            }
        )
    write_strict_json(
        out_dir / "summary.json",
        {
            "schema_version": "1.0.0",
            "coverage_flag_rule": f"coverage_fraction < {DEFAULT_LOW_COVERAGE_FRACTION:.2f}",
            "note": "Same parsing, calendar reindexing and monthly averaging as the Kyiv pipeline (src.no2_pipeline).",
            "regions": summary,
        },
    )
    return monthly


def _box_area_km2(b: Dict[str, float]) -> float:
    import math

    r = 6371.0088
    return (
        r * r * math.radians(b["east"] - b["west"])
        * (math.sin(math.radians(b["north"])) - math.sin(math.radians(b["south"])))
    )


def build_no2_atlas_payload(raw_dir: Path = NO2_RAW_DIR) -> Dict[str, object]:
    """Monthly NO2 series and the March-August 2022 vs 2015-2019 comparison per region, for /api/air/no2.

    Uses the Kyiv functions unchanged (valid-day weighting, equal weight per baseline year)."""
    regions: Dict[str, object] = {}
    extra_places: List[Dict[str, object]] = []
    for region_id, filename in NO2_REGIONAL_FILES.items():
        src = raw_dir / filename
        if not src.exists():
            continue
        daily_raw, meta = parse_giovanni_csv(src)
        daily_full, _ = reindex_daily_calendar(daily_raw, meta)
        monthly, _ = aggregate_monthly(daily_full)
        annual = compute_annual_seasonal_series(daily_full, monthly)
        cmp = compute_baseline_comparison(
            annual,
            comparison_id="primary_2015_2019_valid_day",
            label="March–August 2022 vs. 2015–2019",
            baseline_years=[2015, 2016, 2017, 2018, 2019],
        )
        series = []
        for row in monthly.to_dict("records"):
            value = row[NO2_METRIC]
            cov = row["valid_days"] / row["calendar_days"]
            series.append(
                {
                    "month": row["month"],
                    "value": None if pd.isna(value) else float(value),
                    "valid_days": int(row["valid_days"]),
                    "calendar_days": int(row["calendar_days"]),
                    "coverage_fraction": round(float(cov), 4),
                    "flagged_below_50_pct": bool(cov < DEFAULT_LOW_COVERAGE_FRACTION),
                }
            )
        box = meta["user_bounding_box"]
        regions[region_id] = {
            "region_id": region_id,
            "bounds": box,
            "data_bounds": meta["data_bounding_box"],
            "monthly_series": series,
            "seasonal_mar_aug": {
                "vs_2015_2019": {
                    "baseline_mean": cmp["baseline_mean_molec_cm2"],
                    "target_mean": cmp["target_mean_molec_cm2"],
                    "abs_diff": cmp["absolute_change_molec_cm2"],
                    "pct_change": cmp["pct_change"],
                    "pct_change_status": cmp["pct_change_status"],
                    "target_valid_days": cmp.get("target_valid_days"),
                    "target_calendar_days": cmp.get("target_calendar_days"),
                    "any_flagged_month": cmp.get("any_flagged_month"),
                }
            },
        }
        if region_id in EXTRA_PLACES:
            w, s_, e, n = box["west"], box["south"], box["east"], box["north"]
            extra_places.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[[w, s_], [e, s_], [e, n], [w, n], [w, s_]]]},
                    "properties": {
                        "region_id": region_id,
                        "area_km2": round(_box_area_km2(box), 1),
                        "center": {"lat": round((s_ + n) / 2, 4), "lon": round((w + e) / 2, 4)},
                        **EXTRA_PLACES[region_id],
                    },
                }
            )
    return {
        "schema_version": "1.0.0",
        "status": "available",
        "metric_id": NO2_METRIC,
        "units": "molecules/cm^2",
        "dataset": "OMI OMNO2d v004, tropospheric column, 30% cloud screened (NASA Giovanni area average)",
        "coverage_flag_rule": f"coverage_fraction < {DEFAULT_LOW_COVERAGE_FRACTION:.2f}",
        "regions": regions,
        "extra_places": extra_places,
    }


# --------------------------------------------------------------------------- trend core

def _frame(months: Iterable[str], values: Iterable[Optional[float]]) -> pd.DataFrame:
    df = pd.DataFrame({"month": list(months), NO2_METRIC: pd.to_numeric(pd.Series(list(values)), errors="coerce")})
    df["year"] = df["month"].str[:4].astype(int)
    df["mnum"] = df["month"].str[5:].astype(int)
    return df.sort_values("month").reset_index(drop=True)


def _window(df: pd.DataFrame, window_id: str) -> pd.DataFrame:
    return df[df["month"] <= INVASION_LAST_PRE_MONTH].copy() if window_id == "pre_invasion" else df.copy()


def evaluate(df: pd.DataFrame, window_id: str) -> Dict[str, object]:
    """Generic wrapper: the Kyiv trend function is unit-agnostic; only its key names mention NO2."""
    res = _evaluate_trend_window(_window(df, window_id), window_id=window_id, label=window_id)
    if res["status"] != "assessed":
        return {"status": "not_assessed", "n_months": res["n_months"], "reason": res.get("reason")}
    nonpar = res["nonparametric_sensitivity"]
    hr = nonpar.get("hamed_rao_mk") or {}
    return {
        "status": "assessed",
        "start_month": res["start_month"],
        "end_month": res["end_month"],
        "n_months": res["n_months"],
        "slope_per_year": res["slope_molec_cm2_per_year"],
        "ci_low": res["ci_95_lower_molec_cm2_per_year"],
        "ci_high": res["ci_95_upper_molec_cm2_per_year"],
        "p_value": res["p_value"],
        "theil_sen_slope_per_year": nonpar.get("seasonal_theil_sen_molec_cm2_per_year"),
        "p_value_hamed_rao": hr.get("p_value_hamed_rao"),
    }


SUMMER_MONTHS = (4, 5, 6, 7, 8, 9)


def evaluate_months_subset(df: pd.DataFrame, window_id: str, months: Sequence[int]) -> Dict[str, object]:
    """Same model as `evaluate` (month fixed effects, Newey-West HAC, lag <= 6) on a subset of calendar months.

    Used as the NO2 confirmation when winter months are too poorly observed to repeat the full-year test."""
    import math

    import numpy as np
    from scipy.stats import t as student_t

    sub = _window(df, window_id)
    sub = sub[sub["mnum"].isin(list(months))].dropna(subset=[NO2_METRIC]).sort_values("month").reset_index(drop=True)
    n = int(len(sub))
    counts = sub.groupby("mnum")[NO2_METRIC].size()
    if n < 24 or len(counts) < len(months) or int(counts.min()) < 2:
        return {"status": "not_assessed", "n_months": n}
    t_yr = (pd.to_datetime(sub["month"] + "-01") - pd.to_datetime(sub["month"].iloc[0] + "-01")).dt.days.to_numpy(dtype=float) / 365.25
    X = np.column_stack([t_yr, pd.get_dummies(sub["mnum"], dtype=float).to_numpy()])
    y = sub[NO2_METRIC].to_numpy(dtype=float)
    df_resid = n - int(X.shape[1])
    if df_resid < 10 or np.linalg.matrix_rank(X) < X.shape[1]:
        return {"status": "not_assessed", "n_months": n}
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    scores = X * resid[:, None]
    omega = scores.T @ scores
    lag_limit = min(6, max(1, n // 4))
    for lag in range(1, lag_limit + 1):
        cross = scores[lag:].T @ scores[:-lag]
        omega = omega + (1.0 - lag / (lag_limit + 1.0)) * (cross + cross.T)
    var_slope = float(((n / df_resid) * (xtx_inv @ omega @ xtx_inv))[0, 0])
    if not var_slope > 0:
        return {"status": "not_assessed", "n_months": n}
    slope, se = float(beta[0]), math.sqrt(var_slope)
    t_crit = float(student_t.ppf(0.975, df=df_resid))
    return {
        "status": "assessed",
        "n_months": n,
        "slope_per_year": slope,
        "ci_low": slope - t_crit * se,
        "ci_high": slope + t_crit * se,
        "p_value": round(float(2.0 * student_t.sf(abs(slope / se), df=df_resid)), 6),
    }


def _row(region_id: str, metric_id: str, window_id: str, ev: Dict[str, object], caveats: List[str]) -> Dict[str, object]:
    assessed = ev["status"] == "assessed"
    return {
        "region_id": region_id,
        "metric_id": metric_id,
        "window_id": window_id,
        "status": ev["status"],
        "start_month": ev.get("start_month"),
        "end_month": ev.get("end_month"),
        "n_months": ev.get("n_months"),
        "slope_per_year": ev.get("slope_per_year") if assessed else None,
        "ci_low": ev.get("ci_low") if assessed else None,
        "ci_high": ev.get("ci_high") if assessed else None,
        "p_value": ev.get("p_value") if assessed else None,
        "p_value_fdr": None,
        "significant": False if assessed else None,
        "method": METHOD if assessed else None,
        "theil_sen_slope_per_year": ev.get("theil_sen_slope_per_year") if assessed else None,
        "p_value_hamed_rao": ev.get("p_value_hamed_rao") if assessed else None,
        "caveats": caveats,
    }


# --------------------------------------------------------------------------- rows per source

def no2_rows(region_id: str, monthly: pd.DataFrame) -> List[Dict[str, object]]:
    """Primary trend on every month with a mean (the Kyiv rule) plus a coverage sensitivity.

    Coverage rule: a NO2 trend may only be called significant if it is still significant, with the
    same sign, after dropping months below 50% daily coverage. If those months cannot support the
    test at all, the verdict cannot be 'significant'.
    """
    rows: List[Dict[str, object]] = []
    all_df = _frame(monthly["month"], monthly[NO2_METRIC])
    cov = monthly["valid_days"] / monthly["calendar_days"]
    good = monthly[cov >= DEFAULT_LOW_COVERAGE_FRACTION]
    good_df = _frame(good["month"], good[NO2_METRIC])
    for window_id in WINDOWS:
        ev = evaluate(all_df, window_id)
        sens = evaluate(good_df, window_id)
        win_all = _window(all_df, window_id)
        with_mean = int(win_all[NO2_METRIC].notna().sum())
        n_low = with_mean - int(_window(good_df, window_id)[NO2_METRIC].notna().sum())
        caveats = [CAVEAT_NO2_COLUMN]
        if n_low:
            caveats.append(
                f"In {n_low} of {with_mean} months the satellite saw the box on fewer than half the days (mostly winter cloud)."
            )
        robust: Optional[bool] = None
        check = "none"
        summer: Dict[str, object] = {"status": "not_run"}
        if ev["status"] == "assessed":
            if n_low == 0:
                robust, check = True, "no_low_coverage_months"
                caveats.append("No low-coverage months in this period.")
            elif sens["status"] == "assessed":
                check = "well_observed_months_all_year"
                same_sign = (sens["slope_per_year"] > 0) == (ev["slope_per_year"] > 0)
                robust = bool(same_sign and sens["p_value"] < ALPHA)
                caveats.append(
                    "Without those low-coverage months the rate "
                    + ("keeps" if same_sign else "changes")
                    + f" its direction (p = {sens['p_value']:.3f})."
                )
            else:
                # Team decision (2026-11-15): when winter is too poorly observed, confirm on April-September only.
                check = "well_observed_months_april_september"
                summer = evaluate_months_subset(good_df, window_id, SUMMER_MONTHS)
                if summer["status"] == "assessed":
                    same_sign = (summer["slope_per_year"] > 0) == (ev["slope_per_year"] > 0)
                    robust = bool(same_sign and summer["p_value"] < ALPHA)
                    caveats.append(
                        "Winter is too cloudy to re-test, so the check uses well-observed April–September months: "
                        + ("same direction" if same_sign else "opposite direction")
                        + f", p = {summer['p_value']:.3f}."
                    )
                else:
                    robust = False
                    caveats.append("Too few well-observed months to confirm this rate, even in April–September.")
        if region_id in SMALL_NO2_BOXES:
            caveats.append(CAVEAT_SMALL_BOX)
        caveats.append(CAVEAT_PRE if window_id == "pre_invasion" else CAVEAT_NOT_WAR)
        row = _row(region_id, NO2_METRIC, window_id, ev, caveats)
        row["coverage_sensitivity"] = {
            "rule": f"months with coverage_fraction >= {DEFAULT_LOW_COVERAGE_FRACTION:.2f} only",
            "low_coverage_months_in_window": n_low,
            "status": sens["status"],
            "n_months": sens.get("n_months"),
            "slope_per_year": sens.get("slope_per_year"),
            "p_value": sens.get("p_value"),
            "check_used": check,
            "april_september": {k: summer.get(k) for k in ("status", "n_months", "slope_per_year", "p_value")},
            "robust": robust,
        }
        rows.append(row)
    return rows


def monthly_metric_rows(regions: Dict[str, dict]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for region_id, region in regions.items():
        for metric_id, metric in (region.get("metrics") or {}).items():
            series = metric.get("monthly_series") or []
            df = _frame((p["month"] for p in series), (p.get("value") for p in series))
            for window_id in WINDOWS:
                ev = evaluate(df, window_id)
                caveats = [CAVEAT_POWER, CAVEAT_PRE if window_id == "pre_invasion" else CAVEAT_NOT_WAR]
                rows.append(_row(region_id, metric_id, window_id, ev, caveats))
    return rows


def fire_rows(fire_regions: Dict[str, dict], study_regions: Sequence[str]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for region_id in study_regions:
        region = fire_regions.get(region_id)
        if not region:
            continue
        for metric_id, filter_id in FIRE_METRICS.items():
            series = (region.get("monthly_series") or {}).get(filter_id) or []
            months = sorted(p["month"] for p in series if p.get("month"))
            for window_id in WINDOWS:
                rows.append(
                    {
                        "region_id": region_id,
                        "metric_id": metric_id,
                        "window_id": window_id,
                        "status": "insufficient_evidence",
                        "start_month": months[0] if months else None,
                        "end_month": months[-1] if months else None,
                        "n_months": len(months),
                        "slope_per_year": None,
                        "ci_low": None,
                        "ci_high": None,
                        "p_value": None,
                        "p_value_fdr": None,
                        "significant": None,
                        "method": None,
                        "caveats": [
                            "Only four fire seasons (2019–2022) are comparable; a trend test needs more years.",
                            "Read the 2022 change against 2019–2021 instead; it is a description, not a test.",
                        ],
                    }
                )
    return rows


# --------------------------------------------------------------------------- assemble

def apply_fdr(rows: List[Dict[str, object]]) -> None:
    """BH-adjust within each variable (team decision 2026-11-15), then apply the NO2 coverage rule."""
    by_metric: Dict[str, List[Dict[str, object]]] = {}
    for r in rows:
        if r["status"] == "assessed":
            by_metric.setdefault(str(r["metric_id"]), []).append(r)
    for family in by_metric.values():
        for row, q in zip(family, bh_q_values([float(r["p_value"]) for r in family])):
            row["p_value_fdr"] = round(float(q), 6)
            row["fdr_family_size"] = len(family)
            significant = bool(q < ALPHA)
            sens = row.get("coverage_sensitivity")
            if significant and sens is not None and sens["robust"] is False:
                significant = False
                confirmable = sens["status"] == "assessed" or sens["april_september"]["status"] == "assessed"
                if confirmable:
                    row["caveats"].insert(0, "Not called significant: it does not hold on well-observed months alone.")
                else:
                    # Strong raw signal that cannot be checked on well-observed months: say so instead of a verdict.
                    slope_text = f"{float(row['slope_per_year']) / 1e15:+.3f}".replace("-", "−")
                    row["unconfirmed_estimate"] = {
                        key: row[key]
                        for key in ("slope_per_year", "ci_low", "ci_high", "p_value", "p_value_fdr", "n_months", "method")
                    }
                    row["status"] = "insufficient_evidence"
                    for key in ("slope_per_year", "ci_low", "ci_high", "p_value", "p_value_fdr", "method"):
                        row[key] = None
                    row["significant"] = None
                    row["caveats"] = [
                        f"The raw numbers change steeply ({slope_text} ×10¹⁵ molecules/cm² per year), but too many "
                        "months are poorly observed to confirm it."
                    ] + [c for c in row["caveats"] if not c.startswith("Too few well-observed")]
                    continue
            row["significant"] = significant
            row["caveats"] = row["caveats"][:5]


def build(reports_dir: Path = REPORTS_DIR, raw_dir: Path = NO2_RAW_DIR, out_dir: Path = NO2_OUT_DIR) -> Dict[str, object]:
    rows: List[Dict[str, object]] = []

    kyiv = pd.read_csv(reports_dir / "no2_monthly.csv", dtype={"month": str})
    rows += no2_rows("kyiv_no2_box", kyiv)
    for region_id, monthly in build_regional_no2(raw_dir, out_dir).items():
        rows += no2_rows(region_id, monthly)

    study_regions: List[str] = []
    for name in MONTHLY_ATLAS_FILES:
        regions = json.loads((reports_dir / name).read_text(encoding="utf-8"))["result"]["regions"]
        study_regions = study_regions or list(regions)
        rows += monthly_metric_rows(regions)

    fire = json.loads((reports_dir / FIRE_FILE).read_text(encoding="utf-8"))["result"]
    rows += monthly_metric_rows(fire.get("context_weather_regions") or {})
    rows += fire_rows(fire.get("regions") or {}, study_regions)

    n_tested = sum(1 for r in rows if r["status"] == "assessed")
    apply_fdr(rows)
    assessed = [r for r in rows if r["status"] == "assessed"]
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alpha": ALPHA,
        "multiple_testing": (
            f"Benjamini-Hochberg within each variable (places x periods, about 12-16 tests each; {n_tested} tests "
            "in total); 'significant' means p_value_fdr < alpha"
        ),
        "no2_coverage_rule": (
            "NO2 trends use every month with a mean (as for Kyiv). A NO2 trend is only called significant if it is "
            "confirmed (same sign, p < 0.05) on months with at least 50% daily coverage: all year where possible, "
            "otherwise April-September only."
        ),
        "decisions": "docs/decisions.md",
        "counts": {
            "rows": len(rows),
            "tested": n_tested,
            "assessed": len(assessed),
            "significant": sum(1 for r in assessed if r["significant"]),
            "insufficient_evidence": sum(1 for r in rows if r["status"] == "insufficient_evidence"),
            "not_assessed": sum(1 for r in rows if r["status"] == "not_assessed"),
        },
        "results": rows,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--raw-dir", type=Path, default=NO2_RAW_DIR)
    args = parser.parse_args(argv)
    payload = build(args.reports_dir, args.raw_dir, args.reports_dir / "no2_regional")
    write_strict_json(args.reports_dir / "trend_results.json", payload)
    write_strict_json(args.reports_dir / NO2_ATLAS_FILE, build_no2_atlas_payload(args.raw_dir))
    print(json.dumps(payload["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
