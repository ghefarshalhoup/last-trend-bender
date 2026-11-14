"""Reproducible NASA FIRMS VIIRS S-NPP (SV-C2) ingestion, validation, and accounting pipeline."""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zipfile import ZipFile

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIRE_RAW_DIR = REPO_ROOT / "data" / "raw" / "firms_viirs"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"

REQUIRED_FIRMS_COLUMNS = [
    "latitude",
    "longitude",
    "brightness",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_t31",
    "frp",
    "daynight",
    "type",
]

DEDUP_KEY_COLUMNS = [
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "version",
]

FIRMS_TYPE_LABELS = {
    0: "presumed_vegetation_fire",
    1: "active_volcano",
    2: "other_static_land_source",
    3: "offshore",
}

FIRMS_CONFIDENCE_LABELS = {
    "l": "low",
    "n": "nominal",
    "h": "high",
}

STUDY_MONTHS = (3, 4, 5, 6, 7, 8)
STUDY_YEARS = (2019, 2020, 2021, 2022)
REPEAT_GRID_DEG = 0.01  # ~1.1 km lat x ~0.72 km lon at 49N (diagnostics only)


@dataclass(frozen=True)
class RegionSpec:
    region_id: str
    name: str
    role: str
    south: float
    north: float
    west: float
    east: float
    description: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean_float(val: object, digits: Optional[int] = None) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits) if digits is not None else f


def discover_fire_inputs(raw_dir: Path = DEFAULT_FIRE_RAW_DIR) -> List[Path]:
    """Locate FIRMS SV-C2 .zip archives (or fallback .csv files) in sorted filename order."""
    if not raw_dir.exists():
        raise FileNotFoundError(f"FIRMS raw input directory does not exist: {raw_dir}")
    zips = sorted(raw_dir.glob("*.zip"))
    if zips:
        return zips
    csvs = sorted(raw_dir.glob("*.csv"))
    if csvs:
        return csvs
    raise FileNotFoundError(f"No .zip or .csv FIRMS files found in {raw_dir}")


