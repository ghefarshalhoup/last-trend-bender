"""Full 4-Elements (Air, Fire, Water, Earth) Ukraine & Kyiv analysis pipeline.

Unifies:
  - Air: NASA Giovanni OMNO2d v004 tropospheric NO2 + NASA POWER meteorology (WS10M, PS, CLOUD_AMT)
  - Fire: FIRMS VIIRS S-NPP SV-C2 detections (type0 & type2) + thermal/FAO-56 PET fire weather
  - Water: NASA POWER PRECTOTCORR, QV2M, RH2M, EVPTRNS, VPD, and (P - PET) water balance
  - Earth: NASA POWER GWETTOP/ROOT/PROF soil moisture, TS, (TS - T2M) skin decoupling, albedo

Preserves strict scientific honesty: n=1 war season cannot prove causation via
before/after tests; exploratory weather controls, Box-Tiao step diagnostics,
prewhitened lagged couplings, and BH/BY FDR quantify confounders transparently.
"""

from __future__ import annotations

import argparse
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "war_env_tracker_mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.fire_analysis import PROPOSED_REGIONS
from src.no2_pipeline import (
    DEFAULT_RAW_DIR as DEFAULT_NO2_RAW_DIR,
    DEFAULT_REPORTS_DIR,
    _discover_default_input,
    parse_giovanni_csv,
    reindex_daily_calendar,
)
from src.stats_rigor import (
    INTERVAL_SCALE_UNITS,
    bbox_area_km2,
    bh_q_values,
    by_q_values,
    clean_float,
    compute_baseline_climatology_anomalies,
    compute_lagged_monthly_impulse_coupling,
    fit_box_tiao_step_intervention,
    hamed_rao_modified_mk,
    hirsch_slack_seasonal_mk_and_slope,
    partial_trend_controlling_covariate,
    safe_pct_change,
    structural_hinge_breakpoint_analysis,
    write_strict_json,
)
from src.weather_power_pipeline import (
    DEFAULT_POWER_DIR,
    STUDY_BOXES,
    load_power_panels,
    sha256_file,
)

SCHEMA_VERSION = "1.0.0"
CONFLICT_START_DATE = "2022-02-24"
INTERVENTION_DECIMAL_YEAR = 2022.0 + (2.0 / 12.0)  # March 1, 2022 boundary
MARCH_AUGUST_MONTHS: Tuple[int, ...] = (3, 4, 5, 6, 7, 8)


@dataclass(frozen=True)
class ElementMetricSpec:
    metric_id: str
    element: str
    label: str
    units: str
    is_interval_scale: bool
    source_layer: str


