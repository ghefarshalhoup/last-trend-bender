"""
Complete FIRMS VIIRS S-NPP (SV-C2) Fire Activity analysis, candidate region comparability,
visualizations, chart CSVs, quality report, and backend-ready JSON export.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "war_env_tracker_mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.fire_pipeline import (
    DEFAULT_FIRE_RAW_DIR,
    DEFAULT_REPORTS_DIR,
    STUDY_MONTHS,
    STUDY_YEARS,
    RegionSpec,
    _clean_float,
    discover_fire_inputs,
    load_and_validate_firms_archives,
    summarize_repeated_detections,
)

SCHEMA_VERSION = "1.0.0"
TARGET_YEAR = 2022
BASELINE_YEARS = (2019, 2020, 2021)

MONTH_ABBR = {
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
}

PROPOSED_REGIONS: Tuple[RegionSpec, ...] = (
    RegionSpec(
        region_id="ukraine_national",
        name="Ukraine (Full Country Export)",
        role="national_aggregate",
        south=44.30,
        north=52.50,
        west=22.00,
        east=40.30,
        description="Full national FIRMS SV-C2 country download bounding all Ukrainian territory.",
    ),
    RegionSpec(
        region_id="donbas_kharkiv_east",
        name="East Frontline Corridor (Donbas–Kharkiv, proposed study)",
        role="proposed_study_region",
        south=46.80,
        north=50.30,
        west=35.50,
        east=40.20,
        description="Proposed active-conflict eastern belt spanning Kharkiv, Luhansk, Donetsk, and eastern Zaporizhzhia.",
    ),
    RegionSpec(
        region_id="south_steppe_belt",
        name="South Steppe Corridor (Kherson–Mykolaiv–Crimea edge, proposed study)",
        role="proposed_study_region",
        south=44.40,
        north=47.50,
        west=30.00,
        east=35.50,
        description="Proposed southern steppe and coastal frontline corridor west of 35.5E.",
    ),
    RegionSpec(
        region_id="kyiv_north_belt",
        name="North Corridor (Kyiv–Chernihiv belt, proposed study)",
        role="proposed_study_region",
        south=50.00,
        north=52.40,
        west=28.50,
        east=34.50,
        description="Proposed northern forest/agricultural corridor covering Kyiv and Chernihiv oblasts (February–March invasion axis).",
    ),
    RegionSpec(
        region_id="kyiv_no2_box",
        name="Kyiv Air-Matched Box (0.5 deg, cross-layer check)",
        role="proposed_cross_layer_study_box",
        south=50.200,
        north=50.700,
        west=30.273,
        east=30.773,
        description="Exact bounding box used in the Air/NO2 OMNO2d analysis for Kyiv cross-element context.",
    ),
    RegionSpec(
        region_id="central_interior_cand",
        name="Central Interior Steppe (proposed reference for East/South)",
        role="proposed_reference_region",
        south=47.50,
        north=50.00,
        west=27.50,
        east=35.50,
        description="Proposed lower-ground-combat central agricultural/steppe comparator matched by climate belt to East/South.",
    ),
    RegionSpec(
        region_id="west_ukraine_cand",
        name="Western Ukraine (proposed reference for North/Kyiv)",
        role="proposed_reference_region",
        south=47.70,
        north=51.80,
        west=22.10,
        east=27.50,
        description="Proposed western lower-ground-combat comparator matched by spring fire seasonality to Kyiv/North.",
    ),
)

FILTER_MODES: Tuple[Tuple[str, str], ...] = (
    ("type0_vegetation_all_conf", "type=0 presumed vegetation/open fire detections (all confidence: l, n, h)"),
    ("type0_vegetation_nominal_high", "type=0 presumed vegetation/open fire detections (confidence in {n, h} only)"),
    ("all_types_all_conf", "All FIRMS thermal detections (types 0, 2, 3; all confidence)"),
    ("type2_static_industrial", "type=2 static land anomalies only (industrial plants/flares sensitivity check)"),
)


def _safe_pct_change(target_val: Optional[float], baseline_val: Optional[float]) -> Tuple[Optional[float], Optional[float], str]:
    """Compute (abs_diff, pct_change, status) guarding nonpositive or missing denominators."""
    t_clean = _clean_float(target_val)
    b_clean = _clean_float(baseline_val)
    if t_clean is None or b_clean is None:
        return None, None, "withheld_missing_data"
    diff = t_clean - b_clean
    if b_clean <= 0.0:
        return diff, None, "withheld_nonpositive_baseline"
    return diff, (diff / b_clean) * 100.0, "computed"


def _apply_filter_mode(df: pd.DataFrame, filter_mode: str) -> pd.DataFrame:
    if filter_mode == "type0_vegetation_all_conf":
        return df[df["type"] == 0]
    if filter_mode == "type0_vegetation_nominal_high":
        return df[(df["type"] == 0) & (df["confidence"].isin(["n", "h"]))]
    if filter_mode == "all_types_all_conf":
        return df
    if filter_mode == "type2_static_industrial":
        return df[df["type"] == 2]
    raise ValueError(f"Unknown filter_mode: {filter_mode}")


def _apply_region_box(df: pd.DataFrame, region: RegionSpec) -> pd.DataFrame:
    if region.region_id == "ukraine_national":
        return df
    mask = (
        df["latitude"].between(region.south, region.north)
        & df["longitude"].between(region.west, region.east)
    )
    return df.loc[mask]


def compute_satellite_month_coverage(
    clean_df: pd.DataFrame,
    years: Sequence[int] = STUDY_YEARS,
    months: Sequence[int] = STUDY_MONTHS,
) -> pd.DataFrame:
    """
    Compute Ukraine-wide daily S-NPP observation coverage per YYYY-MM month.
    Distinguishes nationwide satellite gap days (zero detections everywhere in Ukraine,
    notably Jul 27 - Aug 10 2022) from quiet regional days.
    """
    rows: List[Dict[str, object]] = []
    for yr in years:
        for m in months:
            start_ts = pd.Timestamp(year=int(yr), month=int(m), day=1)
            cal_days = int(start_ts.days_in_month)
            ym = f"{yr}-{m:02d}"
            sub = clean_df[clean_df["month"] == ym]
            obs_days = int(sub["acq_date_str"].nunique())
            rows.append(
                {
                    "year": int(yr),
                    "calendar_month": int(m),
                    "month": ym,
                    "calendar_days": cal_days,
                    "satellite_observed_days": obs_days,
                    "satellite_missing_days": cal_days - obs_days,
                    "satellite_coverage_fraction": round(obs_days / float(cal_days), 4),
                }
            )
    return pd.DataFrame(rows)


def compute_monthly_fire_table(
    clean_df: pd.DataFrame,
    sat_cov_df: pd.DataFrame,
    regions: Sequence[RegionSpec] = PROPOSED_REGIONS,
    filter_modes: Sequence[Tuple[str, str]] = FILTER_MODES,
    years: Sequence[int] = STUDY_YEARS,
    months: Sequence[int] = STUDY_MONTHS,
) -> pd.DataFrame:
    """Aggregate clean FIRMS hotspot detections by region, filter mode, and YYYY-MM month."""
    cov_lookup = sat_cov_df.set_index("month").to_dict("index")
    out_rows: List[Dict[str, object]] = []

    for region in regions:
        r_df = _apply_region_box(clean_df, region)
        for mode_id, _ in filter_modes:
            m_df = _apply_filter_mode(r_df, mode_id)
            for yr in years:
                for m in months:
                    ym = f"{yr}-{m:02d}"
                    cinfo = cov_lookup[ym]
                    cal_days = int(cinfo["calendar_days"])
                    sat_days = int(cinfo["satellite_observed_days"])
                    cov_frac = float(cinfo["satellite_coverage_fraction"])

                    sub = m_df[m_df["month"] == ym]
                    det_count = int(len(sub))
                    det_per_sat_day = round(det_count / float(sat_days), 4) if sat_days > 0 else None
                    reg_active_days = int(sub["acq_date_str"].nunique()) if det_count > 0 else 0
                    cell_days = int(len(sub[["cell_lat", "cell_lon", "acq_date_str"]].drop_duplicates())) if det_count > 0 else 0
                    day_cnt = int((sub["daynight"] == "D").sum())
                    night_cnt = int((sub["daynight"] == "N").sum())
                    frp_vals = sub["frp"].dropna()
                    frp_sum = _clean_float(frp_vals.sum(), 2) if not frp_vals.empty else 0.0
                    frp_med = _clean_float(frp_vals.median(), 2) if not frp_vals.empty else None

                    out_rows.append(
                        {
                            "year": int(yr),
                            "calendar_month": int(m),
                            "month": ym,
                            "region_id": region.region_id,
                            "region_role": region.role,
                            "filter_mode": mode_id,
                            "detections": det_count,
                            "satellite_observed_days": sat_days,
                            "calendar_days": cal_days,
                            "satellite_coverage_fraction": cov_frac,
                            "detections_per_observed_day": det_per_sat_day,
                            "region_days_with_detections": reg_active_days,
                            "unique_0_01deg_cell_days": cell_days,
                            "day_detections": day_cnt,
                            "night_detections": night_cnt,
                            "frp_sum_mw": frp_sum,
                            "frp_median_mw": frp_med,
                        }
                    )
    return pd.DataFrame(out_rows)


def compute_regional_comparisons(
    monthly_df: pd.DataFrame,
    regions: Sequence[RegionSpec] = PROPOSED_REGIONS,
    filter_modes: Sequence[Tuple[str, str]] = FILTER_MODES,
    baseline_years: Sequence[int] = BASELINE_YEARS,
    target_year: int = TARGET_YEAR,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Compare 2022 against the 2019-2021 average AND against individual years (especially 2021)
    across March-August and May-August (separating March spring agricultural burns),
    using both raw detections and active-satellite-day normalized detection rates.
    """
    windows = [
        ("mar_aug", "March–August (full 6-month window)", [3, 4, 5, 6, 7, 8]),
        ("may_aug", "May–August (post-spring-burn summer window)", [5, 6, 7, 8]),
    ]

    flat_rows: List[Dict[str, object]] = []
    structured: Dict[str, object] = {}

    for region in regions:
        reg_entry: Dict[str, object] = {}
        for mode_id, _ in filter_modes:
            mode_entry: Dict[str, object] = {}
            sub_rm = monthly_df[(monthly_df["region_id"] == region.region_id) & (monthly_df["filter_mode"] == mode_id)]
            for win_id, win_label, win_months in windows:
                w_df = sub_rm[sub_rm["calendar_month"].isin(win_months)]
                ann_agg = (
                    w_df.groupby("year", as_index=False)
                    .agg(
                        detections=("detections", "sum"),
                        satellite_observed_days=("satellite_observed_days", "sum"),
                        calendar_days=("calendar_days", "sum"),
                        unique_cell_days=("unique_0_01deg_cell_days", "sum"),
                        frp_sum_mw=("frp_sum_mw", "sum"),
                    )
                    .sort_values("year")
                )
                ann_agg["rate_per_observed_day"] = np.where(
                    ann_agg["satellite_observed_days"] > 0,
                    ann_agg["detections"] / ann_agg["satellite_observed_days"],
                    np.nan,
                )
                by_y = ann_agg.set_index("year")

                base_dets = [float(by_y.loc[y, "detections"]) for y in baseline_years if y in by_y.index]
                base_rates = [_clean_float(by_y.loc[y, "rate_per_observed_day"]) for y in baseline_years if y in by_y.index]
                base_rates = [r for r in base_rates if r is not None]

                base_det_mean = float(np.mean(base_dets)) if base_dets else None
                base_det_min = float(np.min(base_dets)) if base_dets else None
                base_det_max = float(np.max(base_dets)) if base_dets else None
                base_rate_mean = float(np.mean(base_rates)) if base_rates else None

                t_det = float(by_y.loc[target_year, "detections"]) if target_year in by_y.index else None
                t_rate = _clean_float(by_y.loc[target_year, "rate_per_observed_day"]) if target_year in by_y.index else None
                t_obs_days = int(by_y.loc[target_year, "satellite_observed_days"]) if target_year in by_y.index else 0
                t_cal_days = int(by_y.loc[target_year, "calendar_days"]) if target_year in by_y.index else 0

                y21_det = float(by_y.loc[2021, "detections"]) if 2021 in by_y.index else None
                y21_rate = _clean_float(by_y.loc[2021, "rate_per_observed_day"]) if 2021 in by_y.index else None

                abs_b, pct_b, st_b = _safe_pct_change(t_det, base_det_mean)
                abs_rate_b, pct_rate_b, st_rate_b = _safe_pct_change(t_rate, base_rate_mean)
                abs_21, pct_21, st_21 = _safe_pct_change(t_det, y21_det)
                abs_rate_21, pct_rate_21, st_rate_21 = _safe_pct_change(t_rate, y21_rate)

                yearly_dict = {
                    str(int(r.year)): {
                        "detections": int(r.detections),
                        "satellite_observed_days": int(r.satellite_observed_days),
                        "calendar_days": int(r.calendar_days),
                        "rate_per_observed_day": _clean_float(r.rate_per_observed_day, 4),
                        "unique_0_01deg_cell_days": int(r.unique_cell_days),
                        "frp_sum_mw": _clean_float(r.frp_sum_mw, 2),
                    }
                    for r in ann_agg.itertuples(index=False)
                }

                win_payload = {
                    "window_id": win_id,
                    "label": win_label,
                    "months_included": win_months,
                    "yearly": yearly_dict,
                    "baseline_2019_2021": {
                        "mean_detections": _clean_float(base_det_mean, 2),
                        "min_detections": _clean_float(base_det_min, 2),
                        "max_detections": _clean_float(base_det_max, 2),
                        "mean_rate_per_observed_day": _clean_float(base_rate_mean, 4),
                    },
                    "target_2022": {
                        "detections": _clean_float(t_det, 0),
                        "satellite_observed_days": t_obs_days,
                        "calendar_days": t_cal_days,
                        "rate_per_observed_day": _clean_float(t_rate, 4),
                    },
                    "vs_baseline_2019_2021": {
                        "detections_abs_change": _clean_float(abs_b, 2),
                        "detections_pct_change": _clean_float(pct_b, 2),
                        "detections_pct_status": st_b,
                        "rate_per_day_abs_change": _clean_float(abs_rate_b, 4),
                        "rate_per_day_pct_change": _clean_float(pct_rate_b, 2),
                        "rate_per_day_pct_status": st_rate_b,
                    },
                    "vs_2021_prior_year": {
                        "detections_abs_change": _clean_float(abs_21, 2),
                        "detections_pct_change": _clean_float(pct_21, 2),
                        "detections_pct_status": st_21,
                        "rate_per_day_abs_change": _clean_float(abs_rate_21, 4),
                        "rate_per_day_pct_change": _clean_float(pct_rate_21, 2),
                        "rate_per_day_pct_status": st_rate_21,
                    },
                }
                mode_entry[win_id] = win_payload

                flat_rows.append(
                    {
                        "region_id": region.region_id,
                        "region_name": region.name,
                        "region_role": region.role,
                        "filter_mode": mode_id,
                        "window_id": win_id,
                        "y2019_detections": yearly_dict.get("2019", {}).get("detections"),
                        "y2020_detections": yearly_dict.get("2020", {}).get("detections"),
                        "y2021_detections": yearly_dict.get("2021", {}).get("detections"),
                        "y2022_detections": yearly_dict.get("2022", {}).get("detections"),
                        "baseline_2019_2021_mean_detections": _clean_float(base_det_mean, 2),
                        "pct_change_vs_2019_2021": _clean_float(pct_b, 2),
                        "pct_status_vs_2019_2021": st_b,
                        "pct_change_vs_2021": _clean_float(pct_21, 2),
                        "baseline_2019_2021_rate_per_day": _clean_float(base_rate_mean, 4),
                        "y2022_rate_per_day": _clean_float(t_rate, 4),
                        "rate_pct_change_vs_2019_2021": _clean_float(pct_rate_b, 2),
                    }
                )
            reg_entry[mode_id] = mode_entry
        structured[region.region_id] = reg_entry

    return pd.DataFrame(flat_rows), structured


