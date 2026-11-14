"""NASA POWER MERRA-2 / CERES multi-element weather, hydrology, and land pipeline.

Fetches, caches, spatially aggregates (3x3 cos(lat) spherical grid), validates,
and derives physical Water, Earth, Thermal/Fire-weather, and Air-meteorology
series (2015–2022) aligned cleanly with the Ukraine OMI NO2 and VIIRS regions.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.fire_analysis import PROPOSED_REGIONS
from src.stats_rigor import (
    bbox_area_km2,
    clean_float,
    compute_fao56_vpd_and_pet_series,
    spherical_area_weighted_mean,
    write_strict_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POWER_DIR = REPO_ROOT / "data" / "raw" / "nasa_power"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"

MONTHLY_CACHE_FILENAME = "ukraine_power_monthly_2015_2022.json"
DAILY_CACHE_FILENAME = "kyiv_power_daily_2015_2022.json"

POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
USER_AGENT = "war-environment-tracker/1.0 (+NASA-SpaceApps)"

POWER_MONTHLY_BATCH_1: Tuple[str, ...] = (
    "PRECTOTCORR",
    "QV2M",
    "RH2M",
    "EVPTRNS",
    "GWETTOP",
    "GWETROOT",
    "GWETPROF",
    "ALLSKY_SRF_ALB",
    "TS",
)
POWER_MONTHLY_BATCH_2: Tuple[str, ...] = (
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "ALLSKY_SFC_SW_DWN",
    "CLRSKY_SFC_SW_DWN",
    "CLOUD_AMT",
    "WS10M",
    "PS",
)
RAW_MONTHLY_PARAMETERS: Tuple[str, ...] = POWER_MONTHLY_BATCH_1 + POWER_MONTHLY_BATCH_2

KYIV_DAILY_PARAMETERS: Tuple[str, ...] = (
    "WS10M",
    "PS",
    "CLOUD_AMT",
    "T2M",
    "PRECTOTCORR",
    "RH2M",
    "QV2M",
    "GWETTOP",
    "TS",
    "ALLSKY_SFC_SW_DWN",
    "CLRSKY_SFC_SW_DWN",
)

MJ_M2_DAY_TO_WM2 = 1_000_000.0 / 86_400.0

REGION_ELEVATIONS_M: Dict[str, float] = {
    "kyiv_no2_box": 179.0,
    "kyiv_north_belt": 145.0,
    "donbas_kharkiv_east": 160.0,
    "south_steppe_belt": 55.0,
    "central_interior_cand": 230.0,
    "west_ukraine_cand": 300.0,
    "poland_krakow": 219.0,
    "czechia_prague": 235.0,
}

REGION_ROLE_OVERRIDES: Dict[str, str] = {
    "kyiv_no2_box": "primary_urban_study",
    "kyiv_north_belt": "war_theater_study",
    "donbas_kharkiv_east": "war_theater_study",
    "south_steppe_belt": "war_theater_study",
    "central_interior_cand": "ukraine_reference_region",
    "west_ukraine_cand": "ukraine_reference_region",
    "poland_krakow": "external_comparator_weather_only",
    "czechia_prague": "external_comparator_weather_only",
}


@dataclass(frozen=True)
class PowerBoxSpec:
    """Geographic bounding box and metadata for NASA POWER spatial extraction."""

    region_id: str
    name: str
    role: str
    south: float
    north: float
    west: float
    east: float
    elevation_m: float
    description: str

    @property
    def center_lat(self) -> float:
        return round(0.5 * (self.south + self.north), 4)

    @property
    def center_lon(self) -> float:
        return round(0.5 * (self.west + self.east), 4)

    @property
    def area_km2(self) -> float:
        return bbox_area_km2(self.west, self.south, self.east, self.north)


def build_study_boxes() -> Tuple[PowerBoxSpec, ...]:
    """Build study boxes anchored to fire_analysis.PROPOSED_REGIONS + EU weather comparators."""
    specs: List[PowerBoxSpec] = []
    for reg in PROPOSED_REGIONS:
        if reg.region_id == "ukraine_national":
            continue
        specs.append(
            PowerBoxSpec(
                region_id=reg.region_id,
                name=reg.name,
                role=REGION_ROLE_OVERRIDES.get(reg.region_id, reg.role),
                south=reg.south,
                north=reg.north,
                west=reg.west,
                east=reg.east,
                elevation_m=REGION_ELEVATIONS_M.get(reg.region_id, 180.0),
                description=reg.description,
            )
        )
    # External weather comparators matching docs/study-spec.md (no NO2 retrieved via API here)
    specs.extend(
        [
            PowerBoxSpec(
                region_id="poland_krakow",
                name="Krakow Box (Poland, meteorological context)",
                role="external_comparator_weather_only",
                south=49.8147,
                north=50.3147,
                west=19.6950,
                east=20.1950,
                elevation_m=REGION_ELEVATIONS_M["poland_krakow"],
                description="0.5 deg external EU reference city box for synoptic climate comparison.",
            ),
            PowerBoxSpec(
                region_id="czechia_prague",
                name="Prague Box (Czechia, meteorological context)",
                role="external_comparator_weather_only",
                south=49.8255,
                north=50.3255,
                west=14.1878,
                east=14.6878,
                elevation_m=REGION_ELEVATIONS_M["czechia_prague"],
                description="0.5 deg external EU reference city box for synoptic climate comparison.",
            ),
        ]
    )
    return tuple(specs)


STUDY_BOXES: Tuple[PowerBoxSpec, ...] = build_study_boxes()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_box_grid_points(
    south: float,
    north: float,
    west: float,
    east: float,
    nx: int = 3,
    ny: int = 3,
) -> List[Tuple[float, float]]:
    """Generate a deterministic (ny x nx) lattice inside a lat/lon bounding box."""
    pts: List[Tuple[float, float]] = []
    for iy in range(ny):
        fy = 0.5 if ny == 1 else iy / float(ny - 1)
        lat_pt = south + fy * (north - south)
        for ix in range(nx):
            fx = 0.5 if nx == 1 else ix / float(nx - 1)
            lon_pt = west + fx * (east - west)
            pts.append((round(lat_pt, 4), round(lon_pt, 4)))
    return pts


def aggregate_multipoint_with_spherical_weights(
    grid_point_payloads: Sequence[Tuple[float, Mapping[str, Mapping[str, float]]]],
) -> Dict[str, Dict[str, float]]:
    """Aggregate multiple NASA POWER node dicts with cos(latitude) weights."""
    if not grid_point_payloads:
        return {}
    all_param_ids = sorted({p for _, node_params in grid_point_payloads for p in node_params.keys()})
    aggregated: Dict[str, Dict[str, float]] = {}
    for param_id in all_param_ids:
        all_t_keys = sorted(
            {t_key for _, node_params in grid_point_payloads for t_key in node_params.get(param_id, {}).keys()}
        )
        agg_series: Dict[str, float] = {}
        for t_key in all_t_keys:
            valid_lats: List[float] = []
            valid_vals: List[float] = []
            for lat_deg, node_params in grid_point_payloads:
                val = node_params.get(param_id, {}).get(t_key, -999.0)
                if val is not None and math.isfinite(float(val)) and float(val) > -900.0:
                    valid_lats.append(float(lat_deg))
                    valid_vals.append(float(val))
            if valid_vals:
                agg_series[t_key] = round(spherical_area_weighted_mean(valid_lats, valid_vals), 5)
            else:
                agg_series[t_key] = -999.0
        aggregated[param_id] = agg_series
    return aggregated


def _fetch_power_json(url: str, max_retries: int = 3) -> Dict[str, object]:
    last_err: Exception = RuntimeError("Unreachable fetch loop")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, http.client.HTTPException) as exc:
            last_err = exc
            if attempt + 1 < max_retries:
                time.sleep(1.5 * (2 ** attempt))
    raise last_err


def _build_power_url(
    base_url: str,
    lat: float,
    lon: float,
    params: Sequence[str],
    start: str,
    end: str,
) -> str:
    return (
        f"{base_url}"
        f"?parameters={','.join(params)}"
        f"&community=AG"
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={start}"
        f"&end={end}"
        f"&format=JSON"
    )


def _fetch_point_monthly(lat: float, lon: float, start_year: int, end_year: int) -> Tuple[dict, dict, dict]:
    p1 = _fetch_power_json(_build_power_url(POWER_MONTHLY_URL, lat, lon, POWER_MONTHLY_BATCH_1, str(start_year), str(end_year)))
    p2 = _fetch_power_json(_build_power_url(POWER_MONTHLY_URL, lat, lon, POWER_MONTHLY_BATCH_2, str(start_year), str(end_year)))
    params = {}
    params.update(p1.get("properties", {}).get("parameter", {}))
    params.update(p2.get("properties", {}).get("parameter", {}))
    meta = {}
    meta.update(p1.get("parameters", {}))
    meta.update(p2.get("parameters", {}))
    return params, meta, p1.get("header", {})


def _fetch_kyiv_daily(box: PowerBoxSpec, start_ymd: str = "20150101", end_ymd: str = "20221231") -> Dict[str, object]:
    payload = _fetch_power_json(
        _build_power_url(POWER_DAILY_URL, box.center_lat, box.center_lon, KYIV_DAILY_PARAMETERS, start_ymd, end_ymd)
    )
    return {
        "metadata": {
            **asdict(box),
            "center_lat": box.center_lat,
            "center_lon": box.center_lon,
            "temporal_resolution": "daily",
            "start_date": start_ymd,
            "end_date": end_ymd,
            "source_api": POWER_DAILY_URL,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "parameters": payload.get("properties", {}).get("parameter", {}),
        "parameter_metadata": payload.get("parameters", {}),
        "header": payload.get("header", {}),
    }


def fetch_and_cache_power_datasets(
    out_dir: Path = DEFAULT_POWER_DIR,
    start_year: int = 2015,
    end_year: int = 2022,
    boxes: Sequence[PowerBoxSpec] = STUDY_BOXES,
    max_workers: int = 4,
) -> Tuple[Path, Path]:
    """Fetch live NASA POWER monthly (3x3 cos-lat grid) + Kyiv daily caches cleanly."""
    out_dir.mkdir(parents=True, exist_ok=True)
    monthly_payload: Dict[str, object] = {
        "schema_version": "1.0.0",
        "source_api": POWER_MONTHLY_URL,
        "spatial_sampling": "spherical_cosine_lat_weighted_3x3_grid",
        "spatial_resolution_note": (
            "MERRA-2 meteorological and land fields are ~0.5 deg x 0.625 deg; CERES radiative "
            "fluxes are ~1.0 deg. Sampling a 3x3 cos(lat) lattice preserves box-edge straddling."
        ),
        "start_year": start_year,
        "end_year": end_year,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "regions": {},
    }

    regions_dict: Dict[str, object] = {}
    for box in boxes:
        grid_pts = generate_box_grid_points(box.south, box.north, box.west, box.east, nx=3, ny=3)
        node_results: List[Tuple[float, Dict[str, Dict[str, float]], dict, dict]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(_fetch_point_monthly, lat, lon, start_year, end_year): (lat, lon) for lat, lon in grid_pts}
            for fut in as_completed(futs):
                lat, _ = futs[fut]
                m_params, m_info, hdr = fut.result()
                node_results.append((lat, m_params, m_info, hdr))
        # Preserve deterministic ordering by latitude/index when inspecting parameter metadata
        node_results.sort(key=lambda item: item[0])
        merged_params = aggregate_multipoint_with_spherical_weights([(item[0], item[1]) for item in node_results])
        regions_dict[box.region_id] = {
            "metadata": {
                **asdict(box),
                "center_lat": box.center_lat,
                "center_lon": box.center_lon,
                "area_km2": round(box.area_km2, 2),
                "grid_points": grid_pts,
            },
            "parameters": merged_params,
            "parameter_metadata": node_results[0][2] if node_results else {},
            "header": node_results[0][3] if node_results else {},
        }
    monthly_payload["regions"] = regions_dict

    monthly_path = out_dir / MONTHLY_CACHE_FILENAME
    write_strict_json(monthly_path, monthly_payload)

    kyiv_box = next(b for b in boxes if b.region_id == "kyiv_no2_box")
    daily_payload = _fetch_kyiv_daily(kyiv_box, start_ymd=f"{start_year}0101", end_ymd=f"{end_year}1231")
    daily_path = out_dir / DAILY_CACHE_FILENAME
    write_strict_json(daily_path, daily_payload)
    return monthly_path, daily_path


def _clean_power_val(val: object) -> float:
    if val is None:
        return float("nan")
    f = float(val)
    return f if (math.isfinite(f) and f > -900.0) else float("nan")


def parse_monthly_power_cache(cache_path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Parse cached NASA POWER monthly dataset into a clean panel DataFrame + metadata."""
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    rows: List[Dict[str, object]] = []
    region_meta: Dict[str, object] = {}

    for region_id, entry in raw.get("regions", {}).items():
        meta = dict(entry.get("metadata", {}))
        region_meta[region_id] = meta
        params = entry.get("parameters", {})
        ym_keys = sorted(
            {
                k
                for p_dict in params.values()
                for k in p_dict.keys()
                if len(k) == 6 and k.isdigit() and 1 <= int(k[4:]) <= 12
            }
        )
        raw_rows: List[Dict[str, object]] = []
        for ym in ym_keys:
            yr, mo = int(ym[:4]), int(ym[4:])
            row: Dict[str, object] = {
                "region_id": region_id,
                "region_name": meta.get("name", region_id),
                "role": meta.get("role", "unknown"),
                "month": f"{yr:04d}-{mo:02d}",
                "year": yr,
                "month_num": mo,
            }
            for p_name in RAW_MONTHLY_PARAMETERS:
                row[p_name.lower()] = _clean_power_val(params.get(p_name, {}).get(ym))
            raw_rows.append(row)

        if not raw_rows:
            continue
        reg_df = pd.DataFrame(raw_rows).sort_values(["year", "month_num"]).reset_index(drop=True)
        derived = compute_fao56_vpd_and_pet_series(
            t2m_c=reg_df["t2m"].tolist(),
            t2m_max_c=reg_df["t2m_max"].tolist(),
            t2m_min_c=reg_df["t2m_min"].tolist(),
            rh2m_pct=reg_df["rh2m"].tolist(),
            sw_dwn_mj_m2_day=reg_df["allsky_sfc_sw_dwn"].tolist(),
            ws10m_m_s=reg_df["ws10m"].tolist(),
            lat_deg=float(meta.get("center_lat", 50.0)),
            elevation_m=float(meta.get("elevation_m", 180.0)),
            months=reg_df["month_num"].tolist(),
            ps_kpa_series=reg_df["ps"].tolist(),
            qv2m_g_kg_series=reg_df["qv2m"].tolist(),
            clrsky_sw_dwn_mj_m2_day=reg_df["clrsky_sfc_sw_dwn"].tolist(),
            albedo_series=reg_df["allsky_srf_alb"].tolist(),
        )
        reg_df["vpd_kpa"] = derived["vpd_kpa"]
        reg_df["pet_fao56_mm_day"] = derived["pet_mm_day"]
        reg_df["pet_rad_mm_day"] = derived["pet_rad_mm_day"]
        reg_df["pet_aero_mm_day"] = derived["pet_aero_mm_day"]

        lambda_vec = np.maximum(2.2, 2.501 - 0.002361 * reg_df["t2m"].to_numpy(dtype=float))
        reg_df["evptrns_mm_day"] = reg_df["evptrns"].to_numpy(dtype=float) / lambda_vec
        reg_df["ts_minus_t2m_c"] = reg_df["ts"] - reg_df["t2m"]
        reg_df["dtr_c"] = reg_df["t2m_max"] - reg_df["t2m_min"]
        reg_df["precip_minus_pet_mm_day"] = reg_df["prectotcorr"] - reg_df["pet_fao56_mm_day"]
        reg_df["cloud_radiative_attenuation_wm2"] = (
            reg_df["clrsky_sfc_sw_dwn"] - reg_df["allsky_sfc_sw_dwn"]
        ) * MJ_M2_DAY_TO_WM2
        rows.extend(reg_df.to_dict(orient="records"))

    panel_df = pd.DataFrame(rows)
    if not panel_df.empty:
        panel_df = panel_df.sort_values(["region_id", "year", "month_num"]).reset_index(drop=True)
    metadata = {
        "cache_path": str(cache_path),
        "sha256": sha256_file(cache_path),
        "schema_version": raw.get("schema_version"),
        "source_api": raw.get("source_api"),
        "spatial_sampling": raw.get("spatial_sampling"),
        "regions": region_meta,
    }
    return panel_df, metadata