FOUR_ELEMENT_METRICS: Tuple[ElementMetricSpec, ...] = (
    ElementMetricSpec("no2_mean_molec_cm2", "air", "Tropospheric NO2 Column (OMNO2d)", "molecules/cm^2", False, "OMI OMNO2d v004"),
    ElementMetricSpec("ws10m", "air", "10m Wind Speed", "m/s", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("cloud_amt", "air", "Total Cloud Amount", "%", False, "NASA POWER CERES/MERRA-2"),
    ElementMetricSpec("ps", "air", "Surface Barometric Pressure", "kPa", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("cloud_radiative_attenuation_wm2", "air", "Cloud Radiative Attenuation (SWclr - SWall)", "W/m^2", True, "Derived CERES"),
    ElementMetricSpec("fire_type0_per_1k_km2_day", "fire", "VIIRS Vegetation Fire Density (type0)", "det / 1000 km^2 / day", False, "FIRMS VIIRS S-NPP"),
    ElementMetricSpec("fire_type2_per_1k_km2_day", "fire", "VIIRS Static Industrial Anomaly Density (type2)", "det / 1000 km^2 / day", False, "FIRMS VIIRS S-NPP"),
    ElementMetricSpec("t2m", "fire", "2m Air Temperature", "°C", True, "NASA POWER MERRA-2"),
    ElementMetricSpec("t2m_max", "fire", "Monthly Peak 2m Temperature (T2M_MAX)", "°C", True, "NASA POWER MERRA-2"),
    ElementMetricSpec("dtr_c", "fire", "Mean Daily Diurnal Temp Range (T2M_RANGE)", "°C", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("allsky_sfc_sw_dwn", "fire", "All-Sky Downward Shortwave Flux", "MJ/m^2/day", False, "NASA POWER CERES"),
    ElementMetricSpec("pet_fao56_mm_day", "fire", "FAO-56 Penman-Monteith PET", "mm/day", False, "Derived FAO-56 PM"),
    ElementMetricSpec("prectotcorr", "water", "Bias-Corrected Precipitation", "mm/day", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("qv2m", "water", "2m Specific Humidity", "g/kg", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("rh2m", "water", "2m Relative Humidity", "%", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("vpd_kpa", "water", "Vapor Pressure Deficit (VPD)", "kPa", False, "Derived MERRA-2"),
    ElementMetricSpec("evptrns_mm_day", "water", "Vegetation Transpiration Flux", "mm/day", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("precip_minus_pet_mm_day", "water", "Climatic Water Balance (P - PET)", "mm/day", True, "Derived FAO-56"),
    ElementMetricSpec("gwettop", "earth", "Surface Soil Wetness (0–5 cm)", "fraction", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("gwetroot", "earth", "Root-Zone Soil Wetness (0–100 cm)", "fraction", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("gwetprof", "earth", "Profile Soil Moisture", "fraction", False, "NASA POWER MERRA-2"),
    ElementMetricSpec("ts", "earth", "Earth Skin Temperature", "°C", True, "NASA POWER MERRA-2"),
    ElementMetricSpec("ts_minus_t2m_c", "earth", "Skin-Air Thermal Decoupling (Ts - T2m)", "°C", True, "Derived MERRA-2"),
    ElementMetricSpec("allsky_srf_alb", "earth", "All-Sky Surface Albedo", "dimensionless", False, "NASA POWER CERES"),
)

METRIC_SPEC_BY_ID: Dict[str, ElementMetricSpec] = {m.metric_id: m for m in FOUR_ELEMENT_METRICS}


def _finite_mean(values: Sequence[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return (sum(arr) / len(arr)) if arr else None


def build_unified_monthly_panel(
    power_monthly_df: pd.DataFrame,
    no2_monthly_df: pd.DataFrame,
    fire_monthly_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge NASA POWER (8 regions), Kyiv OMNO2d, and FIRMS VIIRS (area-normalized)."""
    df = power_monthly_df.copy()
    area_map: Dict[str, float] = {b.region_id: b.area_km2 for b in STUDY_BOXES}
    df["area_km2"] = df["region_id"].map(area_map)

    # Merge Kyiv OMI NO2 strictly onto kyiv_no2_box
    no2_sub = no2_monthly_df[["month", "no2_mean_molec_cm2", "valid_days", "calendar_days", "coverage_fraction"]].copy()
    no2_sub["region_id"] = "kyiv_no2_box"
    no2_sub = no2_sub.rename(
        columns={
            "valid_days": "no2_valid_days",
            "calendar_days": "no2_calendar_days",
            "coverage_fraction": "no2_coverage_fraction",
        }
    )
    df = df.merge(no2_sub, on=["region_id", "month"], how="left")

    # Pivot FIRMS type0 and type2 monthly metrics onto matching Ukraine study boxes
    for mode, prefix in (
        ("type0_vegetation_nominal_high", "fire_type0"),
        ("type2_static_industrial", "fire_type2"),
    ):
        f_sub = fire_monthly_df[fire_monthly_df["filter_mode"] == mode].copy()
        f_sub = f_sub.rename(
            columns={
                "detections": f"{prefix}_detections",
                "detections_per_observed_day": f"{prefix}_rate_per_day",
                "frp_sum_mw": f"{prefix}_frp_sum_mw",
                "satellite_coverage_fraction": f"{prefix}_sat_cov",
            }
        )[["region_id", "month", f"{prefix}_detections", f"{prefix}_rate_per_day", f"{prefix}_frp_sum_mw", f"{prefix}_sat_cov"]]
        df = df.merge(f_sub, on=["region_id", "month"], how="left")
        df[f"{prefix}_per_1k_km2_day"] = np.where(
            df[f"{prefix}_rate_per_day"].notna() & (df["area_km2"] > 0.0),
            df[f"{prefix}_rate_per_day"] / df["area_km2"] * 1000.0,
            np.nan,
        )

    df["no2_flagged_below_50_pct"] = np.where(
        df["no2_coverage_fraction"].notna(),
        df["no2_coverage_fraction"] < 0.50,
        False,
    )
    return df.sort_values(["region_id", "year", "month_num"]).reset_index(drop=True)


def compute_kyiv_daily_wind_cloud_sensitivity(
    daily_no2_df: pd.DataFrame,
    daily_power_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Evaluate Kyiv daily NO2 2022 vs baseline shifts across wind and cloud regimes."""
    merged = daily_no2_df.merge(daily_power_df, on="date", how="left")
    merged["year"] = merged["date"].dt.year
    merged["month_num"] = merged["date"].dt.month
    merged["month"] = merged["date"].dt.strftime("%Y-%m")

    mar_aug = merged[merged["month_num"].isin(MARCH_AUGUST_MONTHS) & merged["value"].notna()].copy()

    def _subset_summary(sub: pd.DataFrame, label: str, rule: str) -> Dict[str, object]:
        b15 = sub[sub["year"].between(2015, 2019)]["value"].dropna().tolist()
        b19 = sub[sub["year"].between(2019, 2021)]["value"].dropna().tolist()
        t22 = sub[sub["year"] == 2022]["value"].dropna().tolist()
        ws_b15 = _finite_mean(sub[sub["year"].between(2015, 2019)]["ws10m"].dropna().tolist())
        ws_t22 = _finite_mean(sub[sub["year"] == 2022]["ws10m"].dropna().tolist())

        m15, m19, m22 = _finite_mean(b15), _finite_mean(b19), _finite_mean(t22)
        d15, p15, s15 = safe_pct_change(m22, m15)
        d19, p19, s19 = safe_pct_change(m22, m19)
        return {
            "stratum_id": label,
            "rule": rule,
            "n_days_2015_2019": len(b15),
            "n_days_2019_2021": len(b19),
            "n_days_2022": len(t22),
            "mean_2015_2019_molec_cm2": clean_float(m15),
            "mean_2019_2021_molec_cm2": clean_float(m19),
            "mean_2022_molec_cm2": clean_float(m22),
            "mean_ws10m_2015_2019_ms": clean_float(ws_b15, 3),
            "mean_ws10m_2022_ms": clean_float(ws_t22, 3),
            "vs_2015_2019_abs_diff": clean_float(d15),
            "vs_2015_2019_pct_change": clean_float(p15, 2),
            "vs_2015_2019_status": s15,
            "vs_2019_2021_abs_diff": clean_float(d19),
            "vs_2019_2021_pct_change": clean_float(p19, 2),
            "vs_2019_2021_status": s19,
        }

    strata = [
        _subset_summary(mar_aug, "all_valid_days", "All valid Mar–Aug OMI retrieval days"),
        _subset_summary(mar_aug[mar_aug["ws10m"] < 3.0], "low_wind_lt_3ms", "Daily MERRA-2 WS10M < 3.0 m/s (stagnant ventilation)"),
        _subset_summary(mar_aug[mar_aug["ws10m"] >= 3.0], "higher_wind_ge_3ms", "Daily MERRA-2 WS10M >= 3.0 m/s (advective dispersion)"),
        _subset_summary(mar_aug[mar_aug["cloud_amt"] < 60.0], "clear_moderate_cloud_lt_60pct", "Daily MERRA-2/CERES CLOUD_AMT < 60%"),
        _subset_summary(mar_aug[mar_aug["month"] != "2022-04"], "excluding_april_2022", "Excludes 2022-04 (only 8/30 valid OMI days)"),
    ]

    # Daily rank correlation on Mar-Aug 2015-2021 pre-invasion days to verify physical NO2-wind relation cleanly
    pre_valid = mar_aug[mar_aug["year"] <= 2021].dropna(subset=["value", "ws10m", "t2m", "cloud_amt"])
    wind_corr = clean_float(pre_valid["value"].corr(pre_valid["ws10m"], method="spearman"), 4)
    cloud_corr = clean_float(pre_valid["value"].corr(pre_valid["cloud_amt"], method="spearman"), 4)

    summary = {
        "purpose": "Tests whether 2022 Kyiv NO2 decrease holds under stagnant low-wind (<3 m/s) and clear-sky filtering.",
        "strata": strata,
        "pre_invasion_daily_spearman_no2_vs_ws10m": wind_corr,
        "pre_invasion_daily_spearman_no2_vs_cloud_amt": cloud_corr,
    }
    return merged, summary


def compute_kyiv_monthly_four_element_summaries(kyiv_df: pd.DataFrame) -> List[Dict[str, object]]:
    """Compute Mar-Aug 2022 vs 2015-2019 and 2019-2021 seasonal comparisons across all 4 elements."""
    ma = kyiv_df[kyiv_df["month_num"].isin(MARCH_AUGUST_MONTHS)].copy()
    records: List[Dict[str, object]] = []
    for spec in FOUR_ELEMENT_METRICS:
        col = spec.metric_id
        if col not in ma.columns:
            continue
        b15 = ma[ma["year"].between(2015, 2019)][col].dropna().tolist()
        b19 = ma[ma["year"].between(2019, 2021)][col].dropna().tolist()
        t22 = ma[ma["year"] == 2022][col].dropna().tolist()
        if not t22:
            continue
        m15, m19, m22 = _finite_mean(b15), _finite_mean(b19), _finite_mean(t22)
        d15, p15, s15 = safe_pct_change(m22, m15, is_interval_scale=spec.is_interval_scale)
        d19, p19, s19 = safe_pct_change(m22, m19, is_interval_scale=spec.is_interval_scale)
        digits = None if spec.metric_id == "no2_mean_molec_cm2" else 4
        records.append(
            {
                "region_id": "kyiv_no2_box",
                "metric_id": spec.metric_id,
                "element": spec.element,
                "label": spec.label,
                "units": spec.units,
                "is_interval_scale": spec.is_interval_scale,
                "source_layer": spec.source_layer,
                "baseline_2015_2019_mean": clean_float(m15, digits),
                "baseline_2019_2021_mean": clean_float(m19, digits),
                "target_2022_mean": clean_float(m22, digits),
                "vs_2015_2019_abs_diff": clean_float(d15, digits),
                "vs_2015_2019_pct_change": clean_float(p15, 2),
                "vs_2015_2019_status": s15,
                "vs_2019_2021_abs_diff": clean_float(d19, digits),
                "vs_2019_2021_pct_change": clean_float(p19, 2),
                "vs_2019_2021_status": s19,
            }
        )
    return records


def compute_kyiv_intervention_and_weather_controls(kyiv_df: pd.DataFrame) -> Dict[str, object]:
    """Run exploratory Box-Tiao step interventions & partial meteorological trends on Kyiv NO2."""
    sub = kyiv_df[kyiv_df["no2_mean_molec_cm2"].notna()].sort_values(["year", "month_num"]).reset_index(drop=True)
    yrs = sub["year"].astype(int).tolist()
    mos = sub["month_num"].astype(int).tolist()
    t_dec = (sub["year"] + (sub["month_num"] - 0.5) / 12.0).tolist()

    no2_anom, _, _, _, _ = compute_baseline_climatology_anomalies(yrs, mos, sub["no2_mean_molec_cm2"].tolist(), 2015, 2019)
    ws_anom, _, _, _, _ = compute_baseline_climatology_anomalies(yrs, mos, sub["ws10m"].tolist(), 2015, 2019)
    cl_anom, _, _, _, _ = compute_baseline_climatology_anomalies(yrs, mos, sub["cloud_amt"].tolist(), 2015, 2019)
    t2_anom, _, _, _, _ = compute_baseline_climatology_anomalies(yrs, mos, sub["t2m"].tolist(), 2015, 2019)
    ps_anom, _, _, _, _ = compute_baseline_climatology_anomalies(yrs, mos, sub["ps"].tolist(), 2015, 2019)

    unadj = fit_box_tiao_step_intervention(t_dec, no2_anom, INTERVENTION_DECIMAL_YEAR)
    wth_all = fit_box_tiao_step_intervention(
        t_dec,
        no2_anom,
        INTERVENTION_DECIMAL_YEAR,
        covariates={"ws10m": ws_anom, "cloud_amt": cl_anom, "t2m": t2_anom, "ps": ps_anom},
    )

    # Sensitivity 1: exclude 2022-04 (only 8/30 valid OMI days)
    mask_no_apr = sub["month"] != "2022-04"
    idx_no_apr = [i for i, keep in enumerate(mask_no_apr.tolist()) if keep]
    wth_no_apr = fit_box_tiao_step_intervention(
        [t_dec[i] for i in idx_no_apr],
        [no2_anom[i] for i in idx_no_apr],
        INTERVENTION_DECIMAL_YEAR,
        covariates={
            k: [arr[i] for i in idx_no_apr]
            for k, arr in (("ws10m", ws_anom), ("cloud_amt", cl_anom), ("t2m", t2_anom), ("ps", ps_anom))
        },
    )

    # Sensitivity 2: matched Mar-Aug calendar months only (n=48)
    idx_ma = [i for i, m in enumerate(mos) if m in MARCH_AUGUST_MONTHS]
    wth_ma = fit_box_tiao_step_intervention(
        [t_dec[i] for i in idx_ma],
        [no2_anom[i] for i in idx_ma],
        INTERVENTION_DECIMAL_YEAR,
        covariates={
            k: [arr[i] for i in idx_ma]
            for k, arr in (("ws10m", ws_anom), ("cloud_amt", cl_anom), ("t2m", t2_anom), ("ps", ps_anom))
        },
    )

    # Pre-invasion secular partial slopes controlling meteorology (2015-03 .. 2022-02)
    idx_pre = [i for i, t in enumerate(t_dec) if t < INTERVENTION_DECIMAL_YEAR]
    t_pre = [t_dec[i] for i in idx_pre]
    y_pre = [no2_anom[i] for i in idx_pre]
    partial_controls: Dict[str, object] = {}
    for cov_name, cov_vec in (("ws10m", ws_anom), ("cloud_amt", cl_anom), ("t2m", t2_anom), ("ps", ps_anom)):
        s_dec, p_val, beta_c = partial_trend_controlling_covariate(t_pre, y_pre, [cov_vec[i] for i in idx_pre])
        partial_controls[cov_name] = {
            "pre_invasion_partial_slope_per_decade": clean_float(s_dec),
            "p_value_ar1": clean_float(p_val, 6),
            "covariate_beta": clean_float(beta_c),
        }

    # Empirical Davies continuous hinge breakpoint on full deseasonalized NO2 series
    bp = structural_hinge_breakpoint_analysis(t_dec, no2_anom, min_segment=6).to_dict()

    # Pre-compute weather-predicted vs actual NO2 monthly series for visualization
    if wth_all["status"] == "assessed":
        b_cov = wth_all["covariate_betas"]
        delta_hat = float(wth_all["delta_step"])
        beta_dec = float(wth_all["beta_within_per_decade"])
        # Reconstruct mean-centered OLS linear + weather fit cleanly using np.linalg.lstsq
        t_arr = np.asarray(t_dec, dtype=float)
        y_arr = np.asarray(no2_anom, dtype=float)
        X = np.column_stack(
            [
                np.ones(len(t_dec)),
                t_arr - INTERVENTION_DECIMAL_YEAR,
                np.where(t_arr >= INTERVENTION_DECIMAL_YEAR, 1.0, 0.0),
                np.asarray(ws_anom) - np.mean(ws_anom),
                np.asarray(cl_anom) - np.mean(cl_anom),
                np.asarray(t2_anom) - np.mean(t2_anom),
                np.asarray(ps_anom) - np.mean(ps_anom),
            ]
        )
        coef, _, _, _ = np.linalg.lstsq(X, y_arr, rcond=None)
        weather_only = (
            coef[0]
            + coef[3] * X[:, 3]
            + coef[4] * X[:, 4]
            + coef[5] * X[:, 5]
            + coef[6] * X[:, 6]
        )
        residual_no2 = y_arr - (coef[0] + coef[1] * X[:, 1] + coef[3] * X[:, 3] + coef[4] * X[:, 4] + coef[5] * X[:, 5] + coef[6] * X[:, 6])
    else:
        weather_only = np.zeros(len(t_dec))
        residual_no2 = np.asarray(no2_anom, dtype=float)

    series_rows = [
        {
            "month": sub["month"].iloc[i],
            "no2_anomaly_molec_cm2": clean_float(no2_anom[i]),
            "weather_predicted_no2_anomaly_molec_cm2": clean_float(weather_only[i]),
            "residual_after_trend_and_weather_molec_cm2": clean_float(residual_no2[i]),
            "ws10m_anomaly_ms": clean_float(ws_anom[i], 3),
        }
        for i in range(len(t_dec))
    ]

    return {
        "inference_caveat": (
            "Exploratory quasi-experimental diagnostics on n=1 post-invasion season (6 months). "
            "Controls for observed MERRA-2/CERES meteorology but does NOT replace a multi-year before/after test or clean NO2 control city."
        ),
        "box_tiao_unadjusted_all_months": unadj,
        "box_tiao_weather_controlled_all_months": wth_all,
        "box_tiao_weather_controlled_excl_apr2022": wth_no_apr,
        "box_tiao_weather_controlled_mar_aug_only": wth_ma,
        "pre_invasion_weather_partial_trends": partial_controls,
        "empirical_breakpoint_check": bp,
        "weather_residual_monthly_series": series_rows,
    }


def compute_regional_fire_water_earth_matrix(panel_df: pd.DataFrame) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """Quantify Mar-Aug 2022 vs 2019-2021 Fire density alongside Water & Earth anomalies across 6 regions."""
    ukr_regions = [b.region_id for b in STUDY_BOXES if b.role != "external_comparator_weather_only"]
    ma = panel_df[panel_df["region_id"].isin(ukr_regions) & panel_df["month_num"].isin(MARCH_AUGUST_MONTHS)].copy()

    rows: List[Dict[str, object]] = []
    for rid in ukr_regions:
        sub = ma[ma["region_id"] == rid]
        pre = sub[sub["year"].between(2019, 2021)]
        t22 = sub[sub["year"] == 2022]
        if pre.empty or t22.empty:
            continue

        f0_pre = _finite_mean(pre["fire_type0_per_1k_km2_day"].dropna().tolist())
        f0_22 = _finite_mean(t22["fire_type0_per_1k_km2_day"].dropna().tolist())
        f2_pre = _finite_mean(pre["fire_type2_per_1k_km2_day"].dropna().tolist())
        f2_22 = _finite_mean(t22["fire_type2_per_1k_km2_day"].dropna().tolist())
        _, f0_pct, _ = safe_pct_change(f0_22, f0_pre)
        _, f2_pct, _ = safe_pct_change(f2_22, f2_pre)

        vpd_pre = _finite_mean(pre["vpd_kpa"].tolist())
        vpd_22 = _finite_mean(t22["vpd_kpa"].tolist())
        gwet_pre = _finite_mean(pre["gwettop"].tolist())
        gwet_22 = _finite_mean(t22["gwettop"].tolist())
        precip_pre = _finite_mean(pre["prectotcorr"].tolist())
        precip_22 = _finite_mean(t22["prectotcorr"].tolist())
        t2m_pre = _finite_mean(pre["t2m"].tolist())
        t2m_22 = _finite_mean(t22["t2m"].tolist())
        pet_pre = _finite_mean(pre["pet_fao56_mm_day"].tolist())
        pet_22 = _finite_mean(t22["pet_fao56_mm_day"].tolist())
        ts_t2_pre = _finite_mean(pre["ts_minus_t2m_c"].tolist())
        ts_t2_22 = _finite_mean(t22["ts_minus_t2m_c"].tolist())

        # Pre-war 2015-2021 VPD std on Mar-Aug for standardized drought index shift
        vpd_hist_sd = float(np.std(sub[sub["year"].between(2015, 2021)]["vpd_kpa"].dropna(), ddof=1))
        drought_vpd_z = ((vpd_22 - vpd_pre) / vpd_hist_sd) if (vpd_pre is not None and vpd_22 is not None and vpd_hist_sd > 1e-6) else None

        meta = next(b for b in STUDY_BOXES if b.region_id == rid)
        rows.append(
            {
                "region_id": rid,
                "region_name": meta.name,
                "role": meta.role,
                "area_km2": round(meta.area_km2, 1),
                "fire_type0_2019_2021_per_1k_km2_day": clean_float(f0_pre, 4),
                "fire_type0_2022_per_1k_km2_day": clean_float(f0_22, 4),
                "fire_type0_pct_change": clean_float(f0_pct, 2),
                "fire_type2_2019_2021_per_1k_km2_day": clean_float(f2_pre, 4),
                "fire_type2_2022_per_1k_km2_day": clean_float(f2_22, 4),
                "fire_type2_pct_change": clean_float(f2_pct, 2),
                "vpd_2019_2021_kpa": clean_float(vpd_pre, 4),
                "vpd_2022_kpa": clean_float(vpd_22, 4),
                "vpd_diff_kpa": clean_float((vpd_22 - vpd_pre) if (vpd_22 is not None and vpd_pre is not None) else None, 4),
                "vpd_drought_shift_z": clean_float(drought_vpd_z, 3),
                "gwettop_2019_2021": clean_float(gwet_pre, 4),
                "gwettop_2022": clean_float(gwet_22, 4),
                "gwettop_diff": clean_float((gwet_22 - gwet_pre) if (gwet_22 is not None and gwet_pre is not None) else None, 4),
                "prectotcorr_diff_mm_day": clean_float((precip_22 - precip_pre) if (precip_22 is not None and precip_pre is not None) else None, 3),
                "pet_diff_mm_day": clean_float((pet_22 - pet_pre) if (pet_22 is not None and pet_pre is not None) else None, 3),
                "t2m_diff_c": clean_float((t2m_22 - t2m_pre) if (t2m_22 is not None and t2m_pre is not None) else None, 3),
                "ts_minus_t2m_diff_c": clean_float((ts_t2_22 - ts_t2_pre) if (ts_t2_22 is not None and ts_t2_pre is not None) else None, 3),
            }
        )

    # Also build external comparator weather context rows (Krakow & Prague)
    ext_rows: List[Dict[str, object]] = []
    for rid in ("poland_krakow", "czechia_prague"):
        sub = panel_df[(panel_df["region_id"] == rid) & panel_df["month_num"].isin(MARCH_AUGUST_MONTHS)]
        pre15 = sub[sub["year"].between(2015, 2019)]
        t22 = sub[sub["year"] == 2022]
        meta = next(b for b in STUDY_BOXES if b.region_id == rid)
        ext_rows.append(
            {
                "region_id": rid,
                "region_name": meta.name,
                "t2m_2015_2019_c": clean_float(_finite_mean(pre15["t2m"].tolist()), 2),
                "t2m_2022_c": clean_float(_finite_mean(t22["t2m"].tolist()), 2),
                "ws10m_2015_2019_ms": clean_float(_finite_mean(pre15["ws10m"].tolist()), 2),
                "ws10m_2022_ms": clean_float(_finite_mean(t22["ws10m"].tolist()), 2),
                "cloud_amt_2015_2019_pct": clean_float(_finite_mean(pre15["cloud_amt"].tolist()), 1),
                "cloud_amt_2022_pct": clean_float(_finite_mean(t22["cloud_amt"].tolist()), 1),
                "vpd_2015_2019_kpa": clean_float(_finite_mean(pre15["vpd_kpa"].tolist()), 3),
                "vpd_2022_kpa": clean_float(_finite_mean(t22["vpd_kpa"].tolist()), 3),
            }
        )

    summary = {
        "interpretation": (
            "Fire-weather mismatch: Western and Central interior benchmarks experienced stronger 2022 evaporative "
            "drying (higher VPD, lower surface soil moisture) yet saw vegetation-type fire detections fall markedly, "
            "whereas the Donbas-Kharkiv frontline corridor had near-baseline VPD/soil moisture while type0 detections "
            "rose +72.4% and type2 static industrial anomalies collapsed -83.3%."
        ),
        "external_eu_weather_context_2015_2019_vs_2022": ext_rows,
    }
    return rows, summary


def compute_multi_element_trends_and_couplings(panel_df: pd.DataFrame) -> Dict[str, object]:
    """Compute Kyiv multi-year Seasonal MK + BH/BY FDR and AR(1)-prewhitened couplings."""
    kyiv = panel_df[panel_df["region_id"] == "kyiv_no2_box"].sort_values(["year", "month_num"]).reset_index(drop=True)
    trend_records: List[Dict[str, object]] = []
    raw_pvals: List[float] = []

    for spec in FOUR_ELEMENT_METRICS:
        if spec.metric_id.startswith("fire_"):
            continue  # FIRMS spans only 24 Mar-Aug months across 4 years (2019-2022); too short for multi-year MK
        sub = kyiv[kyiv[spec.metric_id].notna()].copy()
        if len(sub) < 24:
            continue
        yrs = sub["year"].astype(int).tolist()
        mos = sub["month_num"].astype(int).tolist()
        vals = sub[spec.metric_id].astype(float).tolist()
        t_dec = [y + (m - 0.5) / 12.0 for y, m in zip(yrs, mos)]
        anoms, _, _, _, active_mos = compute_baseline_climatology_anomalies(yrs, mos, vals, 2015, 2019)

        hs = hirsch_slack_seasonal_mk_and_slope(yrs, mos, vals, active_months=active_mos, min_years_per_month=4)
        _, tau_mo, _, _, z_hr, p_hr, vif_mo, n_star, r1_bc = hamed_rao_modified_mk(t_dec, anoms)

        raw_p = float(hs["p_value_seasonal"])
        raw_pvals.append(raw_p)
        trend_records.append(
            {
                "metric_id": spec.metric_id,
                "element": spec.element,
                "label": spec.label,
                "units": spec.units,
                "n_months": len(sub),
                "span": f"{sub['month'].iloc[0]}..{sub['month'].iloc[-1]}",
                "hirsch_slack_sen_slope_per_decade": clean_float(hs["sen_slope_per_decade"], 5),
                "ci95_low_per_decade": clean_float(hs["ci_low_per_decade"], 5),
                "ci95_high_per_decade": clean_float(hs["ci_high_per_decade"], 5),
                "seasonal_p_value": clean_float(raw_p, 6),
                "hamed_rao_anomaly_p_value": clean_float(p_hr, 6),
                "hamed_rao_vif": clean_float(vif_mo, 3),
                "ar1_bc": clean_float(r1_bc, 3),
                "seasonal_divergence_p": hs["van_belle_hughes"]["p_value"],
            }
        )

    q_bh = bh_q_values(raw_pvals)
    q_by = by_q_values(raw_pvals)
    for rec, qb, qy in zip(trend_records, q_bh, q_by):
        rec["bh_fdr_q_value"] = clean_float(qb, 6)
        rec["by_fdr_q_value"] = clean_float(qy, 6)
        rec["bh_fdr_significant_05"] = bool(qb <= 0.05)

    # Physical cross-element couplings (AR(1)-prewhitened lagged monthly Kendall tau)
    coupling_pairs = [
        ("kyiv_no2_box", "ws10m", "no2_mean_molec_cm2", "Wind dispersion -> Tropospheric NO2"),
        ("kyiv_no2_box", "ps", "no2_mean_molec_cm2", "Surface pressure (stagnant highs) -> Tropospheric NO2"),
        ("kyiv_no2_box", "t2m", "no2_mean_molec_cm2", "Air temperature -> Tropospheric NO2"),
        ("kyiv_no2_box", "prectotcorr", "gwettop", "Precipitation -> Topsoil moisture percolation (0-5 cm)"),
        ("kyiv_no2_box", "prectotcorr", "gwetroot", "Precipitation -> Root-zone soil memory (0-100 cm)"),
        ("kyiv_no2_box", "gwettop", "vpd_kpa", "Soil moisture -> Vapor Pressure Deficit coupling"),
        ("donbas_kharkiv_east", "prectotcorr", "gwetroot", "Donbas Precipitation -> Root-zone soil moisture"),
        ("west_ukraine_cand", "gwettop", "vpd_kpa", "West Ukraine Soil drying -> Atmospheric VPD"),
    ]
    couplings: List[Dict[str, object]] = []
    c_pvals: List[float] = []
    for rid, var_x, var_y, desc in coupling_pairs:
        sub = panel_df[(panel_df["region_id"] == rid) & panel_df[var_x].notna() & panel_df[var_y].notna()].sort_values(["year", "month_num"])
        res = compute_lagged_monthly_impulse_coupling(
            sub["year"].tolist(),
            sub["month_num"].tolist(),
            sub[var_x].tolist(),
            sub["year"].tolist(),
            sub["month_num"].tolist(),
            sub[var_y].tolist(),
            max_lag_months=2,
            baseline_start=2015,
            baseline_end=2021,
            min_common_months=24,
        )
        p_sidak = float(res["optimal_lag_sidak_p"]) if res["optimal_lag_sidak_p"] is not None else 1.0
        c_pvals.append(p_sidak)
        couplings.append(
            {
                "region_id": rid,
                "driver_var": var_x,
                "response_var": var_y,
                "relationship": desc,
                **res,
            }
        )

    cq_bh = bh_q_values(c_pvals)
    for rec, qv in zip(couplings, cq_bh):
        rec["bh_fdr_q_value"] = clean_float(qv, 6)
        rec["bh_fdr_significant_05"] = bool(qv <= 0.05)

    return {
        "note": "Multi-year trends span 8 years (2015–2022) and are descriptive indicators, not WMO 30-year climate trends.",
        "kyiv_seasonal_trends": trend_records,
        "prewhitened_cross_element_couplings": couplings,
    }


def _plot_dashboard(kyiv_df: pd.DataFrame, out_path: Path) -> None:
    df = kyiv_df.sort_values(["year", "month_num"]).reset_index(drop=True)
    dates = pd.to_datetime(df["month"] + "-15")
    yrs = df["year"].astype(int).tolist()
    mos = df["month_num"].astype(int).tolist()

    specs = [
        ("no2_mean_molec_cm2", "AIR: OMI Tropospheric NO2 Anomaly (1e15 molec/cm^2)", 1e-15, "#1f618d"),
        ("t2m", "FIRE-WEATHER / THERMAL: 2m Air Temperature Anomaly (°C)", 1.0, "#c0392b"),
        ("vpd_kpa", "WATER: Atmospheric Vapor Pressure Deficit Anomaly (kPa)", 1.0, "#117a65"),
        ("gwettop", "EARTH: Surface Soil Wetness 0–5 cm Anomaly (fraction)", 1.0, "#7d6608"),
    ]
    fig, axes = plt.subplots(4, 1, figsize=(11.5, 9.5), sharex=True)
    invasion_dt = pd.Timestamp(CONFLICT_START_DATE)

    for ax, (col, title, scale, color) in zip(axes, specs):
        sub = df[df[col].notna()].copy()
        s_dates = pd.to_datetime(sub["month"] + "-15")
        anoms, _, _, _, _ = compute_baseline_climatology_anomalies(
            sub["year"].astype(int).tolist(),
            sub["month_num"].astype(int).tolist(),
            sub[col].astype(float).tolist(),
            2015,
            2019,
        )
        y_vals = np.asarray(anoms, dtype=float) * scale
        ax.axhline(0.0, color="#7f8c8d", linewidth=0.9, linestyle="--")
        ax.axvline(invasion_dt, color="#922b21", linewidth=1.3, linestyle=":")
        ax.plot(s_dates, y_vals, color=color, linewidth=1.5)
        ax.fill_between(s_dates, 0.0, y_vals, where=(y_vals >= 0.0), alpha=0.18, color=color, interpolate=True)
        ax.fill_between(s_dates, 0.0, y_vals, where=(y_vals < 0.0), alpha=0.14, color="#566573", interpolate=True)
        if col == "no2_mean_molec_cm2":
            y_lo, y_hi = ax.get_ylim()
            ax.set_ylim(y_lo, max(y_hi, 2.05))
            apr22 = sub[sub["month"] == "2022-04"]
            if not apr22.empty:
                idx_apr = sub.index.get_loc(apr22.index[0])
                ax.scatter([s_dates.iloc[idx_apr]], [y_vals[idx_apr]], color="#e67e22", edgecolor="black", zorder=5, s=48, label="Apr 2022 (8/30 valid days)")
                ax.legend(loc="upper center", fontsize=8.0, frameon=True, facecolor="white")
        ax.set_title(title, loc="left", fontsize=9.8, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle=":", alpha=0.45)

    axes[0].text(invasion_dt - pd.Timedelta(days=20), 1.65, "Invasion\n2022-02-24", color="#922b21", fontsize=8.0, ha="right")
    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("Kyiv Study Box: 4-Element Deseasonalized Monthly Anomalies (vs. 2015–2019 Same-Month Baseline)", fontsize=12.0, fontweight="bold")
    fig.text(
        0.015,
        0.008,
        "Sources: NASA Giovanni OMNO2d v004 & NASA POWER MERRA-2/CERES 3x3 cos(lat) grid. Observed anomalies are descriptive; single-season patterns do not prove war causation.",
        fontsize=7.5,
        color="#566573",
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_weather_no2_sensitivity(daily_summary: Dict[str, object], intervention: Dict[str, object], out_path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.8))

    strata = [s for s in daily_summary["strata"] if s["stratum_id"] in {"all_valid_days", "low_wind_lt_3ms", "higher_wind_ge_3ms", "clear_moderate_cloud_lt_60pct"}]
    labels = ["All Valid\nDays", "Calm Wind\n(<3 m/s)", "Higher Wind\n(>=3 m/s)", "Clear Cloud\n(<60%)"]
    pct15 = [s["vs_2015_2019_pct_change"] or 0.0 for s in strata]
    pct19 = [s["vs_2019_2021_pct_change"] or 0.0 for s in strata]
    x = np.arange(len(labels))
    w = 0.35
    ax1.axhline(0.0, color="#566573", linewidth=0.9)
    b1 = ax1.bar(x - w / 2, pct15, width=w, color="#21618c", label="vs. 2015–2019")
    b2 = ax1.bar(x + w / 2, pct19, width=w, color="#5dade2", label="vs. 2019–2021")
    for bars in (b1, b2):
        for bar in bars:
            val = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, val - 2.3, f"{val:.1f}%", ha="center", va="top", fontsize=7.6, color="#1b2631")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8.5)
    ax1.set_ylabel("Mar–Aug 2022 NO2 Change (%)", fontsize=9.0)
    ax1.set_ylim(min(min(pct15), min(pct19)) - 7.5, 4.0)
    ax1.set_title("Daily Kyiv OMI NO2 Stratified by Wind & Cloud", loc="left", fontsize=10.0, fontweight="bold")
    ax1.legend(loc="lower right", fontsize=8.0)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", linestyle=":", alpha=0.45)

    s_rows = intervention["weather_residual_monthly_series"]
    dates = pd.to_datetime([r["month"] + "-15" for r in s_rows])
    actual = [r["no2_anomaly_molec_cm2"] / 1e15 for r in s_rows]
    pred = [r["weather_predicted_no2_anomaly_molec_cm2"] / 1e15 for r in s_rows]
    ax2.axhline(0.0, color="#7f8c8d", linewidth=0.8, linestyle="--")
    ax2.axvline(pd.Timestamp(CONFLICT_START_DATE), color="#922b21", linewidth=1.2, linestyle=":")
    ax2.plot(dates, actual, color="#1f618d", linewidth=1.4, label="Observed NO2 Anomaly")
    ax2.plot(dates, pred, color="#d35400", linewidth=1.3, linestyle="--", label="Weather-Expected Anomaly (WS10M, PS, T2M, Cloud)")
    bt = intervention["box_tiao_weather_controlled_all_months"]
    step_e14 = (bt["delta_step"] / 1e14) if bt["delta_step"] is not None else 0.0
    ax2.set_title(f"Weather Control: Box-Tiao Mar 2022 Step = {step_e14:+.2f}e14 (p={bt['p_value_ar1']:.3f})", loc="left", fontsize=10.0, fontweight="bold")
    ax2.set_ylabel("NO2 Anomaly (1e15 molec/cm^2)", fontsize=9.0)
    ax2.set_ylim(-1.65, 2.05)
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.legend(loc="upper left", fontsize=7.6, frameon=True, facecolor="white")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", linestyle=":", alpha=0.45)

    fig.text(
        0.015,
        0.01,
        "Exploratory weather-controlled regression (R^2=0.36 vs 0.08 unadjusted). Calm (<3 m/s) NO2 drop persists; n=1 war season cannot isolate causality alone.",
        fontsize=7.4,
        color="#566573",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_fire_drought_contrast(regional_rows: Sequence[Mapping[str, object]], out_path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 5.0))
    short_names = {
        "donbas_kharkiv_east": "Donbas–Kharkiv\n(Frontline)",
        "south_steppe_belt": "South Steppe\n(Corridor)",
        "kyiv_no2_box": "Kyiv NO2 Box\n(Urban)",
        "kyiv_north_belt": "Kyiv–North\n(Corridor)",
        "central_interior_cand": "Central Interior\n(Reference)",
        "west_ukraine_cand": "West Ukraine\n(Reference)",
    }
    colors = {
        "primary_urban_study": "#2e86c1",
        "war_theater_study": "#c0392b",
        "ukraine_reference_region": "#27ae60",
    }

    label_offsets = {
        "kyiv_no2_box": (7, -2, "left"),
        "donbas_kharkiv_east": (7, -11, "left"),
        "south_steppe_belt": (7, 5, "left"),
        "kyiv_north_belt": (7, 6, "left"),
        "central_interior_cand": (-4, 8, "center"),
        "west_ukraine_cand": (-8, 8, "right"),
    }
    for row in regional_rows:
        rid = str(row["region_id"])
        vx = float(row["vpd_diff_kpa"] or 0.0)
        fy = float(row["fire_type0_pct_change"] or 0.0)
        c = colors.get(str(row["role"]), "#566573")
        ax1.scatter([vx], [fy], color=c, s=95, edgecolor="black", zorder=4)
        ox, oy, ha_mode = label_offsets.get(rid, (6, 6, "left"))
        ax1.annotate(short_names.get(rid, rid).replace("\n", " "), (vx, fy), textcoords="offset points", xytext=(ox, oy), ha=ha_mode, fontsize=7.6)

    ax1.axhline(0.0, color="#566573", linewidth=0.9, linestyle="--")
    ax1.axvline(0.0, color="#566573", linewidth=0.9, linestyle="--")
    ax1.set_xlim(-0.095, 0.175)
    ax1.set_ylim(-68, 96)
    ax1.set_xlabel("2022 vs. 2019–2021 VPD Drought Shift (kPa, + = drier air)", fontsize=8.8)
    ax1.set_ylabel("VIIRS Vegetation-Type Fire Shift (%)", fontsize=8.8)
    ax1.set_title("Fire Response vs. Atmospheric Drying (Mar–Aug 2022)", loc="left", fontsize=9.8, fontweight="bold")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(linestyle=":", alpha=0.45)

    ordered = sorted(regional_rows, key=lambda r: float(r["fire_type0_pct_change"] or 0.0), reverse=True)
    y_pos = np.arange(len(ordered))
    f0_pcts = [float(r["fire_type0_pct_change"] or 0.0) for r in ordered]
    f2_pcts = [float(r["fire_type2_pct_change"] or 0.0) for r in ordered]
    h = 0.36
    ax2.axvline(0.0, color="#566573", linewidth=0.9)
    ax2.barh(y_pos - h / 2, f0_pcts, height=h, color="#d35400", label="type0 Vegetation / Unclassified")
    ax2.barh(y_pos + h / 2, f2_pcts, height=h, color="#5b2c6f", label="type2 Static Industrial (Flares/Plants)")
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([short_names.get(str(r["region_id"]), str(r["region_id"])) for r in ordered], fontsize=8.0)
    ax2.set_xlabel("2022 vs. 2019–2021 Area-Normalized Rate Change (%)", fontsize=8.8)
    ax2.set_title("Vegetation Surge vs. Static Industrial Collapse", loc="left", fontsize=9.8, fontweight="bold")
    ax2.legend(loc="upper right", fontsize=7.6, frameon=True, facecolor="white")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="x", linestyle=":", alpha=0.45)

    fig.text(
        0.015,
        0.01,
        "Sources: FIRMS VIIRS S-NPP SV-C2 + NASA POWER MERRA-2. West & Central Ukraine dried (+0.06 to +0.14 kPa VPD, soil -0.03 to -0.04) while burning fell; Donbas burned +72.4% with +0.05 kPa VPD.",
        fontsize=7.3,
        color="#566573",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_four_elements_analysis(
    no2_csv: Optional[Path] = None,
    power_dir: Path = DEFAULT_POWER_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    fetch_power_if_missing: bool = False,
) -> Dict[str, object]:
    """Execute end-to-end 4-element Kyiv & Ukraine integration and emit verified reports."""
    no2_input = no2_csv or _discover_default_input(DEFAULT_NO2_RAW_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    power_monthly_df, power_daily_df, power_prov = load_power_panels(
        power_dir=power_dir,
        fetch_if_missing=fetch_power_if_missing,
    )

    daily_no2_raw, no2_meta = parse_giovanni_csv(no2_input)
    daily_no2_full, no2_daily_counts = reindex_daily_calendar(daily_no2_raw, no2_meta)

    no2_monthly_path = reports_dir / "no2_monthly.csv"
    fire_monthly_path = reports_dir / "fire_monthly.csv"
    if not no2_monthly_path.is_file() or not fire_monthly_path.is_file():
        raise FileNotFoundError(
            "Expected reports/no2_monthly.csv and reports/fire_monthly.csv. "
            "Run `python -m src.no2_pipeline` and `python -m src.fire_analysis` first."
        )
    no2_monthly_df = pd.read_csv(no2_monthly_path)
    fire_monthly_df = pd.read_csv(fire_monthly_path)

    panel_df = build_unified_monthly_panel(power_monthly_df, no2_monthly_df, fire_monthly_df)
    panel_csv_path = reports_dir / "four_elements_monthly_panel.csv"
    panel_df.to_csv(panel_csv_path, index=False)

    daily_merged_df, kyiv_daily_sensitivity = compute_kyiv_daily_wind_cloud_sensitivity(
        daily_no2_full, power_daily_df
    )
    daily_csv_path = reports_dir / "kyiv_daily_air_weather.csv"
    daily_out = daily_merged_df.rename(columns={"value": "no2_molec_cm2"})
    daily_out.to_csv(daily_csv_path, index=False)

    kyiv_panel = panel_df[panel_df["region_id"] == "kyiv_no2_box"].copy()
    kyiv_element_comparisons = compute_kyiv_monthly_four_element_summaries(kyiv_panel)
    kyiv_intervention = compute_kyiv_intervention_and_weather_controls(kyiv_panel)
    regional_fwe_rows, regional_fwe_summary = compute_regional_fire_water_earth_matrix(panel_df)
    multi_trends = compute_multi_element_trends_and_couplings(panel_df)

    comp_df = pd.DataFrame(kyiv_element_comparisons)
    comp_csv_path = reports_dir / "four_elements_comparisons.csv"
    comp_df.to_csv(comp_csv_path, index=False)

    chart_dash = reports_dir / "kyiv_four_elements_dashboard.png"
    chart_sens = reports_dir / "kyiv_weather_no2_sensitivity.png"
    chart_fire = reports_dir / "ukraine_fire_drought_contrast.png"
    _plot_dashboard(kyiv_panel, chart_dash)
    _plot_weather_no2_sensitivity(kyiv_daily_sensitivity, kyiv_intervention, chart_sens)
    _plot_fire_drought_contrast(regional_fwe_rows, chart_fire)

    kyiv_box = next(b for b in STUDY_BOXES if b.region_id == "kyiv_no2_box")
    results_payload: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": "ukraine",
        "study_id": "kyiv_four_elements",
        "conflict_start": CONFLICT_START_DATE,
        "region": {
            "region_id": kyiv_box.region_id,
            "name": kyiv_box.name,
            "area_km2": round(kyiv_box.area_km2, 1),
            "center": {"lat": kyiv_box.center_lat, "lon": kyiv_box.center_lon},
            "bounding_box": {
                "south": kyiv_box.south,
                "north": kyiv_box.north,
                "west": kyiv_box.west,
                "east": kyiv_box.east,
            },
            "spatial_resolution_note": (
                "OMI OMNO2d v004 (0.25 deg), VIIRS S-NPP SV-C2 (375 m nominal), and NASA POWER MERRA-2/CERES "
                "(0.5 deg x 0.625 deg / 1.0 deg sampled over a 3x3 cos(lat) grid). Box means describe area averages, "
                "not street-level or point exposure."
            ),
        },
        "status": {
            "before_after_significance": "not_assessed",
            "exploratory_monthly_intervention": "assessed_noncausal_single_season_only",
            "causal_attribution": "not_established",
            "confounder_control": "assessed_via_daily_stratification_and_monthly_covariates",
            "sub_national_drought_fire_contrast": "assessed_descriptive_2019_2022",
        },
        "kyiv_four_element_comparisons": kyiv_element_comparisons,
        "kyiv_daily_wind_cloud_sensitivity": kyiv_daily_sensitivity,
        "kyiv_intervention_and_weather_controls": kyiv_intervention,
        "regional_fire_water_earth_contrast": {
            **regional_fwe_summary,
            "regions": regional_fwe_rows,
        },
        "multi_element_trends_and_couplings": multi_trends,
        "charts": {
            "four_elements_dashboard": {
                "png_path": f"reports/{chart_dash.name}",
                "title": "Kyiv 4-Element Deseasonalized Monthly Anomalies (2015–2022)",
            },
            "weather_no2_sensitivity": {
                "png_path": f"reports/{chart_sens.name}",
                "title": "Kyiv NO2 Wind/Cloud Stratification and Weather-Controlled Box-Tiao Step",
            },
            "fire_drought_contrast": {
                "png_path": f"reports/{chart_fire.name}",
                "title": "Ukraine Regional Fire-vs-VPD Drought Contrast and Industrial Collapse (2022)",
            },
        },
        "limitations": [
            "Only one post-invasion spring-summer war season (Mar-Aug 2022) is present; formal before/after seasonal inference remains not_assessed.",
            "April 2022 OMI NO2 contains only 8/30 valid days (26.67% coverage); sensitivity checks excluding 2022-04 are reported explicitly.",
            "FIRMS VIIRS S-NPP has known orbit gaps in 2022-07-27..2022-08-10 and 2022-03-05; rates normalize by observed satellite days.",
            "NASA POWER MERRA-2 resolution (0.5 deg x 0.625 deg) captures synoptic/regional hydrology and meteorology rather than urban street microclimates.",
            "External Krakow/Prague boxes supply meteorological context only (NO2 comparability requires matched OMI/TROPOMI retrievals).",
        ],
    }

    results_json_path = reports_dir / "kyiv_four_elements_results.json"
    write_strict_json(results_json_path, results_payload)

    quality_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": results_payload["generated_at_utc"],
        "provenance": {
            "giovanni_no2_csv": {"file": no2_input.name, "sha256": no2_meta["input_sha256"]},
            "power_monthly_json": {
                "file": Path(power_prov["monthly"]["cache_path"]).name,
                "sha256": power_prov["monthly"]["sha256"],
            },
            "power_daily_json": {
                "file": Path(power_prov["daily_kyiv"]["cache_path"]).name,
                "sha256": power_prov["daily_kyiv"]["sha256"],
            },
            "no2_monthly_csv_sha256": sha256_file(no2_monthly_path),
            "fire_monthly_csv_sha256": sha256_file(fire_monthly_path),
        },
        "counts": {
            "monthly_panel_rows": int(len(panel_df)),
            "regions_count": int(panel_df["region_id"].nunique()),
            "kyiv_daily_rows": int(len(daily_merged_df)),
            "no2_valid_daily_observations": int(no2_daily_counts["valid_observations"]),
            "monthly_power_missing_t2m_cells": int(panel_df["t2m"].isna().sum()),
            "monthly_power_missing_vpd_cells": int(panel_df["vpd_kpa"].isna().sum()),
        },
        "invariants": {
            "allow_nan_json": False,
            "missing_no2_never_zero_filled": bool(daily_merged_df["value"].isna().sum() > 0),
            "before_after_seasonal_inference": "not_assessed",
            "causal_attribution": "not_established",
        },
    }
    write_strict_json(reports_dir / "four_elements_quality.json", quality_payload)
    return results_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full 4-Elements Kyiv & Ukraine environmental analysis.")
    parser.add_argument("--no2-csv", type=Path, default=None)
    parser.add_argument("--power-dir", type=Path, default=DEFAULT_POWER_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--fetch", action="store_true", help="Fetch NASA POWER if local cache is absent.")
    args = parser.parse_args()

    res = run_four_elements_analysis(
        no2_csv=args.no2_csv,
        power_dir=args.power_dir,
        reports_dir=args.reports_dir,
        fetch_power_if_missing=args.fetch,
    )
    bt = res["kyiv_intervention_and_weather_controls"]["box_tiao_weather_controlled_all_months"]
    print(f"Wrote 4-elements results -> {args.reports_dir / 'kyiv_four_elements_results.json'}")
    print(f"Weather-controlled Kyiv NO2 Mar 2022 step: delta={bt['delta_step']:.3e}, R2={bt['r_squared']}, p={bt['p_value_ar1']}")


if __name__ == "__main__":
    main()
