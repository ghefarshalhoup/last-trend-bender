"""Complete Air / OMNO2d v004 comparison, sensitivity, statistical assessment, visualization, and backend JSON export."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "war_env_tracker_mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata, t as student_t

from src.no2_pipeline import (
    DEFAULT_LOW_COVERAGE_FRACTION,
    DEFAULT_RAW_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_SPARSE_MIN_VALID_DAYS,
    _discover_default_input,
    aggregate_monthly,
    parse_giovanni_csv,
    reindex_daily_calendar,
    run_pipeline,
)

MARCH_AUGUST_MONTHS: Tuple[int, ...] = (3, 4, 5, 6, 7, 8)
MONTH_NAMES = {3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug"}
PRIMARY_BASELINE_YEARS: Tuple[int, ...] = (2015, 2016, 2017, 2018, 2019)
SENSITIVITY_BASELINE_YEARS: Tuple[int, ...] = (2019, 2020, 2021)
TARGET_YEAR = 2022
DEFAULT_REGION_ID = "ukraine_kyiv"
DEFAULT_REGION_NAME = "Kyiv, Ukraine"
DEFAULT_REGION_CENTER = {"lat": 50.450, "lon": 30.523}
SCHEMA_VERSION = "1.0.0"


def _clean_float(val: object, digits: Optional[int] = None) -> Optional[float]:
    """Return finite Python float (optionally rounded) or None so NaN/Inf never serialize to JSON."""
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits) if digits is not None else f


def _safe_pct_change(target_val: Optional[float], baseline_val: Optional[float]) -> Tuple[Optional[float], Optional[float], str]:
    """Compute (abs_change, pct_change, status) withholding percentages when baseline <= 0 or missing."""
    t_clean = _clean_float(target_val)
    b_clean = _clean_float(baseline_val)
    if t_clean is None or b_clean is None:
        return None, None, "withheld_missing_data"
    abs_diff = t_clean - b_clean
    if b_clean <= 0.0:
        return abs_diff, None, "withheld_nonpositive_baseline"
    return abs_diff, 100.0 * abs_diff / b_clean, "computed"


def compute_annual_seasonal_series(
    daily_full: pd.DataFrame,
    monthly_df: pd.DataFrame,
    months: Sequence[int] = MARCH_AUGUST_MONTHS,
    low_coverage_threshold: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> pd.DataFrame:
    """Compute annual March–August means under both valid-day weighting and equal-month weighting."""
    months_set = sorted({int(m) for m in months})
    m_df = monthly_df.copy()
    m_df["year"] = m_df["month"].str[:4].astype(int)
    m_df["mnum"] = m_df["month"].str[5:].astype(int)
    m_df["cov_exact"] = m_df["valid_days"] / m_df["calendar_days"]
    m_sub = m_df[m_df["mnum"].isin(months_set)]

    d_df = daily_full.copy()
    d_df["year"] = d_df["date"].dt.year
    d_df["mnum"] = d_df["date"].dt.month
    d_sub = d_df[d_df["mnum"].isin(months_set)]

    years = sorted(set(m_sub["year"].unique()).union(set(d_sub["year"].unique())))
    rows: List[Dict[str, object]] = []
    for yr in years:
        d_yr = d_sub[d_sub["year"] == yr]
        m_yr = m_sub[m_sub["year"] == yr].sort_values("mnum")
        valid_vals = d_yr.loc[d_yr["status"] == "valid", "value"].dropna()
        valid_days = int(len(valid_vals))
        calendar_days = int(len(d_yr))
        cov_frac = round(valid_days / float(calendar_days), 4) if calendar_days > 0 else 0.0

        valid_day_mean = _clean_float(valid_vals.mean()) if valid_days > 0 else None
        obs_months = m_yr.loc[m_yr["valid_days"] > 0, "no2_mean_molec_cm2"].dropna()
        equal_month_mean = _clean_float(obs_months.mean()) if len(obs_months) > 0 else None

        flagged_months = [
            {
                "month": str(r.month),
                "valid_days": int(r.valid_days),
                "calendar_days": int(r.calendar_days),
                "coverage_fraction": float(r.coverage_fraction),
            }
            for r in m_yr.itertuples(index=False)
            if (r.valid_days / r.calendar_days) < low_coverage_threshold
        ]
        rows.append(
            {
                "year": int(yr),
                "months_included": months_set,
                "valid_days": valid_days,
                "calendar_days": calendar_days,
                "coverage_fraction": cov_frac,
                "observed_months_count": int(len(obs_months)),
                "expected_months_count": int(len(months_set)),
                "valid_day_mean_molec_cm2": valid_day_mean,
                "equal_month_mean_molec_cm2": equal_month_mean,
                "flagged_months_count": int(len(flagged_months)),
                "flagged_months": flagged_months,
                "any_flagged_month": bool(len(flagged_months) > 0),
            }
        )
    return pd.DataFrame(rows)


def compute_baseline_comparison(
    annual_df: pd.DataFrame,
    comparison_id: str,
    label: str,
    baseline_years: Sequence[int],
    target_year: int = TARGET_YEAR,
    weighting: str = "valid_day_annual_equal_weight",
    months_included: Sequence[int] = MARCH_AUGUST_MONTHS,
    note: str = "",
) -> Dict[str, object]:
    """Compare target_year against an equal-weighted baseline of annual seasonal means."""
    col = "valid_day_mean_molec_cm2" if weighting == "valid_day_annual_equal_weight" else "equal_month_mean_molec_cm2"
    if not months_included or annual_df.empty:
        return {
            "comparison_id": comparison_id,
            "label": label,
            "weighting": weighting,
            "baseline_years_requested": [int(y) for y in baseline_years],
            "available_baseline_years": [],
            "unavailable_baseline_years": [int(y) for y in baseline_years],
            "target_year": int(target_year),
            "months_included": [int(m) for m in months_included],
            "baseline_mean_molec_cm2": None,
            "baseline_annual_min_molec_cm2": None,
            "baseline_annual_max_molec_cm2": None,
            "target_mean_molec_cm2": None,
            "absolute_change_molec_cm2": None,
            "pct_change": None,
            "pct_change_status": "withheld_no_remaining_months",
            "baseline_valid_days": 0,
            "baseline_calendar_days": 0,
            "target_valid_days": 0,
            "target_calendar_days": 0,
            "flagged_months_in_baseline": [],
            "flagged_months_in_target": [],
            "any_flagged_month": False,
            "sampling_sensitivity_review_required": False,
            "note": note,
        }

    by_year = annual_df.set_index("year")
    avail_yrs: List[int] = []
    unavail_yrs: List[int] = []
    base_vals: List[float] = []
    flagged_base: List[Dict[str, object]] = []
    base_valid_days = 0
    base_cal_days = 0

    for yr in baseline_years:
        if yr not in by_year.index:
            unavail_yrs.append(int(yr))
            continue
        row = by_year.loc[yr]
        val = _clean_float(row[col])
        if val is None:
            unavail_yrs.append(int(yr))
        else:
            avail_yrs.append(int(yr))
            base_vals.append(val)
        base_valid_days += int(row["valid_days"])
        base_cal_days += int(row["calendar_days"])
        flagged_base.extend(list(row["flagged_months"]))

    baseline_mean = _clean_float(np.mean(base_vals)) if base_vals else None
    baseline_min = _clean_float(np.min(base_vals)) if base_vals else None
    baseline_max = _clean_float(np.max(base_vals)) if base_vals else None

    if target_year in by_year.index:
        t_row = by_year.loc[target_year]
        target_mean = _clean_float(t_row[col])
        target_valid_days = int(t_row["valid_days"])
        target_cal_days = int(t_row["calendar_days"])
        flagged_target = list(t_row["flagged_months"])
    else:
        target_mean = None
        target_valid_days = 0
        target_cal_days = 0
        flagged_target = []

    abs_diff, pct_diff, pct_status = _safe_pct_change(target_mean, baseline_mean)
    any_flagged = bool(flagged_base or flagged_target)

    return {
        "comparison_id": comparison_id,
        "label": label,
        "weighting": weighting,
        "baseline_years_requested": [int(y) for y in baseline_years],
        "available_baseline_years": avail_yrs,
        "unavailable_baseline_years": unavail_yrs,
        "target_year": int(target_year),
        "months_included": [int(m) for m in months_included],
        "baseline_mean_molec_cm2": baseline_mean,
        "baseline_annual_min_molec_cm2": baseline_min,
        "baseline_annual_max_molec_cm2": baseline_max,
        "target_mean_molec_cm2": target_mean,
        "absolute_change_molec_cm2": _clean_float(abs_diff),
        "pct_change": _clean_float(pct_diff, 4),
        "pct_change_status": pct_status,
        "baseline_valid_days": base_valid_days,
        "baseline_calendar_days": base_cal_days,
        "target_valid_days": target_valid_days,
        "target_calendar_days": target_cal_days,
        "flagged_months_in_baseline": flagged_base,
        "flagged_months_in_target": flagged_target,
        "any_flagged_month": any_flagged,
        "sampling_sensitivity_review_required": any_flagged,
        "note": note,
    }


def _summarize_baseline_month(
    month_slice: pd.DataFrame,
    expected_years: Sequence[int],
    low_coverage_threshold: float,
) -> Dict[str, object]:
    by_yr = month_slice.set_index("year")
    vals: List[float] = []
    covs: List[float] = []
    avail_yrs: List[int] = []
    unavail_yrs: List[int] = []
    flagged_years: List[str] = []
    valid_days_sum = 0
    cal_days_sum = 0

    for yr in expected_years:
        if yr not in by_yr.index:
            unavail_yrs.append(int(yr))
            continue
        r = by_yr.loc[yr]
        val = _clean_float(r["no2_mean_molec_cm2"])
        cov_exact = float(r["valid_days"]) / float(r["calendar_days"]) if r["calendar_days"] > 0 else 0.0
        covs.append(cov_exact)
        valid_days_sum += int(r["valid_days"])
        cal_days_sum += int(r["calendar_days"])
        if cov_exact < low_coverage_threshold:
            flagged_years.append(f"{yr} ({int(r['valid_days'])}/{int(r['calendar_days'])}d)")
        if val is None:
            unavail_yrs.append(int(yr))
        else:
            avail_yrs.append(int(yr))
            vals.append(val)

    return {
        "mean_molec_cm2": _clean_float(np.mean(vals)) if vals else None,
        "min_molec_cm2": _clean_float(np.min(vals)) if vals else None,
        "max_molec_cm2": _clean_float(np.max(vals)) if vals else None,
        "sd_molec_cm2": _clean_float(np.std(vals, ddof=1)) if len(vals) >= 2 else None,
        "available_years": avail_yrs,
        "unavailable_years": unavail_yrs,
        "mean_coverage_fraction": _clean_float(np.mean(covs), 4) if covs else None,
        "valid_days_total": valid_days_sum,
        "calendar_days_total": cal_days_sum,
        "flagged_years_count": len(flagged_years),
        "flagged_years_detail": flagged_years,
    }


def compute_matched_month_comparisons(
    monthly_df: pd.DataFrame,
    primary_years: Sequence[int] = PRIMARY_BASELINE_YEARS,
    sensitivity_years: Sequence[int] = SENSITIVITY_BASELINE_YEARS,
    target_year: int = TARGET_YEAR,
    months: Sequence[int] = MARCH_AUGUST_MONTHS,
    low_coverage_threshold: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> List[Dict[str, object]]:
    """Build month-by-month March–August comparisons of target_year against both baselines."""
    m_df = monthly_df.copy()
    m_df["year"] = m_df["month"].str[:4].astype(int)
    m_df["mnum"] = m_df["month"].str[5:].astype(int)

    results: List[Dict[str, object]] = []
    for mnum in months:
        m_slice = m_df[m_df["mnum"] == mnum]
        prim = _summarize_baseline_month(m_slice, primary_years, low_coverage_threshold)
        sens = _summarize_baseline_month(m_slice, sensitivity_years, low_coverage_threshold)

        t_rows = m_slice[m_slice["year"] == target_year]
        if t_rows.empty:
            t_mean = None
            t_valid = 0
            t_cal = 0
            t_cov = None
            t_flagged = True
        else:
            tr = t_rows.iloc[0]
            t_mean = _clean_float(tr["no2_mean_molec_cm2"])
            t_valid = int(tr["valid_days"])
            t_cal = int(tr["calendar_days"])
            t_cov_exact = float(t_valid) / float(t_cal) if t_cal > 0 else 0.0
            t_cov = round(t_cov_exact, 4)
            t_flagged = bool(t_cov_exact < low_coverage_threshold)

        r21_rows = m_slice[m_slice["year"] == 2021]
        y2021_mean = _clean_float(r21_rows.iloc[0]["no2_mean_molec_cm2"]) if not r21_rows.empty else None

        abs_p, pct_p, st_p = _safe_pct_change(t_mean, prim["mean_molec_cm2"])
        abs_s, pct_s, st_s = _safe_pct_change(t_mean, sens["mean_molec_cm2"])

        results.append(
            {
                "calendar_month": int(mnum),
                "month_name": MONTH_NAMES.get(mnum, str(mnum)),
                "primary_2015_2019": prim,
                "sensitivity_2019_2021": sens,
                "year_2021_mean_molec_cm2": y2021_mean,
                "target_2022": {
                    "mean_molec_cm2": t_mean,
                    "valid_days": t_valid,
                    "calendar_days": t_cal,
                    "coverage_fraction": t_cov,
                    "flagged_below_50_pct": t_flagged,
                },
                "vs_primary_2015_2019": {
                    "absolute_change_molec_cm2": _clean_float(abs_p),
                    "pct_change": _clean_float(pct_p, 4),
                    "pct_change_status": st_p,
                },
                "vs_sensitivity_2019_2021": {
                    "absolute_change_molec_cm2": _clean_float(abs_s),
                    "pct_change": _clean_float(pct_s, 4),
                    "pct_change_status": st_s,
                },
            }
        )
    return results


def compute_coverage_exclusion_sensitivities(
    daily_full: pd.DataFrame,
    monthly_df: pd.DataFrame,
    primary_years: Sequence[int] = PRIMARY_BASELINE_YEARS,
    sensitivity_years: Sequence[int] = SENSITIVITY_BASELINE_YEARS,
    target_year: int = TARGET_YEAR,
    months: Sequence[int] = MARCH_AUGUST_MONTHS,
    low_coverage_threshold: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> Dict[str, object]:
    """
    Evaluate sensitivity when excluding low-coverage (<50%) months using identical
    remaining calendar months across baseline years and target_year.
    """
    m_df = monthly_df.copy()
    m_df["year"] = m_df["month"].str[:4].astype(int)
    m_df["mnum"] = m_df["month"].str[5:].astype(int)
    m_df["passes_cov"] = (m_df["valid_days"] > 0) & ((m_df["valid_days"] / m_df["calendar_days"]) >= low_coverage_threshold)

    def _run_subset(
        comp_id: str,
        label: str,
        base_yrs: Sequence[int],
        keep_months: List[int],
        weighting: str,
        note: str,
    ) -> Dict[str, object]:
        if not keep_months:
            sub_ann = pd.DataFrame()
        else:
            sub_ann = compute_annual_seasonal_series(
                daily_full,
                monthly_df,
                months=keep_months,
                low_coverage_threshold=low_coverage_threshold,
            )
        return compute_baseline_comparison(
            annual_df=sub_ann,
            comparison_id=comp_id,
            label=label,
            baseline_years=base_yrs,
            target_year=target_year,
            weighting=weighting,
            months_included=keep_months,
            note=note,
        )

    out: Dict[str, Dict[str, object]] = {"strict_all_years_unflagged": {}, "excluding_target_flagged_months": {}}
    configs = [
        ("primary_2015_2019", "Primary baseline (2015–2019)", primary_years),
        ("sensitivity_2019_2021", "Sensitivity baseline (2019–2021)", sensitivity_years),
    ]

    for key, base_label, yrs in configs:
        all_yrs = list(yrs) + [target_year]
        strict_months = [
            int(m)
            for m in months
            if all(
                not m_df[(m_df["year"] == y) & (m_df["mnum"] == m)].empty
                and bool(m_df[(m_df["year"] == y) & (m_df["mnum"] == m)].iloc[0]["passes_cov"])
                for y in all_yrs
            )
        ]
        target_ok_months = [
            int(m)
            for m in months
            if not m_df[(m_df["year"] == target_year) & (m_df["mnum"] == m)].empty
            and bool(m_df[(m_df["year"] == target_year) & (m_df["mnum"] == m)].iloc[0]["passes_cov"])
        ]

        for weighting in ("valid_day_annual_equal_weight", "equal_month_annual_equal_weight"):
            w_tag = "valid_day" if weighting == "valid_day_annual_equal_weight" else "equal_month"
            out["strict_all_years_unflagged"][f"{key}_{w_tag}"] = _run_subset(
                comp_id=f"strict_unflagged_{key}_{w_tag}",
                label=f"{base_label} — identical months >=50% in every year",
                base_yrs=yrs,
                keep_months=strict_months,
                weighting=weighting,
                note=(
                    "Retains only calendar months passing >=50% coverage in every year of the comparison window "
                    f"(remaining months: {[MONTH_NAMES[m] for m in strict_months]})."
                ),
            )
            out["excluding_target_flagged_months"][f"{key}_{w_tag}"] = _run_subset(
                comp_id=f"excl_2022_flagged_{key}_{w_tag}",
                label=f"{base_label} — identical months excluding 2022-flagged month(s)",
                base_yrs=yrs,
                keep_months=target_ok_months,
                weighting=weighting,
                note=(
                    "Drops calendar months flagged <50% in 2022 (April 2022: 8/30d) identically from both baseline and 2022 "
                    f"(remaining months: {[MONTH_NAMES[m] for m in target_ok_months]})."
                ),
            )
    return out


def _seasonal_theil_sen_slope(monthly_sub: pd.DataFrame) -> Optional[float]:
    """Median within-calendar-month pairwise slope across years (molecules/cm^2/year)."""
    work = monthly_sub if "year" in monthly_sub.columns else monthly_sub.assign(year=monthly_sub["month"].str[:4].astype(int))
    slopes: List[float] = []
    for _, grp in work.groupby("mnum"):
        valid = grp.dropna(subset=["no2_mean_molec_cm2"]).sort_values("year")
        yrs = valid["year"].to_numpy(dtype=float)
        vals = valid["no2_mean_molec_cm2"].to_numpy(dtype=float)
        n = len(vals)
        for i in range(n - 1):
            for j in range(i + 1, n):
                dt = yrs[j] - yrs[i]
                if dt > 0:
                    slopes.append((vals[j] - vals[i]) / dt)
    return _clean_float(np.median(slopes)) if slopes else None


def _hamed_rao_on_anomalies(anom_series: np.ndarray) -> Optional[Dict[str, object]]:
    """Autocorrelation-adjusted Hamed & Rao (1998) modified Mann-Kendall test on deseasonalized monthly values."""
    y = np.asarray(anom_series, dtype=float)
    y = y[np.isfinite(y)]
    n = len(y)
    if n < 12:
        return None

    slopes: List[float] = []
    S = 0.0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = y[j] - y[i]
            if diff > 0:
                S += 1.0
            elif diff < 0:
                S -= 1.0
            slopes.append(diff / float(j - i))
    if not slopes:
        return None

    ts_slope_mo = float(np.median(slopes))
    detrended = y - ts_slope_mo * np.arange(n, dtype=float)
    if np.allclose(detrended, detrended[0]):
        return None

    ranks = rankdata(detrended)
    r_centered = ranks - (n + 1.0) / 2.0
    denom = float(np.sum(r_centered ** 2))
    if denom <= 0.0:
        return None

    bartlett_crit = norm.ppf(0.975) / math.sqrt(float(n))
    ess_sum = 0.0
    sig_lags: List[Dict[str, float]] = []
    for k in range(1, max(1, n - 3)):
        rho_k = float(np.sum(r_centered[:-k] * r_centered[k:])) / denom
        if abs(rho_k) > bartlett_crit:
            sig_lags.append({"lag_months": int(k), "rank_autocorr": round(rho_k, 4)})
            ess_sum += float(n - k) * float(n - k - 1) * float(n - k - 2) * rho_k

    vif = max(1.0, 1.0 + (2.0 / (float(n) * float(n - 1) * float(n - 2))) * ess_sum)
    var_s = float(n) * float(n - 1) * float(2 * n + 5) / 18.0
    var_mod = var_s * vif
    if var_mod <= 0.0:
        return None

    z_raw = (S - float(np.sign(S))) / math.sqrt(var_s) if S != 0.0 else 0.0
    z_hr = (S - float(np.sign(S))) / math.sqrt(var_mod) if S != 0.0 else 0.0
    return {
        "n_months": int(n),
        "mann_kendall_S": int(S),
        "variance_inflation_factor": round(vif, 4),
        "significant_rank_lags": sig_lags,
        "z_unadjusted": round(z_raw, 4),
        "p_value_unadjusted": round(float(2.0 * norm.sf(abs(z_raw))), 6),
        "z_hamed_rao": round(z_hr, 4),
        "p_value_hamed_rao": round(float(2.0 * norm.sf(abs(z_hr))), 6),
    }


def _evaluate_trend_window(sub_df: pd.DataFrame, window_id: str, label: str, max_hac_lag: int = 6) -> Dict[str, object]:
    """Estimate seasonality-aware trend + Newey-West HAC uncertainty and Hamed-Rao check, or 'not_assessed'."""
    valid = sub_df.dropna(subset=["no2_mean_molec_cm2"]).sort_values("month").reset_index(drop=True)
    if "year" not in valid.columns:
        valid["year"] = valid["month"].str[:4].astype(int)
    if "mnum" not in valid.columns:
        valid["mnum"] = valid["month"].str[5:].astype(int)
    n = int(len(valid))
    if n < 24:
        return {
            "window_id": window_id,
            "label": label,
            "status": "not_assessed",
            "n_months": n,
            "reason": f"Insufficient monthly sample size ({n} < 24 months minimum for seasonality-aware trend inference).",
            "slope_molec_cm2_per_year": None,
            "ci_95_lower_molec_cm2_per_year": None,
            "ci_95_upper_molec_cm2_per_year": None,
            "p_value": None,
        }

    month_counts = valid.groupby("mnum")["no2_mean_molec_cm2"].size()
    if len(month_counts) < 12 or int(month_counts.min()) < 2:
        return {
            "window_id": window_id,
            "label": label,
            "status": "not_assessed",
            "n_months": n,
            "reason": "Requires at least 2 observations in each of all 12 calendar months to fit seasonal fixed effects.",
            "slope_molec_cm2_per_year": None,
            "ci_95_lower_molec_cm2_per_year": None,
            "ci_95_upper_molec_cm2_per_year": None,
            "p_value": None,
        }

    # Month-Fixed-Effects OLS with Newey-West HAC standard errors (lag <= 6 months)
    t_yr = (
        (pd.to_datetime(valid["month"] + "-01") - pd.to_datetime(valid["month"].iloc[0] + "-01")).dt.days.to_numpy(dtype=float)
        / 365.25
    )
    dummies = pd.get_dummies(valid["mnum"], dtype=float).to_numpy()
    X = np.column_stack([t_yr, dummies])
    y = valid["no2_mean_molec_cm2"].to_numpy(dtype=float)

    if float(np.ptp(y)) <= 1e-12 * max(1.0, float(np.max(np.abs(y)))):
        return {
            "window_id": window_id,
            "label": label,
            "status": "not_assessed",
            "n_months": n,
            "reason": "Series has zero variance across months.",
            "slope_molec_cm2_per_year": None,
            "ci_95_lower_molec_cm2_per_year": None,
            "ci_95_upper_molec_cm2_per_year": None,
            "p_value": None,
        }

    df_resid = n - int(X.shape[1])
    if df_resid < 10 or np.linalg.matrix_rank(X) < X.shape[1]:
        return {
            "window_id": window_id,
            "label": label,
            "status": "not_assessed",
            "n_months": n,
            "reason": "Design matrix is rank-deficient or residual degrees of freedom < 10.",
            "slope_molec_cm2_per_year": None,
            "ci_95_lower_molec_cm2_per_year": None,
            "ci_95_upper_molec_cm2_per_year": None,
            "p_value": None,
        }

    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    scores = X * resid[:, None]
    Omega = scores.T @ scores
    lag_limit = min(max_hac_lag, max(1, n // 4))
    for lag in range(1, lag_limit + 1):
        weight = 1.0 - float(lag) / float(lag_limit + 1)
        cross = scores[lag:].T @ scores[:-lag]
        Omega = Omega + weight * (cross + cross.T)

    V_hac = (float(n) / float(df_resid)) * (XtX_inv @ Omega @ XtX_inv)
    var_slope = _clean_float(V_hac[0, 0])
    slope = _clean_float(beta[0])
    if var_slope is None or var_slope <= 1e-24 * max(1.0, float(np.var(y))) or slope is None:
        return {
            "window_id": window_id,
            "label": label,
            "status": "not_assessed",
            "n_months": n,
            "reason": "HAC variance estimate was zero or non-positive.",
            "slope_molec_cm2_per_year": None,
            "ci_95_lower_molec_cm2_per_year": None,
            "ci_95_upper_molec_cm2_per_year": None,
            "p_value": None,
        }

    se_hac = math.sqrt(var_slope)
    t_stat = slope / se_hac
    p_val = float(2.0 * student_t.sf(abs(t_stat), df=df_resid))
    t_crit = float(student_t.ppf(0.975, df=df_resid))
    ci_lo = slope - t_crit * se_hac
    ci_hi = slope + t_crit * se_hac

    resid_lag1 = _clean_float(np.corrcoef(resid[:-1], resid[1:])[0, 1], 4) if n >= 3 and np.std(resid) > 0 else None

    # Nonparametric check on month-centered anomalies & within-month Seasonal Theil-Sen
    month_means = valid.groupby("mnum")["no2_mean_molec_cm2"].transform("mean")
    anomalies = (valid["no2_mean_molec_cm2"] - month_means).to_numpy(dtype=float)
    seasonal_ts = _seasonal_theil_sen_slope(valid)
    hr_mk = _hamed_rao_on_anomalies(anomalies)

    return {
        "window_id": window_id,
        "label": label,
        "status": "assessed",
        "start_month": str(valid["month"].iloc[0]),
        "end_month": str(valid["month"].iloc[-1]),
        "n_months": n,
        "degrees_of_freedom": int(df_resid),
        "primary_method": "Month-Fixed-Effects OLS with Newey-West HAC standard errors",
        "hac_max_lag_months": int(lag_limit),
        "slope_molec_cm2_per_year": slope,
        "slope_molec_cm2_per_decade": slope * 10.0,
        "hac_se_molec_cm2_per_year": se_hac,
        "ci_95_lower_molec_cm2_per_year": ci_lo,
        "ci_95_upper_molec_cm2_per_year": ci_hi,
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_val, 6),
        "significant_at_alpha_0_05": bool(p_val < 0.05),
        "residual_lag1_autocorrelation": resid_lag1,
        "nonparametric_sensitivity": {
            "method": "Within-month Seasonal Theil-Sen + Hamed-Rao (1998) modified Mann-Kendall on deseasonalized monthly anomalies",
            "seasonal_theil_sen_molec_cm2_per_year": seasonal_ts,
            "seasonal_theil_sen_molec_cm2_per_decade": (seasonal_ts * 10.0) if seasonal_ts is not None else None,
            "hamed_rao_mk": hr_mk,
        },
        "assumptions_and_caveats": [
            "Treats missing-day-adjusted monthly means as equal-precision observations despite varying monthly coverage (some <50%).",
            "Accounts for annual cycle via 12 monthly fixed intercepts and short-range serial correlation via Newey-West HAC (lags <= 6 months).",
            "A monotonic linear rate over 2015–2022 blends pre-war variability, 2020 COVID-19 changes, and post-February 2022 disruption and should not be mistaken for a step-change war effect.",
        ],
    }


def assess_statistics(daily_full: pd.DataFrame, monthly_df: pd.DataFrame) -> Dict[str, object]:
    """Assess daily serial dependence, before/after inference validity, and seasonality-aware monthly trends."""
    d = daily_full.copy()
    d["mnum"] = d["date"].dt.month
    d["anom"] = d["value"] - d["mnum"].map(d.loc[d["status"] == "valid"].groupby("mnum")["value"].mean())

    daily_lag_diag: Dict[str, object] = {}
    for lag in (1, 2, 3, 7):
        s0 = d["anom"]
        s1 = d["anom"].shift(lag)
        mask = s0.notna() & s1.notna()
        n_pairs = int(mask.sum())
        if n_pairs >= 10 and np.std(s0[mask]) > 0 and np.std(s1[mask]) > 0:
            r_val = _clean_float(np.corrcoef(s0[mask], s1[mask])[0, 1], 4)
        else:
            r_val = None
        daily_lag_diag[f"lag_{lag}d"] = {"autocorr_r": r_val, "valid_pairs": n_pairs}

    m = monthly_df.copy()
    m["year"] = m["month"].str[:4].astype(int)
    m["mnum"] = m["month"].str[5:].astype(int)

    pre_war_sub = m[m["month"] <= "2022-02"].copy()
    full_sub = m.copy()

    return {
        "before_after_seasonal_inference": {
            "status": "not_assessed",
            "p_value": None,
            "ci_95_lower_molec_cm2": None,
            "ci_95_upper_molec_cm2": None,
            "statistical_significance_claimed": False,
            "reasons_not_assessed": [
                "Only n = 1 post-invasion March–August season (2022) exists, which cannot support variance estimation or a hypothesis test for a war-period effect.",
                "Daily retrievals exhibit positive serial correlation (see daily_autocorrelation_diagnostics), so ordinary independent-observation tests on correlated daily rows would understate standard errors.",
                "April 2022 has low coverage (8/30 valid days, 26.67%), introducing potential clear-sky sampling bias.",
                "No matched reference/comparator region series or meteorological covariates (wind speed, mixing height, cloud bias) are included in this single-region export.",
            ],
        },
        "multi_year_seasonality_aware_trend": {
            "pre_invasion": _evaluate_trend_window(
                pre_war_sub,
                window_id="pre_invasion_2015_03_to_2022_02",
                label="Pre-invasion baseline period (March 2015 – February 2022)",
            ),
            "full_record": _evaluate_trend_window(
                full_sub,
                window_id="full_record_2015_03_to_2022_08",
                label="Full study record (March 2015 – August 2022)",
            ),
        },
        "daily_autocorrelation_diagnostics": {
            "note": "Daily deviations from monthly climatological means remain positively autocorrelated across adjacent days; ordinary i.i.d. tests on daily rows are intentionally omitted.",
            "lags": daily_lag_diag,
        },
    }


def plot_seasonal_comparison(
    annual_df: pd.DataFrame,
    comparisons: Dict[str, object],
    exclusion_sens: Dict[str, object],
    meta: Dict[str, object],
    output_path: Path,
) -> Path:
    """Plot March–August 2022 against 2015–2019 primary and 2019–2021 sensitivity baselines plus sensitivity summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ann = annual_df.sort_values("year").reset_index(drop=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 6.8), gridspec_kw={"width_ratios": [1.18, 1.05]})
    fig.patch.set_facecolor("white")

    # Left panel: year-by-year March-August means (valid-day weighted + equal-month overlay)
    yrs = ann["year"].to_numpy()
    vd_e15 = np.array([v / 1e15 if v is not None else np.nan for v in ann["valid_day_mean_molec_cm2"]], dtype=float)
    em_e15 = np.array([v / 1e15 if v is not None else np.nan for v in ann["equal_month_mean_molec_cm2"]], dtype=float)

    colors = []
    for y in yrs:
        if y in PRIMARY_BASELINE_YEARS:
            colors.append("#5499C7")
        elif y == 2020 or y == 2021:
            colors.append("#45B39D")
        elif y == 2022:
            colors.append("#C0392B")
        else:
            colors.append("#85929E")

    bars = ax1.bar(yrs, vd_e15, width=0.62, color=colors, alpha=0.88, edgecolor="#2C3E50", linewidth=0.6, zorder=2, label="Annual Mar–Aug mean (valid-day weighted)")
    ax1.scatter(yrs, em_e15, color="white", edgecolor="#1B2631", marker="s", s=38, linewidth=1.3, zorder=4, label="Equal-month-weighted check")

    # Overlay primary & sensitivity baseline horizontal spans/lines
    p_comp = comparisons["primary_2015_2019_valid_day"]
    s_comp = comparisons["sensitivity_2019_2021_valid_day"]
    if p_comp["baseline_mean_molec_cm2"] is not None:
        p_mean = p_comp["baseline_mean_molec_cm2"] / 1e15
        p_min = p_comp["baseline_annual_min_molec_cm2"] / 1e15
        p_max = p_comp["baseline_annual_max_molec_cm2"] / 1e15
        ax1.axhspan(p_min, p_max, color="#D6EAF8", alpha=0.45, zorder=1, label="2015–2019 annual min–max range (variability, not CI)")
        ax1.axhline(p_mean, color="#1F618D", linestyle="--", linewidth=1.6, zorder=3, label=f"Primary 2015–2019 mean ({p_mean:.2f})")
    if s_comp["baseline_mean_molec_cm2"] is not None:
        s_mean = s_comp["baseline_mean_molec_cm2"] / 1e15
        ax1.axhline(s_mean, color="#117864", linestyle=":", linewidth=1.8, zorder=3, label=f"Sensitivity 2019–2021 mean ({s_mean:.2f})")

    for bar, em_val, r in zip(bars, em_e15, ann.itertuples(index=False)):
        val = bar.get_height()
        if np.isfinite(val):
            top_y = max(val, em_val if np.isfinite(em_val) else val)
            cov_pct = r.coverage_fraction * 100.0
            tag = f"{val:.2f}\n({cov_pct:.0f}%)"
            if r.any_flagged_month:
                tag += "*"
            ax1.text(bar.get_x() + bar.get_width() / 2.0, top_y + 0.08, tag, ha="center", va="bottom", fontsize=7.5, color="#2C3E50", fontweight="bold" if r.year == 2022 else "normal")

    ax1.set_xticks(yrs)
    ax1.set_xticklabels([str(y) for y in yrs], fontsize=9)
    ymax_bars = float(np.nanmax([np.nanmax(vd_e15), np.nanmax(em_e15)])) if (np.any(np.isfinite(vd_e15)) or np.any(np.isfinite(em_e15))) else 3.0
    ax1.set_ylim(0, max(3.6, ymax_bars * 1.42))
    ax1.set_ylabel("March–August Mean NO₂ (10¹⁵ molecules/cm²)", fontsize=9.8)
    ax1.set_title("A. Yearly March–August Mean & Both Baselines", fontsize=11.0, fontweight="bold", pad=10)
    ax1.legend(loc="upper right", frameon=True, facecolor="white", fontsize=7.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", linestyle=":", alpha=0.5, color="#B2BABB")

    def _fmt_months(m_list: Sequence[int]) -> str:
        return ",".join(MONTH_NAMES.get(int(m), str(m)) for m in m_list) if m_list else "none"

    ex_t_p = exclusion_sens["excluding_target_flagged_months"]["primary_2015_2019_valid_day"]
    ex_s_p = exclusion_sens["strict_all_years_unflagged"]["primary_2015_2019_valid_day"]
    ex_t_s = exclusion_sens["excluding_target_flagged_months"]["sensitivity_2019_2021_valid_day"]
    ex_s_s = exclusion_sens["strict_all_years_unflagged"]["sensitivity_2019_2021_valid_day"]

    # Right panel: Sensitivity of 2022 % difference across baseline, weighting, and coverage exclusion
    sens_items = [
        ("Primary (2015–2019)\nValid-day weighted", comparisons["primary_2015_2019_valid_day"]["pct_change"], "#1F618D"),
        ("Primary (2015–2019)\nEqual-month weighted", comparisons["primary_2015_2019_equal_month"]["pct_change"], "#2E86C1"),
        (f"Primary (2015–2019)\nExcl. 2022-flagged ({_fmt_months(ex_t_p['months_included'])})", ex_t_p["pct_change"], "#5DADE2"),
        (f"Primary (2015–2019)\nStrict >=50% all ({_fmt_months(ex_s_p['months_included'])})", ex_s_p["pct_change"], "#21618C"),
        ("Sensitivity (2019–2021)\nValid-day weighted", comparisons["sensitivity_2019_2021_valid_day"]["pct_change"], "#117864"),
        ("Sensitivity (2019–2021)\nEqual-month weighted", comparisons["sensitivity_2019_2021_equal_month"]["pct_change"], "#17A589"),
        (f"Sensitivity (2019–2021)\nExcl. 2022-flagged ({_fmt_months(ex_t_s['months_included'])})", ex_t_s["pct_change"], "#48C9B0"),
        (f"Sensitivity (2019–2021)\nStrict >=50% all ({_fmt_months(ex_s_s['months_included'])})", ex_s_s["pct_change"], "#0E6251"),
    ]
    y_pos = np.arange(len(sens_items))[::-1]
    pcts = [item[1] if item[1] is not None else 0.0 for item in sens_items]
    lbls = [item[0] for item in sens_items]
    s_colors = [item[2] for item in sens_items]

    ax2.barh(y_pos, pcts, height=0.58, color=s_colors, alpha=0.90, edgecolor="#1B2631", linewidth=0.5)
    ax2.axvline(0.0, color="#2C3E50", linewidth=1.0)
    min_pct = min([p for p in pcts] + [-38.0])
    max_pct = max([p for p in pcts] + [4.0])
    ax2.set_xlim(min_pct - 10.5, max_pct + (8.0 if max_pct > 4.0 else 1.5))
    for y_i, (_, p_val, _) in zip(y_pos, sens_items):
        if p_val is not None:
            ha_dir = "right" if p_val <= 0 else "left"
            x_off = p_val - 0.8 if p_val <= 0 else p_val + 0.8
            ax2.text(x_off, y_i, f"{p_val:+.2f}%", ha=ha_dir, va="center", fontsize=8.3, fontweight="bold", color="#1B2631")
        else:
            ax2.text(-1.0, y_i, "Withheld", ha="right", va="center", fontsize=8.0, color="#7F8C8D")

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(lbls, fontsize=8.1)
    ax2.set_xlabel("March–August 2022 % Change vs. Baseline (descriptive; no CI)", fontsize=9.2)
    ax2.set_title("B. Sensitivity to Baseline, Weighting & Coverage", fontsize=11.0, fontweight="bold", pad=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="x", linestyle=":", alpha=0.5, color="#B2BABB")

    bbox = meta.get("user_bounding_box") or {}
    bbox_txt = (
        f"({bbox['west']:.3f}°E–{bbox['east']:.3f}°E, {bbox['south']:.2f}°N–{bbox['north']:.2f}°N)"
        if bbox
        else "Kyiv box"
    )
    fig.suptitle(
        f"Kyiv March–August Tropospheric NO₂ Comparison & Methodological Sensitivity — OMNO2d v004 {bbox_txt}",
        fontsize=12.2,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.015,
        0.012,
        (
            "Source: NASA Giovanni OMNO2d v004 (30% Cloud Screened) | Dates: March–August 2015–2022 | * Year contains ≥1 month flagged <50% coverage (project rule).\n"
            "Note: Shaded band shows historical year-to-year min–max variability, not a confidence interval. "
            "Statistical significance of the n=1 2022 shift is NOT assessed; no control region or weather adjustment included."
        ),
        fontsize=7.5,
        color="#566573",
        linespacing=1.35,
    )
    plt.tight_layout(rect=[0, 0.065, 1, 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_matched_months(
    matched_months: List[Dict[str, object]],
    meta: Dict[str, object],
    output_path: Path,
) -> Path:
    """Plot matched March–August calendar-month comparisons with visibly flagged low-coverage months."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(matched_months))
    names = [m["month_name"] for m in matched_months]

    p_mean = np.array([(m["primary_2015_2019"]["mean_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    p_min = np.array([(m["primary_2015_2019"]["min_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    p_max = np.array([(m["primary_2015_2019"]["max_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    s_mean = np.array([(m["sensitivity_2019_2021"]["mean_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    y21 = np.array([(m["year_2021_mean_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    v22 = np.array([(m["target_2022"]["mean_molec_cm2"] or np.nan) / 1e15 for m in matched_months])
    flagged22 = np.array([bool(m["target_2022"]["flagged_below_50_pct"]) for m in matched_months])
    cov22_pct = np.array([(m["target_2022"]["coverage_fraction"] or 0.0) * 100.0 for m in matched_months])
    cov_p_pct = np.array([(m["primary_2015_2019"]["mean_coverage_fraction"] or 0.0) * 100.0 for m in matched_months])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.2, 7.8), sharex=True, gridspec_kw={"height_ratios": [1.85, 0.95]})
    fig.patch.set_facecolor("white")

    ax1.fill_between(x, p_min, p_max, color="#D5DBDB", alpha=0.55, label="2015–2019 historical min–max range (variability, not CI)")
    ax1.plot(x, p_mean, color="#1F618D", marker="o", linewidth=2.0, markersize=6, label="Primary baseline (2015–2019 mean)")
    ax1.plot(x, s_mean, color="#117864", linestyle="--", marker="^", linewidth=1.8, markersize=5.5, label="Sensitivity baseline (2019–2021 mean)")
    ax1.plot(x, y21, color="#7F8C8D", linestyle=":", marker=".", linewidth=1.3, markersize=6, label="2021 pre-invasion context")
    ax1.plot(x, v22, color="#C0392B", linewidth=2.2, zorder=4)

    ok_idx = x[~flagged22]
    fl_idx = x[flagged22]
    if len(ok_idx) > 0:
        ax1.scatter(ok_idx, v22[~flagged22], color="#C0392B", s=58, zorder=5, label="2022 (≥50% monthly coverage)")
    if len(fl_idx) > 0:
        ax1.scatter(fl_idx, v22[flagged22], facecolor="white", edgecolor="#D35400", linewidth=2.2, marker="D", s=82, zorder=6, label="2022 Flagged <50% coverage (project rule)")

    # Annotate % change vs 2015-2019 and highlight April 2022 sparse sampling explicitly
    for idx_i, m in enumerate(matched_months):
        val = v22[idx_i]
        pct_p = m["vs_primary_2015_2019"]["pct_change"]
        if np.isfinite(val) and pct_p is not None:
            if m["target_2022"]["flagged_below_50_pct"]:
                vd = m["target_2022"]["valid_days"]
                cd = m["target_2022"]["calendar_days"]
                ax1.annotate(
                    f"2022: {pct_p:+.1f}%\n({vd}/{cd}d <50% flag)",
                    xy=(idx_i, val),
                    xytext=(idx_i + 0.16, val - 0.55),
                    ha="left",
                    va="top",
                    fontsize=7.8,
                    fontweight="bold",
                    color="#A04000",
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#E67E22", linewidth=0.9),
                    arrowprops=dict(arrowstyle="->", color="#D35400", linewidth=1.0),
                )
            else:
                offset_y = -0.22 if idx_i in (4, 5) else -0.20
                ax1.text(idx_i, val + offset_y, f"{pct_p:+.1f}%", ha="center", va="top", fontsize=8.0, fontweight="bold", color="#922B21")

    ymax = max(3.5, float(np.nanmax([np.nanmax(p_max), np.nanmax(v22)]) * 1.12))
    ax1.set_ylim(0, ymax)
    ax1.set_ylabel("Monthly Mean NO₂ (10¹⁵ molecules/cm²)", fontsize=10)
    ax1.legend(loc="upper right", ncol=2, frameon=True, facecolor="white", fontsize=8.0)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", linestyle=":", alpha=0.5, color="#B2BABB")

    # Bottom panel: 2022 coverage vs 2015-2019 average coverage with 50% flag threshold
    w = 0.34
    b1 = ax2.bar(x - w / 2, cov_p_pct, width=w, color="#85C1E9", edgecolor="#2E86C1", linewidth=0.6, label="2015–2019 mean monthly coverage")
    c22_colors = ["#E67E22" if fl else "#C0392B" for fl in flagged22]
    b2 = ax2.bar(x + w / 2, cov22_pct, width=w, color=c22_colors, alpha=0.88, edgecolor="#641E16", linewidth=0.6, label="2022 monthly coverage (orange if <50%)")
    ax2.axhline(50.0, color="#D35400", linestyle=":", linewidth=1.4, label="Proposed project coverage flag (50%)")

    for idx_i, (bar_p, bar_22, m) in enumerate(zip(b1, b2, matched_months)):
        vd22 = m["target_2022"]["valid_days"]
        cd22 = m["target_2022"]["calendar_days"]
        ax2.text(bar_22.get_x() + bar_22.get_width() / 2.0, bar_22.get_height() + 2.2, f"{vd22}/{cd22}d", ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#A04000" if flagged22[idx_i] else "#641E16")
        f_cnt = m["primary_2015_2019"]["flagged_years_count"]
        if f_cnt > 0:
            ax2.text(bar_p.get_x() + bar_p.get_width() / 2.0, bar_p.get_height() + 2.2, f"{f_cnt}/5 yr\n<50%", ha="center", va="bottom", fontsize=7.0, color="#1F618D")

    ax2.set_xticks(x)
    ax2.set_xticklabels(names, fontsize=10, fontweight="bold")
    ax2.set_ylabel("Coverage (% days/mo)", fontsize=9.6)
    ax2.set_ylim(0, 118)
    ax2.legend(loc="upper center", ncol=3, frameon=True, facecolor="white", fontsize=8.0)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", linestyle=":", alpha=0.5, color="#B2BABB")

    bbox = meta.get("user_bounding_box") or {}
    bbox_txt = (
        f"({bbox['west']:.3f}°E–{bbox['east']:.3f}°E, {bbox['south']:.2f}°N–{bbox['north']:.2f}°N)"
        if bbox
        else "Kyiv box"
    )
    flagged_notes = [
        f"{m['month_name']} 2022 ({m['target_2022']['valid_days']}/{m['target_2022']['calendar_days']}d, "
        f"{(m['target_2022']['coverage_fraction'] or 0.0) * 100.0:.1f}%)"
        for m in matched_months
        if m["target_2022"]["flagged_below_50_pct"]
    ]
    flagged_str = ", ".join(flagged_notes) if flagged_notes else "none"

    fig.suptitle(
        f"Matched Calendar-Month NO₂ Comparison (March–August: 2022 vs. Baselines)\nKyiv OMNO2d v004 {bbox_txt}",
        fontsize=11.4,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.015,
        0.012,
        (
            "Source: NASA Giovanni OMNO2d v004 (30% Cloud Screened) | Top labels show 2022 % difference vs. 2015–2019 baseline; bottom counts show 2022 valid/calendar days.\n"
            f"Note: Gray band shows historical 2015–2019 min–max range (not a confidence interval). "
            f"2022 months <50% coverage (project rule): {flagged_str}."
        ),
        fontsize=7.4,
        color="#566573",
        linespacing=1.35,
    )
    plt.tight_layout(rect=[0, 0.065, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _export_reusable_chart_csvs(
    annual_df: pd.DataFrame,
    comparisons: Dict[str, object],
    exclusion_sens: Dict[str, object],
    matched_months: List[Dict[str, object]],
    seasonal_csv_path: Path,
    matched_csv_path: Path,
) -> None:
    """Write flat CSV tables powering Figures 2 and 3 for external charting/review."""
    comp_rows = [
        comparisons["primary_2015_2019_valid_day"],
        comparisons["primary_2015_2019_equal_month"],
        comparisons["sensitivity_2019_2021_valid_day"],
        comparisons["sensitivity_2019_2021_equal_month"],
        exclusion_sens["excluding_target_flagged_months"]["primary_2015_2019_valid_day"],
        exclusion_sens["excluding_target_flagged_months"]["primary_2015_2019_equal_month"],
        exclusion_sens["excluding_target_flagged_months"]["sensitivity_2019_2021_valid_day"],
        exclusion_sens["excluding_target_flagged_months"]["sensitivity_2019_2021_equal_month"],
        exclusion_sens["strict_all_years_unflagged"]["primary_2015_2019_valid_day"],
        exclusion_sens["strict_all_years_unflagged"]["primary_2015_2019_equal_month"],
        exclusion_sens["strict_all_years_unflagged"]["sensitivity_2019_2021_valid_day"],
        exclusion_sens["strict_all_years_unflagged"]["sensitivity_2019_2021_equal_month"],
    ]
    flat_comp = [
        {
            "comparison_id": c["comparison_id"],
            "label": c["label"],
            "weighting": c["weighting"],
            "baseline_years": "-".join(str(y) for y in c["baseline_years_requested"]),
            "available_baseline_years": ",".join(str(y) for y in c["available_baseline_years"]),
            "target_year": c["target_year"],
            "months_included": ",".join(str(m) for m in c["months_included"]),
            "baseline_mean_molec_cm2": c["baseline_mean_molec_cm2"],
            "target_mean_molec_cm2": c["target_mean_molec_cm2"],
            "absolute_change_molec_cm2": c["absolute_change_molec_cm2"],
            "pct_change": c["pct_change"],
            "pct_change_status": c["pct_change_status"],
            "baseline_valid_days": c["baseline_valid_days"],
            "baseline_calendar_days": c["baseline_calendar_days"],
            "target_valid_days": c["target_valid_days"],
            "target_calendar_days": c["target_calendar_days"],
            "any_flagged_month": c["any_flagged_month"],
        }
        for c in comp_rows
    ]
    seasonal_csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flat_comp).to_csv(seasonal_csv_path, index=False)

    flat_matched = [
        {
            "calendar_month": m["calendar_month"],
            "month_name": m["month_name"],
            "primary_2015_2019_mean_molec_cm2": m["primary_2015_2019"]["mean_molec_cm2"],
            "primary_2015_2019_min_molec_cm2": m["primary_2015_2019"]["min_molec_cm2"],
            "primary_2015_2019_max_molec_cm2": m["primary_2015_2019"]["max_molec_cm2"],
            "primary_2015_2019_mean_coverage": m["primary_2015_2019"]["mean_coverage_fraction"],
            "primary_2015_2019_flagged_years": m["primary_2015_2019"]["flagged_years_count"],
            "sensitivity_2019_2021_mean_molec_cm2": m["sensitivity_2019_2021"]["mean_molec_cm2"],
            "sensitivity_2019_2021_mean_coverage": m["sensitivity_2019_2021"]["mean_coverage_fraction"],
            "sensitivity_2019_2021_flagged_years": m["sensitivity_2019_2021"]["flagged_years_count"],
            "year_2021_mean_molec_cm2": m["year_2021_mean_molec_cm2"],
            "target_2022_mean_molec_cm2": m["target_2022"]["mean_molec_cm2"],
            "target_2022_valid_days": m["target_2022"]["valid_days"],
            "target_2022_calendar_days": m["target_2022"]["calendar_days"],
            "target_2022_coverage_fraction": m["target_2022"]["coverage_fraction"],
            "target_2022_flagged_below_50_pct": m["target_2022"]["flagged_below_50_pct"],
            "abs_change_vs_2015_2019": m["vs_primary_2015_2019"]["absolute_change_molec_cm2"],
            "pct_change_vs_2015_2019": m["vs_primary_2015_2019"]["pct_change"],
            "abs_change_vs_2019_2021": m["vs_sensitivity_2019_2021"]["absolute_change_molec_cm2"],
            "pct_change_vs_2019_2021": m["vs_sensitivity_2019_2021"]["pct_change"],
        }
        for m in matched_months
    ]
    matched_csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flat_matched).to_csv(matched_csv_path, index=False)


def run_air_analysis(
    input_csv: Path,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    region_id: str = DEFAULT_REGION_ID,
    region_name: str = DEFAULT_REGION_NAME,
    sparse_min_valid_days: int = DEFAULT_SPARSE_MIN_VALID_DAYS,
    low_coverage_threshold: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> Dict[str, object]:
    """Run complete Air/NO2 pipeline, baseline comparisons, sensitivity checks, statistics, plots, and backend JSON export."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    monthly_csv_path = reports_dir / "no2_monthly.csv"
    monthly_png_path = reports_dir / "no2_monthly.png"
    quality_json_path = reports_dir / "data_quality.json"
    seasonal_png_path = reports_dir / "no2_seasonal_comparison.png"
    matched_png_path = reports_dir / "no2_matched_months.png"
    seasonal_csv_path = reports_dir / "no2_seasonal_comparisons.csv"
    matched_csv_path = reports_dir / "no2_matched_months.csv"
    air_json_path = reports_dir / "air_no2_results.json"

    quality_report = run_pipeline(
        input_csv=input_csv,
        output_csv=monthly_csv_path,
        output_chart=monthly_png_path,
        output_quality=quality_json_path,
        sparse_min_valid_days=sparse_min_valid_days,
        low_coverage_fraction=low_coverage_threshold,
    )

    daily_raw, meta = parse_giovanni_csv(input_csv)
    daily_full, daily_counts = reindex_daily_calendar(daily_raw, meta)
    monthly_df, monthly_qc = aggregate_monthly(
        daily_full,
        sparse_min_valid_days=sparse_min_valid_days,
        low_coverage_fraction=low_coverage_threshold,
    )

    annual_df = compute_annual_seasonal_series(
        daily_full=daily_full,
        monthly_df=monthly_df,
        months=MARCH_AUGUST_MONTHS,
        low_coverage_threshold=low_coverage_threshold,
    )

    comparisons = {
        "primary_2015_2019_valid_day": compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="primary_2015_2019_valid_day",
            label="Primary baseline: March–August 2022 vs. 2015–2019 (study-spec valid-day annual equal weight)",
            baseline_years=PRIMARY_BASELINE_YEARS,
            target_year=TARGET_YEAR,
            weighting="valid_day_annual_equal_weight",
            note="Study specification primary method: equal weight across yearly valid-day seasonal means.",
        ),
        "sensitivity_2019_2021_valid_day": compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="sensitivity_2019_2021_valid_day",
            label="Sensitivity baseline: March–August 2022 vs. 2019–2021 (valid-day annual equal weight)",
            baseline_years=SENSITIVITY_BASELINE_YEARS,
            target_year=TARGET_YEAR,
            weighting="valid_day_annual_equal_weight",
            note="Includes 2020 COVID-19 pandemic period and 2021 pre-invasion decline.",
        ),
        "primary_2015_2019_equal_month": compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="primary_2015_2019_equal_month",
            label="Weighting check: March–August 2022 vs. 2015–2019 (equal weight across 6 monthly means)",
            baseline_years=PRIMARY_BASELINE_YEARS,
            target_year=TARGET_YEAR,
            weighting="equal_month_annual_equal_weight",
            note="Gives each calendar month (Mar–Aug) equal 1/6 weight regardless of cloudy-day count.",
        ),
        "sensitivity_2019_2021_equal_month": compute_baseline_comparison(
            annual_df=annual_df,
            comparison_id="sensitivity_2019_2021_equal_month",
            label="Weighting check: March–August 2022 vs. 2019–2021 (equal weight across 6 monthly means)",
            baseline_years=SENSITIVITY_BASELINE_YEARS,
            target_year=TARGET_YEAR,
            weighting="equal_month_annual_equal_weight",
            note="Equal 1/6 monthly weighting sensitivity check over pandemic-era 2019–2021 baseline.",
        ),
    }

    exclusion_sens = compute_coverage_exclusion_sensitivities(
        daily_full=daily_full,
        monthly_df=monthly_df,
        primary_years=PRIMARY_BASELINE_YEARS,
        sensitivity_years=SENSITIVITY_BASELINE_YEARS,
        target_year=TARGET_YEAR,
        months=MARCH_AUGUST_MONTHS,
        low_coverage_threshold=low_coverage_threshold,
    )

    matched_months = compute_matched_month_comparisons(
        monthly_df=monthly_df,
        primary_years=PRIMARY_BASELINE_YEARS,
        sensitivity_years=SENSITIVITY_BASELINE_YEARS,
        target_year=TARGET_YEAR,
        months=MARCH_AUGUST_MONTHS,
        low_coverage_threshold=low_coverage_threshold,
    )

    statistics = assess_statistics(daily_full=daily_full, monthly_df=monthly_df)

    plot_seasonal_comparison(
        annual_df=annual_df,
        comparisons=comparisons,
        exclusion_sens=exclusion_sens,
        meta=meta,
        output_path=seasonal_png_path,
    )
    plot_matched_months(
        matched_months=matched_months,
        meta=meta,
        output_path=matched_png_path,
    )
    _export_reusable_chart_csvs(
        annual_df=annual_df,
        comparisons=comparisons,
        exclusion_sens=exclusion_sens,
        matched_months=matched_months,
        seasonal_csv_path=seasonal_csv_path,
        matched_csv_path=matched_csv_path,
    )

    monthly_records = [
        {
            "month": str(r.month),
            "no2_mean_molec_cm2": _clean_float(r.no2_mean_molec_cm2),
            "valid_days": int(r.valid_days),
            "calendar_days": int(r.calendar_days),
            "coverage_fraction": float(r.coverage_fraction),
            "flagged_below_50_pct": bool((r.valid_days / r.calendar_days) < low_coverage_threshold),
            "flagged_below_10_valid_days": bool(r.valid_days < sparse_min_valid_days),
        }
        for r in monthly_df.itertuples(index=False)
    ]

    annual_records = [
        {
            "year": int(r.year),
            "months_included": list(r.months_included),
            "valid_days": int(r.valid_days),
            "calendar_days": int(r.calendar_days),
            "coverage_fraction": float(r.coverage_fraction),
            "observed_months_count": int(r.observed_months_count),
            "valid_day_mean_molec_cm2": _clean_float(r.valid_day_mean_molec_cm2),
            "equal_month_mean_molec_cm2": _clean_float(r.equal_month_mean_molec_cm2),
            "flagged_months_count": int(r.flagged_months_count),
            "flagged_months": list(r.flagged_months),
            "any_flagged_month": bool(r.any_flagged_month),
        }
        for r in annual_df.itertuples(index=False)
    ]

    air_results = {
        "schema_version": SCHEMA_VERSION,
        "status": {
            "overall": "validated_descriptive_with_limitations",
            "data_cleaning_and_accounting": "validated",
            "baseline_comparison": "validated",
            "before_after_significance": "not_assessed",
            "reference_region_comparison": "not_assessed_missing_comparator_regions",
            "causal_attribution": "not_established",
            "paper_replication_classification": "related_comparison",
        },
        "region": {
            "region_id": region_id,
            "name": region_name,
            "center": DEFAULT_REGION_CENTER,
            "user_bounding_box": meta.get("user_bounding_box"),
            "data_bounding_box": meta.get("data_bounding_box"),
            "spatial_note": (
                "Giovanni reports snapped 0.25-degree grid-center bounds covering peri-urban and urban area; "
                "not directly comparable to 4-km TROPOMI city-center sampling."
            ),
        },
        "dataset": {
            "provider": "NASA Giovanni",
            "instrument": "Aura/OMI",
            "product": meta.get("dataset") or "OMNO2d v004",
            "version": "004",
            "variable": meta.get("variable"),
            "dataset_variable_token": meta.get("dataset_variable_token"),
            "units": meta.get("units") or "molecules/cm^2",
            "measurement_type": "tropospheric_vertical_column_density",
            "cloud_screen_rule": "30% Cloud Screened",
            "spatial_resolution_deg": 0.25,
            "reproducibility_url": meta.get("reproducibility_url"),
            "catalogue_url": "https://disc.gsfc.nasa.gov/datasets/OMNO2d_004/summary",
            "raw_input_file": meta.get("input_file"),
            "raw_input_sha256": meta.get("input_sha256"),
            "raw_input_bytes": meta.get("input_bytes"),
            "header_line_number_1based": meta.get("header_line_number_1based"),
            "declared_fill_value": _clean_float(meta.get("declared_fill_value")),
        },
        "quality_rules": {
            "missing_values_never_zero_filled": True,
            "negative_valid_values_preserved": True,
            "proposed_coverage_flag_rule": f"coverage_fraction < {low_coverage_threshold:.2f} (proposed project rule)",
            "severe_sparsity_reference_rule": f"valid_days < {sparse_min_valid_days}",
            "daily_counts": daily_counts,
            "monthly_summary": monthly_qc,
            "validation_checks": quality_report["validation_checks"],
        },
        "monthly_series": monthly_records,
        "annual_march_august": annual_records,
        "comparisons": comparisons,
        "coverage_sensitivity": exclusion_sens,
        "matched_months": matched_months,
        "statistics": statistics,
        "charts": {
            "monthly_timeline": {
                "png_path": "reports/no2_monthly.png",
                "data_csv_path": "reports/no2_monthly.csv",
                "baseline_displayed": "2015–2019 same-month mean and min–max range (variability, not CI)",
                "coverage_flag_displayed": "<50% monthly coverage (proposed project rule)",
            },
            "seasonal_comparison": {
                "png_path": "reports/no2_seasonal_comparison.png",
                "data_csv_path": "reports/no2_seasonal_comparisons.csv",
                "baselines_displayed": ["2015–2019 (primary)", "2019–2021 (sensitivity)"],
            },
            "matched_months": {
                "png_path": "reports/no2_matched_months.png",
                "data_csv_path": "reports/no2_matched_months.csv",
                "months": ["Mar", "Apr", "May", "Jun", "Jul", "Aug"],
                "flagged_target_months": [m["month_name"] for m in matched_months if m["target_2022"]["flagged_below_50_pct"]],
            },
        },
        "limitations": [
            "Classified as related_comparison to Ialongo et al. (2023) OMI component; coarser 0.25-degree OMNO2d grid and unresolved paper mask/screening details preclude claiming exact replication.",
            "Tropospheric vertical column NO2 (molecules/cm^2) measures lower-atmosphere column density, not surface air-quality concentration or personal exposure.",
            "April 2022 contains only 8 valid observations out of 30 days (26.67% coverage, below the 50% proposed project threshold), requiring explicit coverage sensitivity checks.",
            "Observed March–August NO2 declined prior to February 2022 (notably 2020–2021), so raw 2022 drops cannot be attributed causally to war without comparator cities and weather covariates.",
            "No reference/comparator regions (e.g., Krakow, Prague, or lower-conflict Ukrainian regions) are yet present in this single-region export.",
        ],
        "reproducibility": {
            "regenerate_all_command": "python -m src.air_analysis",
            "test_command": "python -m unittest discover -s tests -v",
            "schema_doc": "docs/air-results-schema.md",
            "findings_doc": "docs/air-findings.md",
        },
    }

    air_json_path.write_text(json.dumps(air_results, indent=2, allow_nan=False, ensure_ascii=False), encoding="utf-8")
    return air_results


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run full Air/NO2 comparison, sensitivity, stats, charts, and backend JSON export.")
    parser.add_argument("--input", type=Path, default=None, help="Path to raw NASA Giovanni CSV")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--region-id", type=str, default=DEFAULT_REGION_ID)
    parser.add_argument("--region-name", type=str, default=DEFAULT_REGION_NAME)
    parser.add_argument("--sparse-days", type=int, default=DEFAULT_SPARSE_MIN_VALID_DAYS)
    parser.add_argument("--low-coverage", type=float, default=DEFAULT_LOW_COVERAGE_FRACTION)
    args = parser.parse_args(list(argv) if argv is not None else None)

    input_path = args.input if args.input is not None else _discover_default_input(DEFAULT_RAW_DIR)
    res = run_air_analysis(
        input_csv=input_path,
        reports_dir=args.reports_dir,
        region_id=args.region_id,
        region_name=args.region_name,
        sparse_min_valid_days=args.sparse_days,
        low_coverage_threshold=args.low_coverage,
    )

    p_c = res["comparisons"]["primary_2015_2019_valid_day"]
    s_c = res["comparisons"]["sensitivity_2019_2021_valid_day"]
    tr_full = res["statistics"]["multi_year_seasonality_aware_trend"]["full_record"]
    print(
        f"Air/NO2 analysis complete ({res['region']['region_id']}, {res['quality_rules']['daily_counts']['start_date']}..{res['quality_rules']['daily_counts']['end_date']}):\n"
        f"  Mar-Aug 2022 vs 2015-2019 (valid-day): {p_c['pct_change']}% ({p_c['baseline_mean_molec_cm2']:.3e} -> {p_c['target_mean_molec_cm2']:.3e})\n"
        f"  Mar-Aug 2022 vs 2019-2021 (valid-day): {s_c['pct_change']}% ({s_c['baseline_mean_molec_cm2']:.3e} -> {s_c['target_mean_molec_cm2']:.3e})\n"
        f"  Before/after statistical test: {res['statistics']['before_after_seasonal_inference']['status']}\n"
        f"  Full-record trend: {tr_full['status']} (slope={tr_full.get('slope_molec_cm2_per_year')}, p={tr_full.get('p_value')})\n"
        f"  Exported JSON, CSVs, and 3 PNGs to {args.reports_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
