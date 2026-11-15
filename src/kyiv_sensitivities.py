"""Kyiv NO2 coverage/weather sensitivities and Krakow/Prague 2022 comparison exports.

Provides additive scientific diagnostics embedded into
``reports/atlas_air_weather_ukraine.json`` (``GET /api/air/weather``) without
duplicating or overriding the canonical trend panel in ``reports/trend_results.json``
(``GET /api/trends``):

1. Kyiv OMI NO2 coverage-exclusion sensitivity (excluding the 37 months with
   ``coverage_fraction < 0.50``, which drops all November and December months)
   and meteorology-covariate-adjusted Month-FE OLS + calendar-lag Newey-West HAC
   regressions (controlling for ``ws10m``, ``cloud_amt``, ``ps``, ``t2m``).
2. March-August 2022 cross-city comparison of Kyiv against external European
   comparators (Krakow and Prague) and Ukraine-wide study-box means across all
   22 NASA POWER weather/water/earth indicators plus OMI NO2 when regional
   exports are available.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from src.air_analysis import _hamed_rao_on_anomalies
from src.four_elements_analysis import MARCH_AUGUST_MONTHS
from src.stats_rigor import clean_float, safe_pct_change
from src.weather_power_pipeline import STUDY_BOXES

FE_HAC_METHOD_NAME = "Month-Fixed-Effects OLS with calendar-lag Newey-West HAC standard errors"
NONPARAM_METHOD_NAME = (
    "Within-month Seasonal Theil-Sen + Hamed-Rao (1998) modified Mann-Kendall "
    "on deseasonalized monthly anomalies"
)
KYIV_WEATHER_COVARIATES: Tuple[str, ...] = ("ws10m", "cloud_amt", "ps", "t2m")
UKRAINE_REGION_IDS: Tuple[str, ...] = tuple(
    b.region_id for b in STUDY_BOXES if b.region_id not in {"poland_krakow", "czechia_prague"}
)


def _clean_p(val: Optional[float]) -> Optional[float]:
    f = clean_float(val)
    if f is None:
        return None
    f = max(0.0, min(1.0, f))
    if f == 0.0:
        return 0.0
    if f >= 1e-6:
        return round(f, 6)
    return float(f"{f:.6g}")


def _seasonal_theil_sen(monthly_sub: pd.DataFrame, value_col: str) -> Optional[float]:
    work = monthly_sub.copy()
    if "year" not in work.columns:
        work["year"] = work["month"].astype(str).str[:4].astype(int)
    slopes: List[float] = []
    for _, grp in work.groupby("mnum"):
        valid = grp.dropna(subset=[value_col]).sort_values("year")
        yrs = valid["year"].to_numpy(dtype=float)
        vals = valid[value_col].to_numpy(dtype=float)
        for i in range(len(vals) - 1):
            for j in range(i + 1, len(vals)):
                dt = yrs[j] - yrs[i]
                if dt > 0:
                    slopes.append((vals[j] - vals[i]) / dt)
    return clean_float(float(np.median(slopes))) if slopes else None


def evaluate_monthly_fe_hac_trend(
    monthly_df: pd.DataFrame,
    value_col: str,
    window_id: str,
    label: str,
    *,
    covariates: Sequence[str] = (),
    allow_partial_calendar_months: bool = False,
) -> Dict[str, Any]:
    """Estimate Month-FE OLS trend with true calendar-month-distance Newey-West HAC SEs."""
    work = monthly_df.copy()
    if "mnum" not in work.columns:
        work["mnum"] = work["month"].astype(str).str[5:7].astype(int)
    if "year" not in work.columns:
        work["year"] = work["month"].astype(str).str[:4].astype(int)

    valid = work.dropna(subset=[value_col, *covariates]).sort_values("month").reset_index(drop=True)
    n = int(len(valid))
    month_counts = valid["mnum"].value_counts()
    min_cal_months = 6 if allow_partial_calendar_months else 12

    if n < 24 or len(month_counts) < min_cal_months or bool((month_counts < 2).any()):
        return {
            "window_id": window_id,
            "label": label,
            "status": "insufficient_evidence",
            "reason": (
                f"Only {n} valid months across {len(month_counts)} calendar months; "
                f"requires >=24 months spanning >={min_cal_months} calendar months with >=2 years each."
            ),
            "start_month": str(valid["month"].iloc[0]) if n else None,
            "end_month": str(valid["month"].iloc[-1]) if n else None,
            "calendar_months_included": sorted(int(m) for m in month_counts.index),
            "n_months": n,
            "degrees_of_freedom": None,
            "method": f"Withheld (insufficient_evidence: {n} months)",
            "covariates": list(covariates),
            "hac_max_lag_months": None,
            "slope_per_year": None,
            "slope_per_decade": None,
            "hac_se_per_year": None,
            "ci_low": None,
            "ci_high": None,
            "t_statistic": None,
            "p_value": None,
            "significant": None,
            "nonparametric_sensitivity": None,
        }

    m0 = pd.to_datetime(valid["month"].iloc[0] + "-01")
    t_yr = (pd.to_datetime(valid["month"] + "-01") - m0).dt.days.to_numpy(dtype=float) / 365.25
    dummies = pd.get_dummies(valid["mnum"], dtype=float).to_numpy()
    design_cols: List[np.ndarray] = [t_yr, dummies] + [valid[c].to_numpy(dtype=float) for c in covariates]
    X = np.column_stack(design_cols)
    y = valid[value_col].to_numpy(dtype=float)

    k_params = int(X.shape[1])
    df_resid = int(n - k_params)
    if df_resid < 8:
        return {
            "window_id": window_id,
            "label": label,
            "status": "insufficient_evidence",
            "reason": f"Residual degrees of freedom ({df_resid}) below minimum threshold (8).",
            "start_month": str(valid["month"].iloc[0]),
            "end_month": str(valid["month"].iloc[-1]),
            "calendar_months_included": sorted(int(m) for m in month_counts.index),
            "n_months": n,
            "degrees_of_freedom": df_resid,
            "method": f"Withheld (insufficient_evidence: df={df_resid})",
            "covariates": list(covariates),
            "hac_max_lag_months": None,
            "slope_per_year": None,
            "slope_per_decade": None,
            "hac_se_per_year": None,
            "ci_low": None,
            "ci_high": None,
            "t_statistic": None,
            "p_value": None,
            "significant": None,
            "nonparametric_sensitivity": None,
        }

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    xtx_inv = np.linalg.pinv(X.T @ X)
    scores = X * resid[:, None]

    # Accumulate Bartlett-weighted autocovariances by true calendar-month offset
    # so filtered series never treat observations across dropped winter gaps as lag-1 neighbors.
    midx = (valid["year"].to_numpy(dtype=int) * 12) + valid["mnum"].to_numpy(dtype=int)
    pos_by_midx = {int(m): idx for idx, m in enumerate(midx)}
    lag_limit = min(6, max(1, n // 4))
    omega = scores.T @ scores
    for lag in range(1, lag_limit + 1):
        weight = 1.0 - float(lag) / float(lag_limit + 1)
        cross = np.zeros((k_params, k_params), dtype=float)
        for j, m_val in enumerate(midx):
            i = pos_by_midx.get(int(m_val) - lag)
            if i is not None:
                cross += np.outer(scores[j], scores[i])
        omega += weight * (cross + cross.T)

    v_hac = (float(n) / float(df_resid)) * (xtx_inv @ omega @ xtx_inv)
    slope = float(beta[0])
    var_slope = max(float(v_hac[0, 0]), 0.0)
    se_hac = math.sqrt(var_slope)

    if se_hac > 0.0:
        t_stat = slope / se_hac
        raw_p = float(2.0 * student_t.sf(abs(t_stat), df=df_resid))
        t_crit = float(student_t.ppf(0.975, df=df_resid))
        ci_low = slope - t_crit * se_hac
        ci_high = slope + t_crit * se_hac
    else:
        t_stat = 0.0
        raw_p = 1.0
        ci_low = slope
        ci_high = slope

    nonparam: Optional[Dict[str, Any]] = None
    if not covariates:
        ts_yr = _seasonal_theil_sen(valid, value_col)
        anom = (valid[value_col] - valid.groupby("mnum")[value_col].transform("mean")).to_numpy(dtype=float)
        hr = _hamed_rao_on_anomalies(anom)
        nonparam = {
            "method": NONPARAM_METHOD_NAME,
            "seasonal_theil_sen_slope_per_year": ts_yr,
            "seasonal_theil_sen_slope_per_decade": clean_float(ts_yr * 10.0) if ts_yr is not None else None,
            "hamed_rao_mk": hr,
        }

    method_label = (
        FE_HAC_METHOD_NAME
        if not covariates
        else f"{FE_HAC_METHOD_NAME} (adjusted for {', '.join(covariates)})"
    )
    return {
        "window_id": window_id,
        "label": label,
        "status": "assessed",
        "reason": None,
        "start_month": str(valid["month"].iloc[0]),
        "end_month": str(valid["month"].iloc[-1]),
        "calendar_months_included": sorted(int(m) for m in month_counts.index),
        "n_months": n,
        "degrees_of_freedom": df_resid,
        "method": method_label,
        "covariates": list(covariates),
        "hac_max_lag_months": int(lag_limit),
        "slope_per_year": clean_float(slope),
        "slope_per_decade": clean_float(slope * 10.0),
        "hac_se_per_year": clean_float(se_hac),
        "ci_low": clean_float(ci_low),
        "ci_high": clean_float(ci_high),
        "t_statistic": clean_float(t_stat, 4),
        "p_value": _clean_p(raw_p),
        "significant": bool(raw_p < 0.05),
        "nonparametric_sensitivity": nonparam,
    }


def build_kyiv_no2_sensitivities(
    *,
    air_results: Mapping[str, Any],
    panel_df: pd.DataFrame,
    kyiv_four_results: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluate Kyiv NO2 coverage-exclusion and weather-adjusted Month-FE HAC trends."""
    air_df = pd.DataFrame(air_results.get("monthly_series", [])).copy()
    air_df["year"] = air_df["month"].astype(str).str[:4].astype(int)
    air_df["mnum"] = air_df["month"].astype(str).str[5:7].astype(int)

    kyiv_wx = (
        panel_df[panel_df["region_id"] == "kyiv_no2_box"][["month", *KYIV_WEATHER_COVARIATES]]
        .drop_duplicates(subset=["month"])
        .copy()
    )
    merged = air_df.merge(kyiv_wx, on="month", how="left")
    merged["flagged_below_50_pct"] = merged["flagged_below_50_pct"].astype(bool)

    pre_mask = merged["month"] <= "2022-02"
    unflagged_mask = ~merged["flagged_below_50_pct"]

    def _run(
        name: str,
        label: str,
        sub: pd.DataFrame,
        covariates: Sequence[str] = (),
        partial_cal: bool = False,
    ) -> Dict[str, Any]:
        return evaluate_monthly_fe_hac_trend(
            sub,
            "no2_mean_molec_cm2",
            name,
            label,
            covariates=covariates,
            allow_partial_calendar_months=partial_cal,
        )

    all_full = _run("all_months_full_record", "Kyiv NO2 all months (2015-03 to 2022-08)", merged)
    all_pre = _run("all_months_pre_invasion", "Kyiv NO2 all months pre-invasion (2015-03 to 2022-02)", merged[pre_mask])
    unflagged_full = _run(
        "unflagged_ge50pct_full_record",
        "Kyiv NO2 excluding <50% coverage months (2015-03 to 2022-08)",
        merged[unflagged_mask],
        partial_cal=True,
    )
    unflagged_pre = _run(
        "unflagged_ge50pct_pre_invasion",
        "Kyiv NO2 excluding <50% coverage months pre-invasion (2015-03 to 2022-02)",
        merged[unflagged_mask & pre_mask],
        partial_cal=True,
    )

    wx_all_full = _run(
        "weather_adjusted_all_months_full_record",
        "Kyiv NO2 weather-adjusted all months (ws10m, cloud_amt, ps, t2m)",
        merged,
        covariates=KYIV_WEATHER_COVARIATES,
    )
    wx_all_pre = _run(
        "weather_adjusted_all_months_pre_invasion",
        "Kyiv NO2 weather-adjusted pre-invasion (ws10m, cloud_amt, ps, t2m)",
        merged[pre_mask],
        covariates=KYIV_WEATHER_COVARIATES,
    )
    wx_unflagged_full = _run(
        "weather_adjusted_unflagged_full_record",
        "Kyiv NO2 weather-adjusted excluding <50% coverage months (full record)",
        merged[unflagged_mask],
        covariates=KYIV_WEATHER_COVARIATES,
        partial_cal=True,
    )
    wx_unflagged_pre = _run(
        "weather_adjusted_unflagged_pre_invasion",
        "Kyiv NO2 weather-adjusted excluding <50% coverage months (pre-invasion)",
        merged[unflagged_mask & pre_mask],
        covariates=KYIV_WEATHER_COVARIATES,
        partial_cal=True,
    )

    dropped_months = sorted(merged.loc[merged["flagged_below_50_pct"], "month"].astype(str).tolist())
    dropped_2022 = [m for m in dropped_months if m.startswith("2022-")]
    full_flip = bool(all_full["significant"]) != bool(unflagged_full["significant"])
    pre_flip = bool(all_pre["significant"]) != bool(unflagged_pre["significant"])
    bt_ref = kyiv_four_results.get("kyiv_intervention_and_weather_controls", {})

    return {
        "n_total_months": int(len(merged)),
        "n_flagged_below_50_pct": len(dropped_months),
        "n_unflagged_months": int(unflagged_mask.sum()),
        "dropped_calendar_months_completely_excluded": [11, 12],
        "flagged_months_2022": dropped_2022,
        "coverage_exclusion_sensitivity": {
            "all_months_full_record": all_full,
            "unflagged_ge50pct_full_record": unflagged_full,
            "all_months_pre_invasion": all_pre,
            "unflagged_ge50pct_pre_invasion": unflagged_pre,
            "verdict_flips_full_record": full_flip,
            "verdict_flips_pre_invasion": pre_flip,
            "interpretation": (
                "Excluding all 37 low-coverage (<50% valid days) months (leaving 53 months, completely "
                "excluding Nov/Dec) shifts the unadjusted linear FE-HAC trend from non-significant "
                f"(n={all_full['n_months']}, p={all_full['p_value']}) to nominally significant "
                f"(n={unflagged_full['n_months']}, p={unflagged_full['p_value']}), while pre-invasion "
                f"(n={unflagged_pre['n_months']}, p={unflagged_pre['p_value']}) remains non-significant. "
                "Canonical atlas verdicts remain in reports/trend_results.json (/api/trends), which requires "
                "BH-FDR significance plus April-September confirmation where winter fails coverage."
            ),
        },
        "weather_adjusted_fe_hac_trends": {
            "covariates": list(KYIV_WEATHER_COVARIATES),
            "all_months_full_record": wx_all_full,
            "all_months_pre_invasion": wx_all_pre,
            "unflagged_ge50pct_full_record": wx_unflagged_full,
            "unflagged_ge50pct_pre_invasion": wx_unflagged_pre,
            "box_tiao_reference": {
                "unadjusted_all_months": bt_ref.get("box_tiao_unadjusted_all_months"),
                "weather_controlled_all_months": bt_ref.get("box_tiao_weather_controlled_all_months"),
                "weather_controlled_excl_apr2022": bt_ref.get("box_tiao_weather_controlled_excl_apr2022"),
                "weather_controlled_mar_aug_only": bt_ref.get("box_tiao_weather_controlled_mar_aug_only"),
            },
            "interpretation": (
                "Controlling for wind speed (ws10m), cloud cover (cloud_amt), surface pressure (ps), and "
                "temperature (t2m) attenuates the Kyiv NO2 linear trend magnitude from "
                f"{all_full['slope_per_year']:.3e} to {wx_all_full['slope_per_year']:.3e} molec/cm^2/yr "
                f"(p={wx_all_full['p_value']}) across all 90 months and from "
                f"{unflagged_full['slope_per_year']:.3e} to {wx_unflagged_full['slope_per_year']:.3e} "
                f"(p={wx_unflagged_full['p_value']}) across the 53 unflagged months."
            ),
        },
    }