def _validate_acq_time_series(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.strip().str.zfill(4)
    is_digits = cleaned.str.match(r"^\d{4}$", na=False)
    hh = pd.to_numeric(cleaned.where(is_digits, "").str[:2], errors="coerce")
    mm = pd.to_numeric(cleaned.where(is_digits, "").str[2:4], errors="coerce")
    return is_digits & hh.between(0, 23) & mm.between(0, 59)


def _read_single_firms_source(path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Read raw FIRMS CSV or ZipFile without altering the source archive."""
    readme_text: Optional[str] = None
    if path.suffix.lower() == ".zip":
        zip_bytes = path.stat().st_size
        zip_sha = _sha256_file(path)
        with ZipFile(path, "r") as zf:
            csv_members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_members:
                raise ValueError(f"Archive {path.name} contains no CSV member.")
            csv_name = csv_members[0]
            raw_bytes = zf.read(csv_name)
            readme_members = [n for n in zf.namelist() if n.lower().startswith("readme")]
            if readme_members:
                readme_text = zf.read(readme_members[0]).decode("utf-8-sig", errors="replace").strip()
        container_meta = {
            "archive_file": path.name,
            "archive_sha256": zip_sha,
            "archive_bytes": int(zip_bytes),
            "csv_member": csv_name,
            "csv_sha256": _sha256_bytes(raw_bytes),
            "csv_bytes": int(len(raw_bytes)),
            "readme_excerpt": readme_text,
        }
        text = raw_bytes.decode("utf-8-sig")
    elif path.suffix.lower() == ".csv":
        raw_bytes = path.read_bytes()
        container_meta = {
            "archive_file": None,
            "archive_sha256": None,
            "archive_bytes": None,
            "csv_member": path.name,
            "csv_sha256": _sha256_bytes(raw_bytes),
            "csv_bytes": int(len(raw_bytes)),
            "readme_excerpt": None,
        }
        text = raw_bytes.decode("utf-8-sig")
    else:
        raise ValueError(f"Unsupported FIRMS input format: {path}")

    df = pd.read_csv(io.StringIO(text), dtype={"acq_time": str, "confidence": str, "version": str})
    missing_cols = [c for c in REQUIRED_FIRMS_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"{path.name} is missing required FIRMS columns: {missing_cols}")

    container_meta["columns"] = list(df.columns)
    container_meta["raw_row_count"] = int(len(df))
    return df, container_meta


def load_and_validate_firms_archives(
    input_paths: Sequence[Path],
    years_expected: Sequence[int] = STUDY_YEARS,
    months_expected: Sequence[int] = STUDY_MONTHS,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Load all FIRMS archives/CSVs, validate coordinates/times/numeric fields,
    deduplicate exact duplicate records, and build a complete quality & provenance report.
    """
    frames: List[pd.DataFrame] = []
    file_provenance: List[Dict[str, object]] = []
    total_raw_rows = 0

    for src_path in sorted(input_paths):
        raw_df, fmeta = _read_single_firms_source(src_path)
        total_raw_rows += len(raw_df)
        raw_df = raw_df.copy()
        raw_df["source_file"] = str(fmeta["archive_file"] or fmeta["csv_member"])
        frames.append(raw_df)

        fmeta["date_min"] = str(raw_df["acq_date"].min()) if not raw_df.empty else None
        fmeta["date_max"] = str(raw_df["acq_date"].max()) if not raw_df.empty else None
        fmeta["satellites"] = sorted(raw_df["satellite"].astype(str).unique().tolist())
        fmeta["instruments"] = sorted(raw_df["instrument"].astype(str).unique().tolist())
        fmeta["versions"] = sorted(raw_df["version"].astype(str).unique().tolist())
        file_provenance.append(fmeta)

    if not frames:
        raise ValueError("No FIRMS frames loaded.")

    combined = pd.concat(frames, ignore_index=True)

    # Normalize & validate fields without modifying raw archives
    combined["latitude"] = pd.to_numeric(combined["latitude"], errors="coerce")
    combined["longitude"] = pd.to_numeric(combined["longitude"], errors="coerce")
    combined["brightness"] = pd.to_numeric(combined["brightness"], errors="coerce")
    combined["bright_t31"] = pd.to_numeric(combined["bright_t31"], errors="coerce")
    combined["frp"] = pd.to_numeric(combined["frp"], errors="coerce")
    combined["scan"] = pd.to_numeric(combined["scan"], errors="coerce")
    combined["track"] = pd.to_numeric(combined["track"], errors="coerce")
    combined["type"] = pd.to_numeric(combined["type"], errors="coerce")
    combined["confidence"] = combined["confidence"].astype(str).str.strip().str.lower()
    combined["satellite"] = combined["satellite"].astype(str).str.strip()
    combined["instrument"] = combined["instrument"].astype(str).str.strip()
    combined["version"] = combined["version"].astype(str).str.strip()
    combined["daynight"] = combined["daynight"].astype(str).str.strip().str.upper()
    combined["acq_time"] = combined["acq_time"].astype(str).str.strip().str.zfill(4)
    combined["acq_date_str"] = combined["acq_date"].astype(str).str.strip().str[:10]
    parsed_dt = pd.to_datetime(combined["acq_date_str"], format="%Y-%m-%d", errors="coerce")

    valid_lat = combined["latitude"].notna() & combined["latitude"].between(-90.0, 90.0)
    valid_lon = combined["longitude"].notna() & combined["longitude"].between(-180.0, 180.0)
    valid_date = parsed_dt.notna()
    valid_time = _validate_acq_time_series(combined["acq_time"])
    valid_conf = combined["confidence"].isin(set(FIRMS_CONFIDENCE_LABELS.keys()))
    valid_type = combined["type"].notna() & combined["type"].isin(set(FIRMS_TYPE_LABELS.keys()))
    valid_numeric = combined["brightness"].notna() & combined["frp"].notna()

    is_valid_row = valid_lat & valid_lon & valid_date & valid_time & valid_type
    invalid_coord_rows = int((~(valid_lat & valid_lon)).sum())
    invalid_date_rows = int((~valid_date).sum())
    invalid_time_rows = int((~valid_time).sum())
    invalid_type_rows = int((~valid_type).sum())
    invalid_conf_rows = int((~valid_conf).sum())
    invalid_numeric_rows = int((~valid_numeric).sum())
    nonpositive_frp_rows = int((combined["frp"].notna() & (combined["frp"] <= 0.0)).sum())

    validated = combined.loc[is_valid_row].copy()
    validated["acq_date"] = parsed_dt.loc[is_valid_row]
    validated["year"] = validated["acq_date"].dt.year.astype(int)
    validated["mnum"] = validated["acq_date"].dt.month.astype(int)
    validated["month"] = validated["acq_date"].dt.strftime("%Y-%m")
    validated["type"] = validated["type"].astype(int)

    # Remove exact duplicate records across space/time/sensor/version key
    pre_dedup = int(len(validated))
    exact_dup_mask = validated.duplicated(subset=DEDUP_KEY_COLUMNS, keep="first")
    exact_duplicates_removed = int(exact_dup_mask.sum())
    clean_df = validated.loc[~exact_dup_mask].copy().reset_index(drop=True)

    # Enforce requested study year/month window check
    in_study_window = clean_df["year"].isin(years_expected) & clean_df["mnum"].isin(months_expected)
    out_of_window_rows = int((~in_study_window).sum())
    clean_df = clean_df.loc[in_study_window].copy().reset_index(drop=True)

    # Check completeness of March-August calendar days in every expected year
    missing_dates_by_year: Dict[str, List[str]] = {}
    observed_days_summary: Dict[str, Dict[str, object]] = {}
    for yr in years_expected:
        start_d = date(int(yr), min(months_expected), 1)
        end_m = max(months_expected)
        next_m_start = date(int(yr) + (1 if end_m == 12 else 0), 1 if end_m == 12 else end_m + 1, 1)
        end_d = next_m_start - timedelta(days=1)

        all_expected_days: List[str] = []
        cur = start_d
        while cur <= end_d:
            if cur.month in months_expected:
                all_expected_days.append(cur.isoformat())
            cur += timedelta(days=1)

        yr_df = clean_df[clean_df["year"] == yr]
        present_dates = set(yr_df["acq_date_str"].unique())
        missing = [d for d in all_expected_days if d not in present_dates]
        missing_dates_by_year[str(yr)] = missing
        observed_days_summary[str(yr)] = {
            "expected_calendar_days": len(all_expected_days),
            "observed_active_dates": len(present_dates),
            "missing_dates_count": len(missing),
            "missing_dates": missing,
            "date_min_observed": str(yr_df["acq_date_str"].min()) if not yr_df.empty else None,
            "date_max_observed": str(yr_df["acq_date_str"].max()) if not yr_df.empty else None,
            "clean_rows": int(len(yr_df)),
        }

    # Confidence & type breakdown across clean records
    type_counts = {
        FIRMS_TYPE_LABELS[int(t)]: int((clean_df["type"] == int(t)).sum())
        for t in sorted(clean_df["type"].unique())
    }
    conf_counts = {
        FIRMS_CONFIDENCE_LABELS.get(str(c), str(c)): int((clean_df["confidence"] == str(c)).sum())
        for c in sorted(clean_df["confidence"].unique())
    }
    type_by_year: Dict[str, Dict[str, int]] = {}
    conf_by_year: Dict[str, Dict[str, int]] = {}
    for yr in years_expected:
        sub = clean_df[clean_df["year"] == yr]
        type_by_year[str(yr)] = {
            FIRMS_TYPE_LABELS[t]: int((sub["type"] == t).sum())
            for t in (0, 1, 2, 3)
            if (sub["type"] == t).any()
        }
        conf_by_year[str(yr)] = {
            FIRMS_CONFIDENCE_LABELS[c]: int((sub["confidence"] == c).sum())
            for c in ("l", "n", "h")
            if (sub["confidence"] == c).any()
        }

    # Spatial grid index for repeated-detection metrics (~0.01 deg grid)
    clean_df["cell_lat"] = clean_df["latitude"].round(2)
    clean_df["cell_lon"] = clean_df["longitude"].round(2)

    lat_min = _clean_float(clean_df["latitude"].min(), 5) if not clean_df.empty else None
    lat_max = _clean_float(clean_df["latitude"].max(), 5) if not clean_df.empty else None
    lon_min = _clean_float(clean_df["longitude"].min(), 5) if not clean_df.empty else None
    lon_max = _clean_float(clean_df["longitude"].max(), 5) if not clean_df.empty else None

    quality_report: Dict[str, object] = {
        "product": {
            "provider": "NASA FIRMS (LANCE/EOSDIS)",
            "archive_series": "SV-C2",
            "satellite": sorted(clean_df["satellite"].unique().tolist()),
            "instrument": sorted(clean_df["instrument"].unique().tolist()),
            "nominal_sensor": "Suomi NPP VIIRS I-band 375 m Active Fire Archive",
            "version": sorted(clean_df["version"].unique().tolist()),
            "source_url": "https://firms.modaps.eosdis.nasa.gov/",
            "fields_schema": REQUIRED_FIRMS_COLUMNS,
        },
        "files_verified": file_provenance,
        "accounting": {
            "raw_rows_total": int(total_raw_rows),
            "invalid_coordinate_rows_dropped": invalid_coord_rows,
            "invalid_date_rows_dropped": invalid_date_rows,
            "invalid_time_rows_dropped": invalid_time_rows,
            "invalid_type_rows_dropped": invalid_type_rows,
            "invalid_confidence_rows": invalid_conf_rows,
            "invalid_numeric_rows": invalid_numeric_rows,
            "nonpositive_frp_rows_retained": nonpositive_frp_rows,
            "pre_deduplication_valid_rows": pre_dedup,
            "exact_duplicates_removed": exact_duplicates_removed,
            "out_of_study_window_rows_dropped": out_of_window_rows,
            "clean_rows_retained": int(len(clean_df)),
        },
        "observed_extent": {
            "south_lat": lat_min,
            "north_lat": lat_max,
            "west_lon": lon_min,
            "east_lon": lon_max,
        },
        "temporal_coverage_by_year": observed_days_summary,
        "classification_breakdown": {
            "overall_by_type": type_counts,
            "overall_by_confidence": conf_counts,
            "by_year_type": type_by_year,
            "by_year_confidence": conf_by_year,
        },
        "validation_checks": {
            "all_expected_years_present": all(observed_days_summary[str(y)]["clean_rows"] > 0 for y in years_expected),
            "all_coordinates_in_bounds": invalid_coord_rows == 0,
            "all_dates_and_times_valid": (invalid_date_rows == 0 and invalid_time_rows == 0),
            "row_accounting_exact": (
                total_raw_rows
                - (total_raw_rows - pre_dedup)
                - exact_duplicates_removed
                - out_of_window_rows
                == int(len(clean_df))
            ),
            "duplicates_check_completed": True,
        },
    }

    return clean_df, quality_report


def summarize_repeated_detections(df: pd.DataFrame) -> Dict[str, object]:
    """
    Quantify repeated detections (~0.01 deg grid vicinity, ~1.1 x 0.7 km at 49N)
    to demonstrate why FIRMS counts are pixel-overpass hotspot detections, not individual fires.
    """
    if df.empty:
        return {"overall": {}, "by_year": {}}

    def _calc(sub: pd.DataFrame) -> Dict[str, object]:
        if sub.empty:
            return {
                "detections": 0,
                "unique_0_01deg_cells": 0,
                "unique_0_01deg_cell_days": 0,
                "multi_detection_cells": 0,
                "multi_detection_cell_share": None,
                "multi_day_cells": 0,
                "max_detections_single_cell": 0,
                "mean_detections_per_cell_day": None,
                "day_fraction": None,
            }
        cell_counts = sub.groupby(["cell_lat", "cell_lon"]).size()
        cell_days = sub.groupby(["cell_lat", "cell_lon"])["acq_date_str"].nunique()
        unique_cell_days = int(len(sub[["cell_lat", "cell_lon", "acq_date_str"]].drop_duplicates()))
        n_cells = int(len(cell_counts))
        multi_cells = int((cell_counts > 1).sum())
        multi_day = int((cell_days > 1).sum())
        day_n = int((sub["daynight"] == "D").sum())
        return {
            "detections": int(len(sub)),
            "unique_0_01deg_cells": n_cells,
            "unique_0_01deg_cell_days": unique_cell_days,
            "multi_detection_cells": multi_cells,
            "multi_detection_cell_share": round(multi_cells / float(n_cells), 4) if n_cells > 0 else None,
            "multi_day_cells": multi_day,
            "max_detections_single_cell": int(cell_counts.max()),
            "mean_detections_per_cell_day": round(len(sub) / float(unique_cell_days), 4) if unique_cell_days > 0 else None,
            "day_fraction": round(day_n / float(len(sub)), 4) if len(sub) > 0 else None,
        }

    veg = df[df["type"] == 0]
    return {
        "definition": (
            "Cells rounded to 0.01 deg (~1.1 km N-S x ~0.72 km E-W at 49N). "
            "Multiple rows in one cell/day occur from multi-pixel fire fronts, swath overlap, or twice-daily D/N S-NPP overpasses."
        ),
        "all_types_overall": _calc(df),
        "type0_vegetation_overall": _calc(veg),
        "type0_vegetation_by_year": {
            str(yr): _calc(veg[veg["year"] == yr])
            for yr in sorted(veg["year"].unique())
        },
        "all_types_by_year": {
            str(yr): _calc(df[df["year"] == yr])
            for yr in sorted(df["year"].unique())
        },
    }