def parse_daily_power_cache(cache_path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Parse cached Kyiv daily NASA POWER JSON into a clean date-indexed DataFrame."""
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    params = raw.get("parameters", {})
    ymd_keys = sorted({k for p_dict in params.values() for k in p_dict.keys() if len(k) == 8 and k.isdigit()})
    records: List[Dict[str, object]] = []
    for ymd in ymd_keys:
        rec: Dict[str, object] = {"date": pd.to_datetime(ymd, format="%Y%m%d")}
        for p_name in KYIV_DAILY_PARAMETERS:
            rec[p_name.lower()] = _clean_power_val(params.get(p_name, {}).get(ymd))
        records.append(rec)

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    if not df.empty:
        df["ts_minus_t2m_c"] = df["ts"] - df["t2m"]
        df["cloud_radiative_attenuation_wm2"] = (
            df["clrsky_sfc_sw_dwn"] - df["allsky_sfc_sw_dwn"]
        ) * MJ_M2_DAY_TO_WM2
    meta = {
        "cache_path": str(cache_path),
        "sha256": sha256_file(cache_path),
        "metadata": raw.get("metadata", {}),
        "parameter_metadata": {k: v.get("units") for k, v in raw.get("parameter_metadata", {}).items()},
    }
    return df, meta


def load_power_panels(
    power_dir: Path = DEFAULT_POWER_DIR,
    fetch_if_missing: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    """Load cached monthly and daily NASA POWER panels (optionally fetching if absent)."""
    monthly_path = power_dir / MONTHLY_CACHE_FILENAME
    daily_path = power_dir / DAILY_CACHE_FILENAME
    if not monthly_path.is_file() or not daily_path.is_file():
        if not fetch_if_missing:
            raise FileNotFoundError(
                f"NASA POWER cache files not found in {power_dir}. "
                "Run `python -m src.weather_power_pipeline --fetch` first."
            )
        fetch_and_cache_power_datasets(out_dir=power_dir)

    monthly_df, monthly_meta = parse_monthly_power_cache(monthly_path)
    daily_df, daily_meta = parse_daily_power_cache(daily_path)
    provenance = {
        "monthly": monthly_meta,
        "daily_kyiv": daily_meta,
    }
    return monthly_df, daily_df, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and validate NASA POWER 4-element datasets for Ukraine.")
    parser.add_argument("--fetch", action="store_true", help="Download live NASA POWER caches.")
    parser.add_argument("--power-dir", type=Path, default=DEFAULT_POWER_DIR)
    args = parser.parse_args()

    if args.fetch:
        m_path, d_path = fetch_and_cache_power_datasets(out_dir=args.power_dir)
        print(f"Cached monthly NASA POWER JSON -> {m_path} (sha256={sha256_file(m_path)[:12]}...)")
        print(f"Cached Kyiv daily NASA POWER JSON -> {d_path} (sha256={sha256_file(d_path)[:12]}...)")

    monthly_df, daily_df, prov = load_power_panels(power_dir=args.power_dir, fetch_if_missing=False)
    print(f"Loaded monthly panel: {len(monthly_df)} region-months across {monthly_df['region_id'].nunique()} regions.")
    print(f"Loaded Kyiv daily panel: {len(daily_df)} days ({daily_df['date'].min().date()} .. {daily_df['date'].max().date()}).")


if __name__ == "__main__":
    main()