def assess_pre2022_comparability(
    monthly_df: pd.DataFrame,
    regions: Sequence[RegionSpec] = PROPOSED_REGIONS,
    filter_mode: str = "type0_vegetation_all_conf",
    baseline_years: Sequence[int] = BASELINE_YEARS,
) -> Tuple[pd.DataFrame, List[Dict[str, object]]]:
    """
    Evaluate whether candidate study and candidate reference regions shared comparable
    monthly fire-activity trajectories during pre-war years (March-August 2019-2021).
    """
    pre_months = [f"{y}-{m:02d}" for y in baseline_years for m in STUDY_MONTHS]
    sub = monthly_df[(monthly_df["filter_mode"] == filter_mode) & (monthly_df["year"].isin(baseline_years))]

    study_regs = [r for r in regions if r.role in {"proposed_study_region", "proposed_cross_layer_study_box"}]
    ref_regs = [r for r in regions if r.role == "proposed_reference_region"]

    series_by_reg: Dict[str, np.ndarray] = {}
    summer_share_by_reg: Dict[str, Optional[float]] = {}
    annual_cv_by_reg: Dict[str, Optional[float]] = {}

    for reg in study_regs + ref_regs:
        r_df = sub[sub["region_id"] == reg.region_id].set_index("month")["detections"].reindex(pre_months, fill_value=0)
        vec = r_df.to_numpy(dtype=float)
        series_by_reg[reg.region_id] = vec

        total_pre = float(vec.sum())
        summer_pre = float(
            sub[(sub["region_id"] == reg.region_id) & (sub["calendar_month"].isin([6, 7, 8]))]["detections"].sum()
        )
        summer_share_by_reg[reg.region_id] = round(summer_pre / total_pre, 4) if total_pre > 0 else None

        ann_sums = sub[sub["region_id"] == reg.region_id].groupby("year")["detections"].sum().to_numpy(dtype=float)
        mean_ann = float(np.mean(ann_sums)) if len(ann_sums) > 0 else 0.0
        annual_cv_by_reg[reg.region_id] = round(float(np.std(ann_sums, ddof=1)) / mean_ann, 4) if (len(ann_sums) >= 2 and mean_ann > 0) else None

    rows: List[Dict[str, object]] = []
    for st in study_regs:
        s_vec = series_by_reg[st.region_id]
        for rf in ref_regs:
            r_vec = series_by_reg[rf.region_id]
            if np.std(s_vec) > 0 and np.std(r_vec) > 0:
                pearson_r = _clean_float(np.corrcoef(s_vec, r_vec)[0, 1], 4)
                sp_res = spearmanr(s_vec, r_vec)
                spearman_rho = _clean_float(sp_res.statistic, 4)
                z_s = (s_vec - np.mean(s_vec)) / np.std(s_vec)
                z_r = (r_vec - np.mean(r_vec)) / np.std(r_vec)
                z_rmse = _clean_float(np.sqrt(np.mean((z_s - z_r) ** 2)), 4)
            else:
                pearson_r = None
                spearman_rho = None
                z_rmse = None

            mean_s = float(np.mean(s_vec))
            mean_r = float(np.mean(r_vec))
            scale_ratio = _clean_float(mean_s / mean_r, 4) if mean_r > 0 else None

            if pearson_r is None:
                tier = "not_assessed_zero_variance"
            elif pearson_r >= 0.80:
                tier = "strong_pre2022_seasonal_alignment"
            elif pearson_r >= 0.60:
                tier = "moderate_pre2022_alignment"
            else:
                tier = "weak_regime_mismatch_not_comparable"

            rows.append(
                {
                    "study_region_id": st.region_id,
                    "study_region_name": st.name,
                    "reference_region_id": rf.region_id,
                    "reference_region_name": rf.name,
                    "n_pre2022_months": len(pre_months),
                    "pre2022_pearson_r": pearson_r,
                    "pre2022_spearman_rho": spearman_rho,
                    "standardized_anomaly_rmse": z_rmse,
                    "pre2022_level_ratio_study_to_ref": scale_ratio,
                    "study_jun_aug_share_pre2022": summer_share_by_reg[st.region_id],
                    "ref_jun_aug_share_pre2022": summer_share_by_reg[rf.region_id],
                    "study_annual_cv_pre2022": annual_cv_by_reg[st.region_id],
                    "ref_annual_cv_pre2022": annual_cv_by_reg[rf.region_id],
                    "comparability_tier": tier,
                    "agreement_status": "proposed_for_review_not_validated_control",
                }
            )
    return pd.DataFrame(rows), rows


