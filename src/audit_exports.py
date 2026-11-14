"""Reproducible generator for spatial mask, CMR matched-date Fire, and PET sensitivity audits.

Regenerates deterministically offline from ``data/frozen/`` + ``data/raw/firms_viirs/``:
  - ``data/frozen/spatial_mask_audit.json``
  - ``data/frozen/firms_cmr_matched_audit.json``
  - Kyiv elevation & strict FAO-56 PET checks inside
    ``data/frozen/nasa_power/native_grid_vs_3x3_summary.json``

With ``--fetch-upstream``, also re-queries NASA CMR ``VNP14IMG``, geoBoundaries
``UKR-ADM0``, and the dense native MERRA-2/CERES grid over ``donbas_kharkiv_east``.

Usage:
    python -m src.audit_exports
    python -m src.audit_exports --out-dir /tmp/audit_check
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "war_env_tracker_mplconfig"))

from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd

from src.fire_pipeline import (
    DEFAULT_FIRE_RAW_DIR,
    STUDY_MONTHS,
    STUDY_YEARS,
    discover_fire_inputs,
    load_and_validate_firms_archives,
)
from src.stats_rigor import compute_fao56_vpd_and_pet_series, write_strict_json
from src.weather_power_pipeline import (
    FROZEN_POWER_DIR,
    MONTHLY_CACHE_FILENAME,
    STUDY_BOXES,
    PowerBoxSpec,
    _fetch_point_monthly,
    aggregate_multipoint_with_spherical_weights,
    generate_box_grid_points,
    parse_monthly_power_cache,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "data" / "frozen"

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
GEOBOUNDARIES_UKR_META_URL = "https://www.geoboundaries.org/api/current/gbOpen/UKR/ADM0/"


def load_ukraine_adm0_path(geojson_path: Path = FROZEN_DIR / "ukraine_adm0_geoboundaries_simplified.geojson") -> MplPath:
    """Load the UKR-ADM0 boundary exterior ring into a vectorized Matplotlib Path."""
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    geom = payload["features"][0]["geometry"]
    if geom["type"] == "Polygon":
        coords = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        coords = max((poly[0] for poly in geom["coordinates"]), key=len)
    else:
        raise ValueError(f"Unsupported UKR-ADM0 geometry type: {geom['type']}")
    return MplPath(np.asarray(coords, dtype=float))


def _box_overlap_fraction(box: PowerBoxSpec, ukr_path: MplPath, grid_n: int = 80) -> float:
    """Cos(lat)-weighted fraction of ``box`` falling inside ``ukr_path``."""
    lats = np.linspace(box.south, box.north, grid_n)
    lons = np.linspace(box.west, box.east, grid_n)
    gx, gy = np.meshgrid(lons, lats)
    weights = np.cos(np.radians(gy)).ravel()
    inside = ukr_path.contains_points(np.column_stack([gx.ravel(), gy.ravel()]))
    return float(weights[inside].sum() / weights.sum()) if weights.sum() > 0 else 0.0


def compute_spatial_mask_audit(
    clean_firms_df: pd.DataFrame,
    ukr_path: MplPath,
    boxes: Sequence[PowerBoxSpec] = STUDY_BOXES,
    grid_n: int = 80,
) -> Dict[str, Dict[str, object]]:
    """Quantify box-vs-UKR-ADM0 overlap, POWER 3x3 lattice coverage, and FIRMS border clipping."""
    window_df = clean_firms_df[
        clean_firms_df["year"].isin(STUDY_YEARS) & clean_firms_df["mnum"].isin(STUDY_MONTHS)
    ].copy()
    if not window_df.empty:
        in_ukr = ukr_path.contains_points(window_df[["longitude", "latitude"]].to_numpy(dtype=float))
        window_df["in_ukr"] = in_ukr
    else:
        window_df["in_ukr"] = pd.Series(dtype=bool)

    audit: Dict[str, Dict[str, object]] = {}
    for box in boxes:
        overlap_frac = _box_overlap_fraction(box, ukr_path, grid_n=grid_n)
        pct_box = round(100.0 * overlap_frac, 2)
        est_ukr_km2 = round(box.area_km2 * overlap_frac, 2)

        pts = generate_box_grid_points(box.south, box.north, box.west, box.east, nx=3, ny=3)
        lattice_in = int(ukr_path.contains_points([(lon, lat) for lat, lon in pts]).sum())

        in_box = window_df[
            window_df["latitude"].between(box.south, box.north)
            & window_df["longitude"].between(box.west, box.east)
        ]
        n_box = int(len(in_box))
        n_ukr = int(in_box["in_ukr"].sum()) if n_box > 0 else 0
        pct_firms = round(100.0 * n_ukr / float(n_box), 2) if n_box > 0 else None
        inflation = round(box.area_km2 / est_ukr_km2, 4) if est_ukr_km2 > 0.0 else None

        audit[box.region_id] = {
            "box_bounds": [box.south, box.north, box.west, box.east],
            "box_area_km2": box.area_km2,
            "pct_box_inside_ukr_adm0": pct_box,
            "estimated_ukr_land_km2": est_ukr_km2,
            "lattice_points_inside_ukr_adm0": lattice_in,
            "lattice_points_total": len(pts),
            "firms_detections_in_box": n_box,
            "firms_detections_inside_ukr_adm0": n_ukr,
            "pct_firms_inside_ukr_adm0": pct_firms,
            "area_ratio_inflation_factor": inflation,
        }
    return audit


def _filter_firms_subset(df: pd.DataFrame, subset_id: str) -> pd.DataFrame:
    if subset_id == "type0_nh":
        return df[(df["type"] == 0) & (df["confidence"].isin(["n", "h"]))]
    if subset_id == "type0_all":
        return df[df["type"] == 0]
    if subset_id == "type2_all":
        return df[df["type"] == 2]
    raise ValueError(f"Unknown subset_id: {subset_id}")


def compute_firms_cmr_matched_audit(
    clean_firms_df: pd.DataFrame,
    cmr_inventory: Mapping[str, object],
    spatial_mask_audit: Mapping[str, Mapping[str, object]],
    boxes: Sequence[PowerBoxSpec] = STUDY_BOXES,
) -> Dict[str, object]:
    """Compute CMR-observed-day and matched-calendar-date UKR-land FIRMS rates plus top type=2 cells."""
    window_df = clean_firms_df[
        clean_firms_df["year"].isin(STUDY_YEARS) & clean_firms_df["mnum"].isin(STUDY_MONTHS)
    ].copy()
    zero_days = {str(d) for d in cmr_inventory.get("zero_granule_days", [])}
    zero_mmdd = {d[5:] for d in zero_days}
    daily_counts: Mapping[str, int] = cmr_inventory.get("daily_counts", {})  # type: ignore[assignment]

    def _obs_days(years: Sequence[int]) -> int:
        if daily_counts:
            yr_strs = {str(y) for y in years}
            return sum(1 for d, cnt in daily_counts.items() if d[:4] in yr_strs and int(cnt) > 0)
        return sum(
            int((date(y, 8, 31) - date(y, 3, 1)).days + 1)
            - sum(1 for zd in zero_days if zd.startswith(f"{y}-"))
            for y in years
        )

    base_cmr_days = _obs_days((2019, 2020, 2021))
    t22_cmr_days = _obs_days((2022,))
    matched_days_per_yr = int((date(2022, 8, 31) - date(2022, 3, 1)).days + 1) - len(zero_mmdd)

    window_df["mmdd"] = window_df["acq_date_str"].str[5:]
    regional_matched: Dict[str, Dict[str, Dict[str, object]]] = {}

    for box in boxes:
        if box.role == "external_comparator_weather_only":
            continue
        ukr_km2 = float(spatial_mask_audit[box.region_id]["estimated_ukr_land_km2"])
        in_box = window_df[
            window_df["latitude"].between(box.south, box.north)
            & window_df["longitude"].between(box.west, box.east)
        ]
        matched_box = in_box[~in_box["mmdd"].isin(zero_mmdd)]

        sub_out: Dict[str, Dict[str, object]] = {}
        for subset_id in ("type0_nh", "type0_all", "type2_all"):
            sub_all = _filter_firms_subset(in_box, subset_id)
            sub_mat = _filter_firms_subset(matched_box, subset_id)

            n_base_raw = int(sub_all["year"].isin([2019, 2020, 2021]).sum())
            n_22_raw = int((sub_all["year"] == 2022).sum())
            if n_base_raw > 0 and base_cmr_days > 0 and t22_cmr_days > 0:
                cmr_pct = round(100.0 * ((n_22_raw / float(t22_cmr_days)) / (n_base_raw / float(base_cmr_days)) - 1.0), 2)
            else:
                cmr_pct = None

            n_base_mat = int(sub_mat["year"].isin([2019, 2020, 2021]).sum())
            n_22_mat = int((sub_mat["year"] == 2022).sum())
            denom_base = 3.0 * matched_days_per_yr * (ukr_km2 / 1000.0)
            denom_22 = float(matched_days_per_yr) * (ukr_km2 / 1000.0)
            rate_base = (n_base_mat / denom_base) if denom_base > 0 else 0.0
            rate_22 = (n_22_mat / denom_22) if denom_22 > 0 else 0.0
            mat_pct = round(100.0 * (rate_22 / rate_base - 1.0), 2) if rate_base > 0.0 else None

            sub_out[subset_id] = {
                "base_raw_count": n_base_raw,
                "target_2022_raw_count": n_22_raw,
                "pct_change_cmr_obs_days_box_area": cmr_pct,
                "pct_change_matched_dates_169d": mat_pct,
                "rate_base_matched_ukr_land_per_1k_km2_day": round(rate_base, 4),
                "rate_2022_matched_ukr_land_per_1k_km2_day": round(rate_22, 4),
            }
        regional_matched[box.region_id] = sub_out

    t2_df = window_df[window_df["type"] == 2].copy()
    t2_df["c_lat"] = [round(float(v), 2) for v in t2_df["latitude"]]
    t2_df["c_lon"] = [round(float(v), 2) for v in t2_df["longitude"]]
    top_cells = t2_df.groupby(["c_lat", "c_lon"]).size().sort_values(ascending=False).head(10).index.tolist()

    window_df["c_lat"] = [round(float(v), 2) for v in window_df["latitude"]]
    window_df["c_lon"] = [round(float(v), 2) for v in window_df["longitude"]]
    top_rows: List[Dict[str, object]] = []
    for clat, clon in top_cells:
        c_sub = window_df[(window_df["c_lat"] == clat) & (window_df["c_lon"] == clon)]
        years_map = {
            str(yr): {
                "t0": int(((c_sub["year"] == yr) & (c_sub["type"] == 0)).sum()),
                "t2": int(((c_sub["year"] == yr) & (c_sub["type"] == 2)).sum()),
            }
            for yr in STUDY_YEARS
        }
        top_rows.append({"cell": [float(clat), float(clon)], "years": years_map})

    return {
        "regional_matched_outage": regional_matched,
        "top_static_type2_cells": top_rows,
    }


def compute_kyiv_pet_sensitivities(
    monthly_cache_path: Path = FROZEN_POWER_DIR / MONTHLY_CACHE_FILENAME,
    daily_raw_path: Path = FROZEN_POWER_DIR / "sample_kyiv_center_daily_raw.json",
) -> Dict[str, float]:
    """Compute Kyiv elevation (179m vs DEM) and strict FAO-56 vs legacy PET differences."""
    mdf, _ = parse_monthly_power_cache(monthly_cache_path)
    kyiv = mdf[mdf["region_id"] == "kyiv_no2_box"].sort_values(["year", "month_num"])
    daily_raw = json.loads(daily_raw_path.read_text(encoding="utf-8"))
    elev_dem = float(daily_raw["geometry"]["coordinates"][2])

    t2m = kyiv["t2m"].to_numpy(dtype=float)
    dtr = kyiv["dtr_c"].to_numpy(dtype=float)
    tmax = (t2m + 0.5 * dtr).tolist()
    tmin = (t2m - 0.5 * dtr).tolist()
    rh = kyiv["rh2m"].tolist()
    sw = kyiv["allsky_sfc_sw_dwn"].tolist()
    ws = kyiv["ws10m"].tolist()
    mos = kyiv["month_num"].tolist()
    ps = kyiv["ps"].tolist()
    qv = kyiv["qv2m"].tolist()
    clr = kyiv["clrsky_sfc_sw_dwn"].tolist()
    alb = kyiv["allsky_srf_alb"].tolist()

    pet_179 = np.asarray(
        compute_fao56_vpd_and_pet_series(t2m.tolist(), tmax, tmin, rh, sw, ws, 50.45, 179.0, mos, ps, qv)["pet_mm_day"],
        dtype=float,
    )
    pet_dem = np.asarray(
        compute_fao56_vpd_and_pet_series(t2m.tolist(), tmax, tmin, rh, sw, ws, 50.45, elev_dem, mos, ps, qv)["pet_mm_day"],
        dtype=float,
    )
    pet_leg = np.asarray(
        compute_fao56_vpd_and_pet_series(
            t2m.tolist(), tmax, tmin, rh, sw, ws, 50.45, 179.0, mos, ps, qv,
            clrsky_sw_dwn_mj_m2_day=clr, albedo_series=alb,
            use_reference_albedo=False, use_fao56_clear_sky_rso=False,
        )["pet_mm_day"],
        dtype=float,
    )
    return {
        "kyiv_pet_elevation_179_vs_128_71m_max_abs_diff_mm_day": round(float(np.max(np.abs(pet_179 - pet_dem))), 5),
        "kyiv_pet_strict_fao56_vs_legacy_var_albedo_rmse_mm_day": round(float(np.sqrt(np.mean((pet_179 - pet_leg) ** 2))), 5),
        "kyiv_pet_strict_fao56_vs_legacy_var_albedo_max_abs_mm_day": round(float(np.max(np.abs(pet_179 - pet_leg))), 5),
    }


def _fetch_cmr_daily_inventory(years: Sequence[int] = STUDY_YEARS) -> Dict[str, object]:
    """Optionally refresh daily NASA CMR VNP14IMG granule counts over Ukraine (online)."""
    daily_counts: Dict[str, int] = {}
    zero_days: List[str] = []
    low_days: Dict[str, int] = {}
    for yr in years:
        cur = date(yr, 3, 1)
        end = date(yr, 8, 31)
        while cur <= end:
            day_str = cur.isoformat()
            q = urllib.parse.urlencode(
                {
                    "short_name": "VNP14IMG",
                    "bounding_box": "22.0,44.3,40.3,52.5",
                    "temporal": f"{day_str}T00:00:00Z,{day_str}T23:59:59Z",
                    "page_size": 50,
                }
            )
            with urllib.request.urlopen(f"{CMR_GRANULES_URL}?{q}", timeout=30) as resp:
                entries = json.loads(resp.read().decode("utf-8")).get("feed", {}).get("entry", [])
            cnt = len(entries)
            daily_counts[day_str] = cnt
            if cnt == 0:
                zero_days.append(day_str)
            elif cnt < 4:
                low_days[day_str] = cnt
            cur += timedelta(days=1)
    return {
        "short_name": "VNP14IMG",
        "bounding_box": "22.0,44.3,40.3,52.5",
        "seasons": "Mar-Aug 2019-2022",
        "total_days": len(daily_counts),
        "zero_granule_days": zero_days,
        "low_granule_days_lt4": low_days,
        "daily_counts": daily_counts,
    }


def _fetch_dense_donbas_comparison(
    monthly_cache_path: Path = FROZEN_POWER_DIR / MONTHLY_CACHE_FILENAME,
) -> Dict[str, Dict[str, object]]:
    """Optionally re-fetch dense 4x4 native POWER lattice over donbas_kharkiv_east (online)."""
    donbas = next(b for b in STUDY_BOXES if b.region_id == "donbas_kharkiv_east")
    pts = generate_box_grid_points(donbas.south, donbas.north, donbas.west, donbas.east, nx=4, ny=4)
    node_payloads = []
    for lat, lon in pts:
        m_params, _, _ = _fetch_point_monthly(lat, lon, 2015, 2022)
        node_payloads.append((lat, m_params))
    dense = aggregate_multipoint_with_spherical_weights(node_payloads)

    mdf, _ = parse_monthly_power_cache(monthly_cache_path)
    sub = mdf[mdf["region_id"] == "donbas_kharkiv_east"].sort_values(["year", "month_num"])
    base_raw = json.loads(monthly_cache_path.read_text(encoding="utf-8"))["regions"]["donbas_kharkiv_east"]["parameters"]
    comparison: Dict[str, Dict[str, object]] = {}
    ym_keys = sorted(k for k in base_raw.get("T2M", {}) if len(k) == 6 and k.isdigit())
    for param in ("T2M", "PRECTOTCORR", "EVPTRNS", "ALLSKY_SFC_SW_DWN", "CLOUD_AMT", "ALLSKY_SRF_ALB"):
        a3 = np.array([float(base_raw[param][k]) for k in ym_keys])
        ad = np.array([float(dense[param][k]) for k in ym_keys])
        diff = a3 - ad
        ma_base = np.array([2019 <= int(k[:4]) <= 2021 and 3 <= int(k[4:]) <= 8 for k in ym_keys])
        ma_22 = np.array([int(k[:4]) == 2022 and 3 <= int(k[4:]) <= 8 for k in ym_keys])
        comparison[param] = {
            "n_months": len(ym_keys),
            "mean_bias_3x3_minus_native": round(float(np.mean(diff)), 5),
            "rmse": round(float(np.sqrt(np.mean(diff ** 2))), 5),
            "max_abs_diff": round(float(np.max(np.abs(diff))), 5),
            "mar_aug_2022_vs_2019_2021_diff_3x3": round(float(np.mean(a3[ma_22]) - np.mean(a3[ma_base])), 5),
            "mar_aug_2022_vs_2019_2021_diff_native": round(float(np.mean(ad[ma_22]) - np.mean(ad[ma_base])), 5),
        }
    return comparison


def regenerate_audit_summaries(
    firms_raw_dir: Path = DEFAULT_FIRE_RAW_DIR,
    frozen_dir: Path = FROZEN_DIR,
    out_dir: Optional[Path] = None,
    fetch_upstream: bool = False,
) -> Dict[str, Path]:
    """Regenerate spatial_mask_audit.json, firms_cmr_matched_audit.json, and PET summary checks."""
    target_dir = out_dir or frozen_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    power_target_dir = target_dir / "nasa_power"
    power_target_dir.mkdir(parents=True, exist_ok=True)

    ukr_path = load_ukraine_adm0_path(frozen_dir / "ukraine_adm0_geoboundaries_simplified.geojson")
    firms_inputs = discover_fire_inputs(firms_raw_dir)
    clean_firms_df, _ = load_and_validate_firms_archives(firms_inputs)

    cmr_path = frozen_dir / "firms_cmr_vnp14img_daily_2019_2022.json"
    if fetch_upstream:
        cmr_inv = _fetch_cmr_daily_inventory()
        write_strict_json(target_dir / cmr_path.name, cmr_inv)
    else:
        cmr_inv = json.loads(cmr_path.read_text(encoding="utf-8"))

    spatial_audit = compute_spatial_mask_audit(clean_firms_df, ukr_path)
    spatial_out = target_dir / "spatial_mask_audit.json"
    write_strict_json(spatial_out, spatial_audit)

    cmr_audit = compute_firms_cmr_matched_audit(clean_firms_df, cmr_inv, spatial_audit)
    cmr_out = target_dir / "firms_cmr_matched_audit.json"
    write_strict_json(cmr_out, cmr_audit)

    native_src = frozen_dir / "nasa_power" / "native_grid_vs_3x3_summary.json"
    native_payload = json.loads(native_src.read_text(encoding="utf-8")) if native_src.is_file() else {}
    if fetch_upstream:
        native_payload["donbas_kharkiv_east_3x3_vs_dense_native"] = _fetch_dense_donbas_comparison(
            frozen_dir / "nasa_power" / MONTHLY_CACHE_FILENAME
        )
    native_payload.update(
        compute_kyiv_pet_sensitivities(
            frozen_dir / "nasa_power" / MONTHLY_CACHE_FILENAME,
            frozen_dir / "nasa_power" / "sample_kyiv_center_daily_raw.json",
        )
    )
    native_out = power_target_dir / "native_grid_vs_3x3_summary.json"
    write_strict_json(native_out, native_payload)

    return {
        "spatial_mask_audit": spatial_out,
        "firms_cmr_matched_audit": cmr_out,
        "native_grid_vs_3x3_summary": native_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate spatial mask, CMR matched-date Fire, and Kyiv PET sensitivity audit JSONs."
    )
    parser.add_argument("--firms-dir", type=Path, default=DEFAULT_FIRE_RAW_DIR)
    parser.add_argument("--frozen-dir", type=Path, default=FROZEN_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--fetch-upstream",
        action="store_true",
        help="Re-query NASA CMR VNP14IMG and dense 4x4 NASA POWER native grid (requires network).",
    )
    args = parser.parse_args()

    outputs = regenerate_audit_summaries(
        firms_raw_dir=args.firms_dir,
        frozen_dir=args.frozen_dir,
        out_dir=args.out_dir,
        fetch_upstream=args.fetch_upstream,
    )
    for key, path in outputs.items():
        print(f"Wrote {key} -> {path}")


if __name__ == "__main__":
    main()