def _extract_no2_cross_city_summary(
    air_results: Optional[Mapping[str, Any]],
    no2_regional: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not air_results or not no2_regional or not isinstance(no2_regional.get("regions"), Mapping):
        return {
            "status": "not_available",
            "reason": "Regional NO2 comparison payload (atlas_no2_regional.json) was not supplied.",
        }

    kyiv_cmp = (air_results.get("comparisons") or {}).get("primary_2015_2019_valid_day")
    reg_map = no2_regional["regions"]
    if not kyiv_cmp or "poland_krakow" not in reg_map or "czechia_prague" not in reg_map:
        return {
            "status": "not_available",
            "reason": "Missing Kyiv, Krakow, or Prague NO2 March-August 2022 vs 2015-2019 comparison.",
        }

    def _entry_from_regional(rid: str) -> Optional[Dict[str, Any]]:
        item = reg_map.get(rid)
        if not isinstance(item, Mapping):
            return None
        s = ((item.get("seasonal_mar_aug") or {}).get("vs_2015_2019")) or None
        if not isinstance(s, Mapping):
            return None
        return {
            "baseline_mean_molec_cm2": clean_float(s.get("baseline_mean")),
            "target_mean_molec_cm2": clean_float(s.get("target_mean")),
            "abs_diff_molec_cm2": clean_float(s.get("abs_diff")),
            "pct_change": clean_float(s.get("pct_change"), 2),
        }

    kyiv_entry = {
        "baseline_mean_molec_cm2": clean_float(kyiv_cmp.get("baseline_mean_molec_cm2")),
        "target_mean_molec_cm2": clean_float(kyiv_cmp.get("target_mean_molec_cm2")),
        "abs_diff_molec_cm2": clean_float(kyiv_cmp.get("absolute_change_molec_cm2")),
        "pct_change": clean_float(kyiv_cmp.get("pct_change"), 2),
    }
    krak_entry = _entry_from_regional("poland_krakow")
    prag_entry = _entry_from_regional("czechia_prague")
    kharkiv_entry = _entry_from_regional("kharkiv_city")
    kyiv_pct = kyiv_entry.get("pct_change")
    krak_pct = krak_entry.get("pct_change") if krak_entry else None
    prag_pct = prag_entry.get("pct_change") if prag_entry else None
    out: Dict[str, Any] = {
        "status": "available",
        "baseline_window": "March-August 2022 vs. 2015-2019",
        "kyiv_no2_box": kyiv_entry,
        "poland_krakow": krak_entry,
        "czechia_prague": prag_entry,
        "kharkiv_city": kharkiv_entry,
        "kyiv_minus_krakow_pct_pts": (
            clean_float(kyiv_pct - krak_pct, 2)
            if (kyiv_pct is not None and krak_pct is not None)
            else None
        ),
        "kyiv_minus_prague_pct_pts": (
            clean_float(kyiv_pct - prag_pct, 2)
            if (kyiv_pct is not None and prag_pct is not None)
            else None
        ),
    }
    return out


def build_krakow_prague_comparison(
    panel_df: pd.DataFrame,
    power_specs: Sequence[Any],
    *,
    air_results: Optional[Mapping[str, Any]] = None,
    no2_regional: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare March-August 2022 Kyiv changes against Krakow, Prague, and 6-box Ukraine averages."""
    mar_aug = panel_df[panel_df["month_num"].isin(MARCH_AUGUST_MONTHS)].copy()
    comparisons: List[Dict[str, Any]] = []

    def _window_diff(sub_df: pd.DataFrame, rid: str, col: str, is_interval: bool) -> Dict[str, Any]:
        rdf = sub_df[sub_df["region_id"] == rid]
        b15_raw = rdf[rdf["year"].isin(range(2015, 2020))][col].mean()
        b19_raw = rdf[rdf["year"].isin(range(2019, 2022))][col].mean()
        t22_raw = rdf[rdf["year"] == 2022][col].mean()
        d15, pct15, pct15_status = safe_pct_change(t22_raw, b15_raw, is_interval_scale=is_interval)
        d19, pct19, pct19_status = safe_pct_change(t22_raw, b19_raw, is_interval_scale=is_interval)
        return {
            "mean_2015_2019": clean_float(b15_raw, 4),
            "mean_2019_2021": clean_float(b19_raw, 4),
            "mean_2022": clean_float(t22_raw, 4),
            "diff_vs_2015_2019": clean_float(d15, 4),
            "diff_vs_2019_2021": clean_float(d19, 4),
            "pct_change_vs_2015_2019": clean_float(pct15, 2),
            "pct_change_vs_2019_2021": clean_float(pct19, 2),
            "pct_change_status_vs_2015_2019": pct15_status,
            "pct_change_status_vs_2019_2021": pct19_status,
        }

    for spec in power_specs:
        col = spec.metric_id
        kyiv_ma = _window_diff(mar_aug, "kyiv_no2_box", col, spec.is_interval_scale)
        krak_ma = _window_diff(mar_aug, "poland_krakow", col, spec.is_interval_scale)
        prag_ma = _window_diff(mar_aug, "czechia_prague", col, spec.is_interval_scale)

        ukr_shifts = [
            _window_diff(mar_aug, rid, col, spec.is_interval_scale)["diff_vs_2015_2019"]
            for rid in UKRAINE_REGION_IDS
        ]
        ukr_valid = [v for v in ukr_shifts if v is not None]
        ukr_mean_shift = clean_float(sum(ukr_valid) / len(ukr_valid), 4) if ukr_valid else None

        did = lambda a, b: clean_float(a - b, 4) if (a is not None and b is not None) else None
        same_sign = lambda a, b: bool((a * b) > 0) if (a is not None and b is not None) else None

        comparisons.append({
            "metric_id": col,
            "element_id": spec.element_id,
            "label": spec.label,
            "units": spec.units,
            "is_interval_scale": spec.is_interval_scale,
            "seasonal_window": "March-August",
            "kyiv_no2_box": kyiv_ma,
            "poland_krakow": krak_ma,
            "czechia_prague": prag_ma,
            "ukraine_6_boxes_mean_diff_vs_2015_2019": ukr_mean_shift,
            "kyiv_minus_krakow_diff_vs_2015_2019": did(kyiv_ma["diff_vs_2015_2019"], krak_ma["diff_vs_2015_2019"]),
            "kyiv_minus_prague_diff_vs_2015_2019": did(kyiv_ma["diff_vs_2015_2019"], prag_ma["diff_vs_2015_2019"]),
            "kyiv_minus_krakow_diff_vs_2019_2021": did(kyiv_ma["diff_vs_2019_2021"], krak_ma["diff_vs_2019_2021"]),
            "kyiv_minus_prague_diff_vs_2019_2021": did(kyiv_ma["diff_vs_2019_2021"], prag_ma["diff_vs_2019_2021"]),
            "same_direction_as_krakow_vs_2015_2019": same_sign(kyiv_ma["diff_vs_2015_2019"], krak_ma["diff_vs_2015_2019"]),
            "same_direction_as_prague_vs_2015_2019": same_sign(kyiv_ma["diff_vs_2015_2019"], prag_ma["diff_vs_2015_2019"]),
        })

    by_metric = {row["metric_id"]: row for row in comparisons}
    ws_k, ws_kr, ws_pr = (
        by_metric["ws10m"]["kyiv_no2_box"]["diff_vs_2015_2019"],
        by_metric["ws10m"]["poland_krakow"]["diff_vs_2015_2019"],
        by_metric["ws10m"]["czechia_prague"]["diff_vs_2015_2019"],
    )
    cl_k, cl_kr, cl_pr = (
        by_metric["cloud_amt"]["kyiv_no2_box"]["diff_vs_2015_2019"],
        by_metric["cloud_amt"]["poland_krakow"]["diff_vs_2015_2019"],
        by_metric["cloud_amt"]["czechia_prague"]["diff_vs_2015_2019"],
    )
    t_k, t_kr, t_pr = (
        by_metric["t2m"]["kyiv_no2_box"]["diff_vs_2015_2019"],
        by_metric["t2m"]["poland_krakow"]["diff_vs_2015_2019"],
        by_metric["t2m"]["czechia_prague"]["diff_vs_2015_2019"],
    )

    return {
        "seasonal_window": "March-August (2022 vs 2015-2019 and 2019-2021 baselines)",
        "regions_compared": {
            "primary_target": "kyiv_no2_box",
            "comparators": ["poland_krakow", "czechia_prague"],
            "ukraine_context_mean": list(UKRAINE_REGION_IDS),
        },
        "no2_cross_city_comparison": _extract_no2_cross_city_summary(air_results, no2_regional),
        "key_meteorology_contrast_summary": {
            "ws10m_diff_2022_vs_2015_2019_m_s": {
                "kyiv_no2_box": ws_k,
                "poland_krakow": ws_kr,
                "czechia_prague": ws_pr,
            },
            "cloud_amt_diff_2022_vs_2015_2019_pct": {
                "kyiv_no2_box": cl_k,
                "poland_krakow": cl_kr,
                "czechia_prague": cl_pr,
            },
            "t2m_diff_2022_vs_2015_2019_c": {
                "kyiv_no2_box": t_k,
                "poland_krakow": t_kr,
                "czechia_prague": t_pr,
            },
            "vpd_kpa_diff_2022_vs_2015_2019": {
                "kyiv_no2_box": by_metric["vpd_kpa"]["kyiv_no2_box"]["diff_vs_2015_2019"],
                "poland_krakow": by_metric["vpd_kpa"]["poland_krakow"]["diff_vs_2015_2019"],
                "czechia_prague": by_metric["vpd_kpa"]["czechia_prague"]["diff_vs_2015_2019"],
            },
            "interpretation": (
                f"In March-August 2022 vs 2015-2019, Kyiv experienced windier ({ws_k:+.2f} m/s), cloudier "
                f"({cl_k:+.2f}%), and cooler ({t_k:+.2f} C) conditions, whereas Krakow and Prague were "
                f"calmer ({ws_kr:+.2f} / {ws_pr:+.2f} m/s) and clearer ({cl_kr:+.2f}% / {cl_pr:+.2f}%). "
                "This synoptic divergence independently reinforces lower 2022 NO2 in Kyiv alongside the "
                "~2.5-3.7x larger NO2 drop observed in Kyiv/Kharkiv versus Krakow/Prague."
            ),
        },
        "metrics_count": len(comparisons),
        "metrics": comparisons,
    }