def compute_spatial_grid_shifts(
    clean_df: pd.DataFrame,
    grid_step_deg: float = 0.25,
    baseline_years: Sequence[int] = BASELINE_YEARS,
    target_year: int = TARGET_YEAR,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Compute grid-level spatial shift (2022 minus 2019-2021 annual mean) for type=0 detections."""
    veg = clean_df[clean_df["type"] == 0].copy()
    if veg.empty:
        return pd.DataFrame(), {"top_increases": [], "top_decreases": []}

    veg["grid_lat"] = (np.floor(veg["latitude"] / grid_step_deg) + 0.5) * grid_step_deg
    veg["grid_lon"] = (np.floor(veg["longitude"] / grid_step_deg) + 0.5) * grid_step_deg

    base = veg[veg["year"].isin(baseline_years)].groupby(["grid_lat", "grid_lon"]).size() / float(len(baseline_years))
    targ = veg[veg["year"] == target_year].groupby(["grid_lat", "grid_lon"]).size().astype(float)

    all_cells = base.index.union(targ.index)
    grid_df = pd.DataFrame(index=all_cells)
    grid_df["baseline_2019_2021_annual_mean"] = base.reindex(all_cells, fill_value=0.0)
    grid_df["target_2022_detections"] = targ.reindex(all_cells, fill_value=0.0)
    grid_df["delta_2022_minus_baseline"] = grid_df["target_2022_detections"] - grid_df["baseline_2019_2021_annual_mean"]
    grid_df = grid_df.reset_index()

    top_inc = [
        {
            "cell_center_lat": round(float(r.grid_lat), 3),
            "cell_center_lon": round(float(r.grid_lon), 3),
            "baseline_2019_2021_mean": round(float(r.baseline_2019_2021_annual_mean), 1),
            "target_2022_detections": int(r.target_2022_detections),
            "delta_detections": round(float(r.delta_2022_minus_baseline), 1),
        }
        for r in grid_df.sort_values("delta_2022_minus_baseline", ascending=False).head(8).itertuples(index=False)
    ]
    top_dec = [
        {
            "cell_center_lat": round(float(r.grid_lat), 3),
            "cell_center_lon": round(float(r.grid_lon), 3),
            "baseline_2019_2021_mean": round(float(r.baseline_2019_2021_annual_mean), 1),
            "target_2022_detections": int(r.target_2022_detections),
            "delta_detections": round(float(r.delta_2022_minus_baseline), 1),
        }
        for r in grid_df.sort_values("delta_2022_minus_baseline", ascending=True).head(8).itertuples(index=False)
    ]

    return grid_df, {
        "grid_resolution_deg": grid_step_deg,
        "total_populated_cells": int(len(grid_df)),
        "cells_with_increase": int((grid_df["delta_2022_minus_baseline"] > 0).sum()),
        "cells_with_decrease": int((grid_df["delta_2022_minus_baseline"] < 0).sum()),
        "top_increases": top_inc,
        "top_decreases": top_dec,
    }


def _draw_region_boxes_and_cities(ax: plt.Axes, regions: Sequence[RegionSpec], show_labels: bool = True) -> None:
    """Overlay proposed study & reference boxes plus major landmark cities cleanly."""
    style_map = {
        "proposed_study_region": ("#B03A2E", "--", 1.35),
        "proposed_reference_region": ("#1B4F72", "-.", 1.35),
        "proposed_cross_layer_study_box": ("#7D3C98", "-", 1.35),
    }
    short_labels = {
        "donbas_kharkiv_east": "East Frontline\n(proposed study)",
        "south_steppe_belt": "South Steppe\n(proposed study)",
        "kyiv_north_belt": "North / Kyiv\n(proposed study)",
        "kyiv_no2_box": "Kyiv NO2 box",
        "central_interior_cand": "Central Interior\n(cand. ref: East/South)",
        "west_ukraine_cand": "West Ukraine\n(cand. ref: North/Kyiv)",
    }

    for reg in regions:
        if reg.role not in style_map:
            continue
        color, ls, lw = style_map[reg.role]
        rect = mpatches.Rectangle(
            (reg.west, reg.south),
            reg.east - reg.west,
            reg.north - reg.south,
            fill=False,
            edgecolor=color,
            linestyle=ls,
            linewidth=lw,
            zorder=5,
        )
        ax.add_patch(rect)
        if show_labels:
            if reg.region_id == "kyiv_no2_box":
                ax.annotate(
                    "Kyiv NO2 box",
                    xy=(reg.west, reg.north),
                    xytext=(reg.west - 2.6, reg.north + 0.55),
                    fontsize=6.8,
                    fontweight="bold",
                    color="#7D3C98",
                    arrowprops=dict(arrowstyle="->", color="#7D3C98", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="#D2B4DE", alpha=0.88),
                    zorder=8,
                )
            elif reg.region_id == "donbas_kharkiv_east":
                ax.text(
                    reg.east - 0.15,
                    reg.north - 0.14,
                    short_labels.get(reg.region_id, reg.region_id),
                    fontsize=6.9,
                    fontweight="bold",
                    color=color,
                    va="top",
                    ha="right",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.84),
                    zorder=7,
                )
            else:
                lx = reg.west + 0.20
                ly = reg.north - 0.16 if reg.region_id != "south_steppe_belt" else reg.south + 0.16
                va = "top" if reg.region_id != "south_steppe_belt" else "bottom"
                ax.text(
                    lx,
                    ly,
                    short_labels.get(reg.region_id, reg.region_id),
                    fontsize=6.9,
                    fontweight="bold",
                    color=color,
                    va=va,
                    ha="left",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.82),
                    zorder=7,
                )

    landmarks = [
        ("Kyiv", 30.52, 50.45, (10, -4)),
        ("Kharkiv", 36.23, 49.99, (-32, 4)),
        ("Donetsk", 37.80, 48.02, (-12, 6)),
        ("Mariupol", 37.55, 47.10, (-36, -9)),
        ("Kherson", 32.61, 46.64, (-12, 6)),
        ("Lviv", 24.03, 49.84, (4, 4)),
    ]
    for name, lon, lat, offset in landmarks:
        ax.scatter([lon], [lat], s=18, color="#17202A", marker="^", zorder=9)
        ax.annotate(
            name,
            xy=(lon, lat),
            xytext=offset,
            textcoords="offset points",
            fontsize=6.7,
            color="#17202A",
            fontweight="semibold",
            zorder=9,
        )


def plot_fire_location_map(
    clean_df: pd.DataFrame,
    grid_df: pd.DataFrame,
    regions: Sequence[RegionSpec],
    output_path: Path,
) -> Path:
    """
    Two-panel map:
    (A) 2022 FIRMS hotspot detection locations (type=0 landscape vs type=2 industrial),
    (B) 0.25-deg spatial shift (2022 minus 2019-2021 annual mean, type=0) with proposed study/reference boxes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 6.9), sharex=True, sharey=True)
    fig.patch.set_facecolor("white")

    # Panel A: 2022 raw detection scatter
    d22 = clean_df[clean_df["year"] == TARGET_YEAR]
    d22_t0 = d22[d22["type"] == 0]
    d22_t2 = d22[d22["type"] == 2]
    d22_t3 = d22[d22["type"] == 3]

    if not d22_t0.empty:
        ax1.scatter(
            d22_t0["longitude"],
            d22_t0["latitude"],
            s=3.5,
            alpha=0.22,
            color="#D35400",
            edgecolors="none",
            rasterized=True,
            label=f"2022 type=0 open/veg ({len(d22_t0):,})",
            zorder=2,
        )
    if not d22_t2.empty:
        ax1.scatter(
            d22_t2["longitude"],
            d22_t2["latitude"],
            s=8.0,
            alpha=0.55,
            color="#2E4053",
            edgecolors="none",
            rasterized=True,
            label=f"2022 type=2 static industrial ({len(d22_t2):,})",
            zorder=3,
        )
    if not d22_t3.empty:
        ax1.scatter(
            d22_t3["longitude"],
            d22_t3["latitude"],
            s=6.0,
            alpha=0.45,
            color="#1F618D",
            edgecolors="none",
            rasterized=True,
            label=f"2022 type=3 offshore ({len(d22_t3):,})",
            zorder=3,
        )

    _draw_region_boxes_and_cities(ax1, regions, show_labels=True)
    ax1.set_title("A. 2022 VIIRS Hotspot Detection Locations (Mar–Aug)", fontsize=10.8, fontweight="bold", pad=10)
    ax1.set_xlabel("Longitude (°E)", fontsize=9.5)
    ax1.set_ylabel("Latitude (°N)", fontsize=9.5)
    ax1.legend(loc="lower left", fontsize=7.6, frameon=True, facecolor="white", framealpha=0.92, markerscale=2.2)

    # Panel B: 0.25-deg spatial shift (2022 - baseline 2019-2021) for type=0
    if not grid_df.empty:
        deltas = grid_df["delta_2022_minus_baseline"].to_numpy(dtype=float)
        vmax = float(np.nanpercentile(np.abs(deltas), 98)) if len(deltas) > 0 else 50.0
        vmax = max(25.0, vmax)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
        sc = ax2.scatter(
            grid_df["grid_lon"],
            grid_df["grid_lat"],
            c=deltas,
            cmap="RdBu_r",
            norm=norm,
            marker="s",
            s=28,
            alpha=0.88,
            edgecolors="none",
            zorder=2,
        )
        cbar = fig.colorbar(sc, ax=ax2, fraction=0.042, pad=0.02, extend="both")
        cbar.set_label("type=0 det. shift (2022 minus 2019–2021 mean / 0.25° cell)", fontsize=8.3)
        cbar.ax.tick_params(labelsize=8)

    _draw_region_boxes_and_cities(ax2, regions, show_labels=False)
    # Add short legend for boxes on Panel B
    box_handles = [
        mpatches.Patch(edgecolor="#B03A2E", facecolor="none", linestyle="--", linewidth=1.4, label="Proposed study region"),
        mpatches.Patch(edgecolor="#1B4F72", facecolor="none", linestyle="-.", linewidth=1.4, label="Proposed candidate reference"),
        mpatches.Patch(edgecolor="#7D3C98", facecolor="none", linestyle="-", linewidth=1.4, label="Kyiv NO2 matched box"),
    ]
    ax2.legend(handles=box_handles, loc="lower left", fontsize=7.6, frameon=True, facecolor="white", framealpha=0.92)
    ax2.set_title("B. Geographic Shift: 2022 vs. 2019–2021 Baseline (type=0)", fontsize=10.8, fontweight="bold", pad=10)
    ax2.set_xlabel("Longitude (°E)", fontsize=9.5)

    for ax in (ax1, ax2):
        ax.set_xlim(21.7, 40.6)
        ax.set_ylim(44.1, 52.7)
        ax.set_aspect(1.0 / np.cos(np.radians(48.5)))
        ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.45)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Ukraine Satellite Active-Fire Detections — Spatial Footprint & 2022 Shift (VIIRS S-NPP SV-C2, Mar–Aug)",
        fontsize=12.4,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.015,
        0.012,
        (
            "Source: NASA FIRMS Suomi NPP VIIRS Archive (SV-C2, 375 m pixel centers) | Counts reflect hotspot detections (repeated overpasses/clusters), NOT unique fires or burned hectares.\n"
            "Note: Proposed sub-regions are exploratory candidates pending team agreement; 2022 excludes 16 zero-detection satellite dates (2022-03-05 and 2022-07-27..08-10 S-NPP outage)."
        ),
        fontsize=7.5,
        color="#566573",
        linespacing=1.35,
    )
    plt.tight_layout(rect=[0, 0.055, 1, 0.935])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_fire_monthly_comparison(
    monthly_df: pd.DataFrame,
    reg_comp: Dict[str, object],
    comp_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """
    Two-panel comparison visual:
    (A) National Ukraine monthly type=0 detections (2022 vs. 2019-2021 min-max range & individual years) + outage rate,
    (B) Regional divergence across proposed study & candidate reference zones (Mar-Aug vs. May-Aug 2022 vs. 2019-2021).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 6.6), gridspec_kw={"width_ratios": [1.1, 1.05]})
    fig.patch.set_facecolor("white")

    # Panel A: Monthly national type=0 trajectory
    nat0 = monthly_df[(monthly_df["region_id"] == "ukraine_national") & (monthly_df["filter_mode"] == "type0_vegetation_all_conf")]
    piv = nat0.pivot(index="calendar_month", columns="year", values="detections").reindex(STUDY_MONTHS)
    x = np.arange(len(STUDY_MONTHS))
    m_labels = [MONTH_ABBR[m] for m in STUDY_MONTHS]

    base_mat = piv[[2019, 2020, 2021]].to_numpy(dtype=float) / 1000.0
    base_mean = np.mean(base_mat, axis=1)
    base_min = np.min(base_mat, axis=1)
    base_max = np.max(base_mat, axis=1)
    y22 = piv[2022].to_numpy(dtype=float) / 1000.0
    y21 = piv[2021].to_numpy(dtype=float) / 1000.0

    # Active-day scaled equivalent (31 days * rate_per_observed_day) for July & August 2022 outage transparency
    nat_22 = nat0[nat0["year"] == 2022].set_index("calendar_month").reindex(STUDY_MONTHS)
    obs_days = nat_22["satellite_observed_days"].to_numpy(dtype=float)
    cal_days = nat_22["calendar_days"].to_numpy(dtype=float)
    y22_rate_scaled = (nat_22["detections_per_observed_day"].to_numpy(dtype=float) * cal_days) / 1000.0

    ax1.fill_between(
        x,
        base_min,
        base_max,
        color="#D6EAF8",
        alpha=0.60,
        label="2019–2021 min–max range (variability, not CI)",
        zorder=1,
    )
    ax1.plot(x, base_mean, color="#1F618D", linestyle="--", linewidth=1.8, marker="o", markersize=4.5, label="2019–2021 baseline mean", zorder=3)
    ax1.plot(x, y21, color="#5D6D7E", linestyle=":", linewidth=1.5, marker="^", markersize=4.5, label="2021 prior year (low-fire year)", zorder=3)
    ax1.plot(x, y22, color="#C0392B", linewidth=2.3, marker="o", markersize=6.0, label="2022 observed detections (type=0)", zorder=5)

    # Show July & August 2022 rate-normalized equivalent (accounting for 26/31d and 21/31d S-NPP outage)
    ax1.plot(
        [3, 4, 5],
        y22_rate_scaled[3:],
        color="#C0392B",
        linestyle="--",
        linewidth=1.3,
        marker="s",
        markersize=5.0,
        markerfacecolor="white",
        label="2022 active-day rate x calendar days (Jul 26/31d, Aug 21/31d)",
        zorder=4,
    )

    ax1.annotate(
        "S-NPP outage:\nJul 27–Aug 10 missing\n(Aug 21/31 obs. days)",
        xy=(5, y22[5]),
        xytext=(3.2, 16.2),
        fontsize=7.6,
        color="#922B21",
        fontweight="semibold",
        arrowprops=dict(arrowstyle="->", color="#922B21", lw=1.0),
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#FDEDEC", edgecolor="#E6B0AA", alpha=0.92),
        zorder=7,
    )
    ax1.annotate(
        f"Apr 2020 spring &\nwildfire spike ({base_max[1]:.1f}k)",
        xy=(1, base_max[1]),
        xytext=(0.08, 25.8),
        fontsize=7.5,
        color="#1F618D",
        arrowprops=dict(arrowstyle="->", color="#1F618D", lw=0.9),
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#AED6F1", alpha=0.92),
        zorder=6,
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels(m_labels)
    ax1.set_ylabel("Ukraine Monthly Detections (thousands, type=0)", fontsize=9.8)
    ax1.set_title("A. Ukraine National Monthly Detections (type=0 open fire)", fontsize=10.5, fontweight="bold", pad=10)
    ax1.set_ylim(0, max(float(np.max(base_max)), float(np.max(y22))) * 1.26)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=7.2, frameon=True, facecolor="white", framealpha=0.94)

    # Panel B: Proposed regional % change vs. 2019-2021 (Mar-Aug & May-Aug, counts)
    # Ordered from bottom (y=0: East positive) to top (y=6: Central negative) so upper-right and lower-left stay clean
    order = [
        ("donbas_kharkiv_east", "East Frontline\n(Study prop.)"),
        ("kyiv_no2_box", "Kyiv NO2 Box\n(Study cross-layer)"),
        ("south_steppe_belt", "South Steppe\n(Study prop.)"),
        ("ukraine_national", "Ukraine National\n(Aggregate type=0)"),
        ("west_ukraine_cand", "West Ukraine\n(Ref cand.: North, r=0.89)"),
        ("kyiv_north_belt", "North / Kyiv\n(Study prop.)"),
        ("central_interior_cand", "Central Interior\n(Ref cand.: East, r=0.81)"),
    ]

    comp_idx = comp_df[comp_df["filter_mode"] == "type0_vegetation_all_conf"].set_index(["region_id", "window_id"])
    y_pos = np.arange(len(order))
    mar_aug_vals = [float(comp_idx.loc[(rid, "mar_aug"), "pct_change_vs_2019_2021"]) for rid, _ in order]
    may_aug_vals = [float(comp_idx.loc[(rid, "may_aug"), "pct_change_vs_2019_2021"]) for rid, _ in order]

    h = 0.36
    bars1 = ax2.barh(y_pos + h / 2.0, mar_aug_vals, height=h, color="#C0392B", alpha=0.86, edgecolor="#2C3E50", linewidth=0.6, label="Mar–Aug 2022 vs. 2019–2021 (%)")
    bars2 = ax2.barh(y_pos - h / 2.0, may_aug_vals, height=h, color="#E67E22", alpha=0.82, edgecolor="#2C3E50", linewidth=0.6, label="May–Aug 2022 vs. 2019–2021 (excl. Mar–Apr burns)")
    ax2.axvline(0.0, color="#2C3E50", linewidth=1.1)

    for b in list(bars1) + list(bars2):
        w = b.get_width()
        xpos = w + 1.8 if w >= 0 else w - 1.8
        ha = "left" if w >= 0 else "right"
        ax2.text(xpos, b.get_y() + b.get_height() / 2.0, f"{w:+.1f}%", va="center", ha=ha, fontsize=7.6, fontweight="bold", color="#1B2631")

    # Place industrial type=2 callout cleanly in bottom-left empty quadrant (East bars extend right)
    nat_t2 = reg_comp["ukraine_national"]["type2_static_industrial"]["mar_aug"]["vs_baseline_2019_2021"]["detections_pct_change"]
    ax2.text(
        0.02,
        0.03,
        f"Excluded here: FIRMS type=2\nstatic industrial sources changed\n{nat_t2:+.1f}% nationwide in 2022\n(e.g., Mariupol/Kryvyi Rih).",
        transform=ax2.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.1,
        color="#34495E",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#F4F6F7", edgecolor="#BDC3C7", alpha=0.95),
    )

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([lbl for _, lbl in order], fontsize=8.3)
    ax2.set_xlabel("% Change in type=0 Hotspot Detections (2022 vs. 2019–2021 Mean)", fontsize=9.3)
    ax2.set_title("B. Regional Divergence Under Proposed Study vs. Reference Zones", fontsize=10.5, fontweight="bold", pad=10)
    min_x = min(min(mar_aug_vals), min(may_aug_vals))
    max_x = max(max(mar_aug_vals), max(may_aug_vals))
    ax2.set_xlim(min_x - 36.0, max_x + 36.0)
    ax2.set_ylim(-0.75, len(order) + 0.55)
    ax2.grid(axis="x", linestyle="--", alpha=0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper right", fontsize=7.2, frameon=True, facecolor="white", framealpha=0.95)

    fig.suptitle(
        "Ukraine Active-Fire Monthly Activity & Sub-Regional Divergence (VIIRS S-NPP SV-C2, 2019–2022)",
        fontsize=12.4,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.015,
        0.012,
        (
            "Source: NASA FIRMS SV-C2 (satellite=SNPP, version=2) | Counts are 375 m hotspot detections (not fires/burned area); national totals hide strong regional divergence.\n"
            "Note: Before/after statistical significance is NOT assessed (n=1 post-invasion season, clustered pixel detections, and 16-day 2022 S-NPP outage); weather controls omitted."
        ),
        fontsize=7.5,
        color="#566573",
        linespacing=1.35,
    )
    plt.tight_layout(rect=[0, 0.055, 1, 0.93])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def run_fire_analysis(
    input_paths: Optional[Sequence[Path]] = None,
    raw_dir: Path = DEFAULT_FIRE_RAW_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
) -> Dict[str, object]:
    """Run complete FIRMS VIIRS validation, regional comparison, comparability, plots, and strict JSON export."""
    resolved_inputs = list(input_paths) if input_paths is not None else discover_fire_inputs(raw_dir)
    clean_df, quality_report = load_and_validate_firms_archives(resolved_inputs)
    repeated_summary = summarize_repeated_detections(clean_df)

    sat_cov_df = compute_satellite_month_coverage(clean_df)
    monthly_df = compute_monthly_fire_table(clean_df, sat_cov_df)
    comp_df, reg_comp = compute_regional_comparisons(monthly_df)
    comparability_df, comparability_rows = assess_pre2022_comparability(monthly_df)
    grid_df, spatial_shifts = compute_spatial_grid_shifts(clean_df)

    reports_dir.mkdir(parents=True, exist_ok=True)
    monthly_csv_path = reports_dir / "fire_monthly.csv"
    comp_csv_path = reports_dir / "fire_regional_summary.csv"
    comparability_csv_path = reports_dir / "fire_comparability_matrix.csv"
    quality_json_path = reports_dir / "fire_quality.json"
    fire_json_path = reports_dir / "fire_viirs_results.json"
    map_png_path = reports_dir / "fire_location_map.png"
    monthly_png_path = reports_dir / "fire_monthly_comparison.png"

    monthly_df.to_csv(monthly_csv_path, index=False)
    comp_df.to_csv(comp_csv_path, index=False)
    comparability_df.to_csv(comparability_csv_path, index=False)

    plot_fire_location_map(clean_df, grid_df, PROPOSED_REGIONS, map_png_path)
    plot_fire_monthly_comparison(monthly_df, reg_comp, comp_df, monthly_png_path)

    quality_payload = dict(quality_report)
    quality_payload["repeated_detections"] = repeated_summary
    quality_json_path.write_text(json.dumps(quality_payload, indent=2, allow_nan=False, ensure_ascii=False), encoding="utf-8")

    # Confidence sensitivity ratio across clean data (n+h vs all conf on type=0)
    conf_sens: Dict[str, object] = {}
    for yr in sorted(clean_df["year"].unique()):
        sub0 = clean_df[(clean_df["year"] == yr) & (clean_df["type"] == 0)]
        n_all = int(len(sub0))
        n_nh = int(sub0["confidence"].isin(["n", "h"]).sum())
        n_h = int((sub0["confidence"] == "h").sum())
        conf_sens[str(int(yr))] = {
            "type0_all_conf": n_all,
            "type0_nominal_high": n_nh,
            "type0_high_only": n_h,
            "nominal_high_share": round(n_nh / float(n_all), 4) if n_all > 0 else None,
        }

    # Build monthly national + key proposed regions records for JSON
    monthly_records = [
        {
            "month": str(r.month),
            "year": int(r.year),
            "calendar_month": int(r.calendar_month),
            "region_id": str(r.region_id),
            "filter_mode": str(r.filter_mode),
            "detections": int(r.detections),
            "satellite_observed_days": int(r.satellite_observed_days),
            "calendar_days": int(r.calendar_days),
            "satellite_coverage_fraction": float(r.satellite_coverage_fraction),
            "detections_per_observed_day": _clean_float(r.detections_per_observed_day, 4),
            "unique_0_01deg_cell_days": int(r.unique_0_01deg_cell_days),
            "day_detections": int(r.day_detections),
            "night_detections": int(r.night_detections),
            "frp_sum_mw": _clean_float(r.frp_sum_mw, 2),
            "frp_median_mw": _clean_float(r.frp_median_mw, 2),
        }
        for r in monthly_df.itertuples(index=False)
    ]

    cov_2022 = quality_report["temporal_coverage_by_year"].get("2022", {})
    missing_2022 = cov_2022.get("missing_dates", [])

    fire_results: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": {
            "overall": "validated_descriptive_with_limitations",
            "archive_verification": "validated_all_four_years_mar_aug_2019_2022",
            "coordinate_and_time_validation": "validated",
            "deduplication": "validated",
            "proposed_region_agreement": "proposed_pending_team_agreement",
            "before_after_significance": "not_assessed",
            "causal_attribution": "not_established",
        },
        "dataset": {
            "provider": quality_report["product"]["provider"],
            "product": quality_report["product"]["nominal_sensor"],
            "archive_series": quality_report["product"]["archive_series"],
            "satellites_observed": quality_report["product"]["satellite"],
            "instruments_observed": quality_report["product"]["instrument"],
            "versions_observed": quality_report["product"]["version"],
            "units": "hotspot_detections (375 m VIIRS pixel-center thermal anomalies per overpass)",
            "unit_caveat": (
                "Counts represent satellite hotspot detections (repeated overpasses and multi-pixel clusters included), "
                "NEVER unique fires, forest loss area, or burned hectares."
            ),
            "study_months": [MONTH_ABBR[m] for m in STUDY_MONTHS],
            "study_years": list(STUDY_YEARS),
            "observed_extent": quality_report["observed_extent"],
            "files_verified": [
                {
                    "archive_file": f["archive_file"],
                    "archive_sha256": f["archive_sha256"],
                    "csv_member": f["csv_member"],
                    "csv_sha256": f["csv_sha256"],
                    "raw_row_count": f["raw_row_count"],
                    "date_min": f["date_min"],
                    "date_max": f["date_max"],
                }
                for f in quality_report["files_verified"]
            ],
        },
        "quality_summary": {
            "accounting": quality_report["accounting"],
            "validation_checks": quality_report["validation_checks"],
            "classification_breakdown": quality_report["classification_breakdown"],
            "confidence_filtering_sensitivity": conf_sens,
        },
        "missing_observation_gaps": {
            "2019_missing_dates_count": quality_report["temporal_coverage_by_year"]["2019"]["missing_dates_count"],
            "2020_missing_dates_count": quality_report["temporal_coverage_by_year"]["2020"]["missing_dates_count"],
            "2021_missing_dates_count": quality_report["temporal_coverage_by_year"]["2021"]["missing_dates_count"],
            "2022_missing_dates_count": len(missing_2022),
            "2022_missing_dates": missing_2022,
            "satellite_month_coverage": sat_cov_df.to_dict(orient="records"),
            "gap_explanation": (
                "All 184 Mar-Aug dates exist in 2019, 2020, and 2021. In 2022, 16 dates have zero detections "
                "across all of Ukraine: 2022-03-05 (1 day) and a continuous 15-day blackout from 2022-07-27 through "
                "2022-08-10 aligning with the documented NASA Suomi NPP spacecraft anomaly/outage. Because August 2022 "
                "contains only 21/31 observed days (and July 26/31), raw 2022 late-summer counts understate activity "
                "and must be read alongside detections_per_observed_day."
            ),
        },
        "repeated_detections_summary": repeated_summary,
        "proposed_regions": [
            {
                "region_id": r.region_id,
                "name": r.name,
                "role": r.role,
                "bounding_box": {"south": r.south, "north": r.north, "west": r.west, "east": r.east},
                "description": r.description,
                "agreement_status": "proposed_pending_team_agreement" if r.region_id != "ukraine_national" else "full_country_export",
            }
            for r in PROPOSED_REGIONS
        ],
        "pre_2022_comparability": comparability_rows,
        "regional_comparisons": reg_comp,
        "spatial_shift_highlights": spatial_shifts,
        "monthly_series": monthly_records,
        "statistics": {
            "before_after_seasonal_inference": {
                "status": "not_assessed",
                "p_value": None,
                "ci_95_lower": None,
                "ci_95_upper": None,
                "statistical_significance_claimed": False,
                "reasons_not_assessed": [
                    "Only n = 1 post-invasion season (March-August 2022) is observed across 3 baseline years (2019-2021).",
                    "Satellite hotspot pixels exhibit strong spatial and temporal clustering (repeated multi-day detections over single burning areas or static plants), invalidating independent-event Poisson/t-test p-values.",
                    "2022 contains a 16-day observation blackout (Jul 27 - Aug 10 S-NPP outage + Mar 05), breaking equal seasonal exposure.",
                    "No meteorological covariates (drought/VPD, wind, temperature, cloud fraction) or external validated controls are included to isolate conflict from weather or agricultural burning shifts.",
                ],
            }
        },
        "charts": {
            "detection_location_map": {
                "png_path": "reports/fire_location_map.png",
                "data_source": "clean FIRMS SV-C2 detections + 0.25-deg grid shifts",
            },
            "monthly_and_regional_comparison": {
                "png_path": "reports/fire_monthly_comparison.png",
                "monthly_csv_path": "reports/fire_monthly.csv",
                "regional_csv_path": "reports/fire_regional_summary.csv",
                "comparability_csv_path": "reports/fire_comparability_matrix.csv",
            },
        },
        "limitations": [
            "Hotspot counts measure 375 m pixel-center thermal anomalies per overpass, NOT number of fires, forest loss area, or burned hectares.",
            "Repeated detections (~30-38% of 0.01-deg cells have multiple detections) amplify slow-moving or persistent sources across swath overlaps and day/night overpasses.",
            "FIRMS type=2 static industrial detections (steelworks/flares, e.g., Mariupol & Kryvyi Rih) plunged -77.5% in 2022; including type=2 mixes industrial shutdowns with open fires.",
            "Suomi NPP suffered a 15-day outage (2022-07-27 to 2022-08-10; plus zero detections on 2022-03-05), reducing August 2022 to 21/31 observed days.",
            "Proposed study/reference boxes inside Ukraine are candidates for team agreement and are NOT validated causal controls; pre-2022 fire regimes differ sharply between Western/Northern spring burning and Eastern/Southern summer steppe burning.",
            "No meteorological controls (drought, soil moisture, temperature, cloud obstruction) or causal attribution models are included.",
        ],
        "reproducibility": {
            "regenerate_all_command": "python -m src.fire_analysis",
            "test_command": "python -m unittest discover -s tests -v",
            "schema_doc": "docs/fire-results-schema.md",
            "methods_doc": "docs/fire-methods.md",
            "findings_doc": "docs/fire-findings.md",
        },
    }

    fire_json_path.write_text(json.dumps(fire_results, indent=2, allow_nan=False, ensure_ascii=False), encoding="utf-8")
    return fire_results


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run FIRMS VIIRS S-NPP fire ingestion, verification, plots, and backend JSON export.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_FIRE_RAW_DIR, help="Directory holding FIRMS .zip/.csv files")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Output directory for CSV, JSON, PNG")
    args = parser.parse_args(list(argv) if argv is not None else None)

    res = run_fire_analysis(raw_dir=args.raw_dir, reports_dir=args.reports_dir)
    nat_all = res["regional_comparisons"]["ukraine_national"]["all_types_all_conf"]["mar_aug"]["vs_baseline_2019_2021"]
    nat_t0 = res["regional_comparisons"]["ukraine_national"]["type0_vegetation_all_conf"]["mar_aug"]["vs_baseline_2019_2021"]
    east_t0 = res["regional_comparisons"]["donbas_kharkiv_east"]["type0_vegetation_all_conf"]["mar_aug"]["vs_baseline_2019_2021"]
    print(f"Fire/VIIRS analysis complete ({res['quality_summary']['accounting']['clean_rows_retained']:,} clean detections):")
    print(f"  Ukraine all-types 2022 vs 2019-2021: {nat_all['detections_pct_change']:+.2f}% (rate/day: {nat_all['rate_per_day_pct_change']:+.2f}%)")
    print(f"  Ukraine type=0    2022 vs 2019-2021: {nat_t0['detections_pct_change']:+.2f}% (rate/day: {nat_t0['rate_per_day_pct_change']:+.2f}%)")
    print(f"  East Frontline t0 2022 vs 2019-2021: {east_t0['detections_pct_change']:+.2f}% (rate/day: {east_t0['rate_per_day_pct_change']:+.2f}%)")
    print(f"  Missing 2022 dates: {res['missing_observation_gaps']['2022_missing_dates_count']} | Stats: {res['statistics']['before_after_seasonal_inference']['status']}")
    print(f"  Exported JSON, CSVs, and 2 PNGs to {args.reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
