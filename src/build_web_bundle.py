"""Compile validated 4-Elements reports into a self-contained static web bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.stats_rigor import clean_float, compute_baseline_climatology_anomalies, write_strict_json
from src.weather_power_pipeline import STUDY_BOXES

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"
DEFAULT_WEB_DATA_PATH = REPO_ROOT / "web" / "data" / "ukraine_4elements_bundle.json"

WEB_VARIABLES = (
    ("air", "no2_mean_molec_cm2", "OMI Tropospheric NO2", "molec/cm^2", 1e-15, "1e15 molec/cm^2"),
    ("air", "ws10m", "10m Wind Speed", "m/s", 1.0, "m/s"),
    ("air", "cloud_amt", "Total Cloud Amount", "%", 1.0, "%"),
    ("air", "cloud_radiative_attenuation_wm2", "Cloud Radiative Attenuation", "W/m^2", 1.0, "W/m^2"),
    ("fire", "fire_type0_per_1k_km2_day", "VIIRS Vegetation Fires (type0)", "det / 1000 km^2 / d", 1.0, "det/1k km^2/d"),
    ("fire", "fire_type2_per_1k_km2_day", "VIIRS Industrial Flares (type2)", "det / 1000 km^2 / d", 1.0, "det/1k km^2/d"),
    ("fire", "t2m", "2m Air Temperature", "°C", 1.0, "°C"),
    ("fire", "pet_fao56_mm_day", "FAO-56 Reference ET (PET)", "mm/day", 1.0, "mm/day"),
    ("water", "prectotcorr", "Precipitation", "mm/day", 1.0, "mm/day"),
    ("water", "vpd_kpa", "Vapor Pressure Deficit (VPD)", "kPa", 1.0, "kPa"),
    ("water", "rh2m", "Relative Humidity (2m)", "%", 1.0, "%"),
    ("water", "precip_minus_pet_mm_day", "Water Balance (P - PET)", "mm/day", 1.0, "mm/day"),
    ("earth", "gwettop", "Surface Soil Wetness (0-5 cm)", "fraction", 1.0, "fraction"),
    ("earth", "gwetroot", "Root-Zone Soil Wetness (0-100 cm)", "fraction", 1.0, "fraction"),
    ("earth", "ts_minus_t2m_c", "Skin-Air Coupling (Ts - T2m)", "°C", 1.0, "°C"),
    ("earth", "allsky_srf_alb", "Surface Albedo", "dimensionless", 1.0, "dimensionless"),
)


def build_web_bundle(
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    out_path: Path = DEFAULT_WEB_DATA_PATH,
) -> Dict[str, object]:
    """Assemble web-ready strict JSON bundle from validated analysis artifacts."""
    results_path = reports_dir / "kyiv_four_elements_results.json"
    panel_path = reports_dir / "four_elements_monthly_panel.csv"
    quality_path = reports_dir / "four_elements_quality.json"
    if not results_path.is_file() or not panel_path.is_file():
        raise FileNotFoundError(
            "Missing reports/kyiv_four_elements_results.json or four_elements_monthly_panel.csv. "
            "Run `python -m src.four_elements_analysis` first."
        )

    results = json.loads(results_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
    panel_df = pd.read_csv(panel_path)

    regions_payload: Dict[str, object] = {}
    for box in STUDY_BOXES:
        sub = panel_df[panel_df["region_id"] == box.region_id].sort_values(["year", "month_num"]).reset_index(drop=True)
        months = sub["month"].astype(str).tolist()
        yrs = sub["year"].astype(int).tolist()
        mos = sub["month_num"].astype(int).tolist()

        series_by_var: Dict[str, object] = {}
        for element, col, label, raw_unit, scale, disp_unit in WEB_VARIABLES:
            if col not in sub.columns or sub[col].dropna().empty:
                continue
            vals = [float(v) * scale if pd.notna(v) else float("nan") for v in sub[col].tolist()]
            anom_15, _, clim_15, std_15, _ = compute_baseline_climatology_anomalies(yrs, mos, vals, 2015, 2019, min_baseline_years=2)
            anom_19, _, clim_19, std_19, _ = compute_baseline_climatology_anomalies(yrs, mos, vals, 2019, 2021, min_baseline_years=2)

            def _vec(seq: List[float], digits: int = 4) -> List[object]:
                return [clean_float(x, digits) for x in seq]

            cov_flags: List[str] = []
            for idx, m_str in enumerate(months):
                flag = ""
                if col == "no2_mean_molec_cm2" and pd.notna(sub["no2_valid_days"].iloc[idx]):
                    vd = int(sub["no2_valid_days"].iloc[idx])
                    cd = int(sub["no2_calendar_days"].iloc[idx])
                    if vd / max(1, cd) < 0.50:
                        flag = f"Low OMI coverage: {vd}/{cd} valid days (<50%)"
                elif col.startswith("fire_") and m_str in {"2022-07", "2022-08", "2022-03"} and pd.notna(sub[col].iloc[idx]):
                    flag = "VIIRS S-NPP orbit outage noted in 2022 (rate normalized per observed day)"
                cov_flags.append(flag)

            series_by_var[col] = {
                "element": element,
                "label": label,
                "display_unit": disp_unit,
                "raw_unit": raw_unit,
                "scale_factor": scale,
                "raw": _vec(vals),
                "anom_2015_2019": _vec(anom_15),
                "anom_2019_2021": _vec(anom_19),
                "baseline_2015_2019_by_month": {str(k): clean_float(v, 4) for k, v in clim_15.items()},
                "baseline_2019_2021_by_month": {str(k): clean_float(v, 4) for k, v in clim_19.items()},
                "flags": cov_flags,
            }

        regions_payload[box.region_id] = {
            "region_id": box.region_id,
            "name": box.name,
            "role": box.role,
            "area_km2": round(box.area_km2, 1),
            "center": {"lat": box.center_lat, "lon": box.center_lon},
            "bounds": {"south": box.south, "north": box.north, "west": box.west, "east": box.east},
            "months": months,
            "years": yrs,
            "month_nums": mos,
            "series": series_by_var,
        }

    bundle: Dict[str, object] = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": "ukraine",
        "title": "Ukraine & Kyiv 4-Elements Environmental Trend Observatory",
        "conflict_start": results["conflict_start"],
        "status": results["status"],
        "variable_catalog": [
            {"element": el, "metric_id": mid, "label": lbl, "unit": du}
            for el, mid, lbl, _, _, du in WEB_VARIABLES
        ],
        "kyiv_comparisons": results["kyiv_four_element_comparisons"],
        "kyiv_daily_wind_cloud_sensitivity": results["kyiv_daily_wind_cloud_sensitivity"],
        "kyiv_intervention_and_weather_controls": results["kyiv_intervention_and_weather_controls"],
        "regional_fire_water_earth_contrast": results["regional_fire_water_earth_contrast"],
        "multi_element_trends_and_couplings": results["multi_element_trends_and_couplings"],
        "limitations": results["limitations"],
        "provenance": quality.get("provenance", {}),
        "regions": regions_payload,
    }
    write_strict_json(out_path, bundle)
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Build interactive 4-Elements web data bundle.")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_WEB_DATA_PATH)
    args = parser.parse_args()
    bundle = build_web_bundle(reports_dir=args.reports_dir, out_path=args.out)
    print(f"Built web bundle -> {args.out} ({len(bundle['regions'])} regions)")


if __name__ == "__main__":
    main()
