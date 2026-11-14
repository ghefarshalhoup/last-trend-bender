"""Reproducible NASA Giovanni OMNO2d v004 daily-to-monthly NO2 pipeline."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "war_env_tracker_mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"

MONTHLY_COLUMNS = [
    "month",
    "no2_mean_molec_cm2",
    "valid_days",
    "calendar_days",
    "coverage_fraction",
]

TIME_HEADERS = {"time", "timestamp", "timestamp (utc)", "date", "datetime"}
DEFAULT_SPARSE_MIN_VALID_DAYS = 10
DEFAULT_VERY_SPARSE_DAYS = 5
DEFAULT_LOW_COVERAGE_FRACTION = 0.50


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_table_header(lines: List[str]) -> Tuple[int, List[str]]:
    """Scan lines dynamically to locate the CSV data header instead of assuming fixed preamble length."""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cells = [c.strip().strip('"') for c in next(csv.reader([stripped]))]
        if len(cells) < 2:
            continue
        first_norm = cells[0].lower()
        if first_norm.endswith(":"):
            continue
        if first_norm in TIME_HEADERS:
            return idx, cells
    raise ValueError("Could not locate tabular time-series header row in Giovanni CSV.")


def _parse_metadata_preamble(preamble_lines: List[str]) -> Dict[str, object]:
    """Extract provenance metadata and declared fill value from header lines."""
    meta: Dict[str, object] = {
        "raw_header_lines": [],
        "title": None,
        "dataset": None,
        "variable": None,
        "units": "molecules/cm^2",
        "user_start_date": None,
        "user_end_date": None,
        "user_bounding_box": None,
        "data_bounding_box": None,
        "reproducibility_url": None,
        "declared_fill_value": None,
    }

    for raw in preamble_lines:
        cleaned = raw.lstrip("#").strip()
        if not cleaned:
            continue
        meta["raw_header_lines"].append(cleaned)

        # Giovanni metadata rows are commonly CSV-quoted `Key:,Value`
        cells = [c.strip().strip('"') for c in next(csv.reader([cleaned]))]
        key = cells[0].rstrip(":").strip().lower() if cells else ""
        val = ",".join(c for c in cells[1:] if c != "").strip() if len(cells) > 1 else ""
        if not val and ":" in cleaned:
            k_part, v_part = cleaned.split(":", 1)
            key = k_part.strip().lower()
            val = v_part.strip().lstrip(",").strip().strip('"')

        if key == "title":
            meta["title"] = val
        elif key == "user start date":
            meta["user_start_date"] = val[:10] if len(val) >= 10 else val
        elif key == "user end date":
            meta["user_end_date"] = val[:10] if len(val) >= 10 else val
        elif key == "user bounding box":
            nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", val)]
            if len(nums) >= 4:
                meta["user_bounding_box"] = {
                    "west": nums[0],
                    "south": nums[1],
                    "east": nums[2],
                    "north": nums[3],
                }
        elif key == "data bounding box":
            nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", val)]
            if len(nums) >= 4:
                meta["data_bounding_box"] = {
                    "west": nums[0],
                    "south": nums[1],
                    "east": nums[2],
                    "north": nums[3],
                }
        elif key == "url to reproduce results":
            meta["reproducibility_url"] = val
            ds_match = re.search(r"data=([A-Za-z0-9_]+)", val)
            if ds_match:
                meta["dataset_variable_token"] = ds_match.group(1)
        elif "fill value" in key or "fillvalue" in key:
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", val)
            if nums:
                meta["declared_fill_value"] = float(nums[0])
        elif key == "units" and val:
            meta["units"] = val

        if "omno2d" in cleaned.lower() and meta["dataset"] is None:
            ver_match = re.search(r"omno2d[._-]?v?(00\d|\d+\.\d+)", cleaned.lower())
            meta["dataset"] = f"OMNO2d v{ver_match.group(1)}" if ver_match else "OMNO2d"

    return meta


def parse_giovanni_csv(csv_path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Parse a raw Giovanni daily NO2 CSV without altering the source file.

    Returns:
      - daily DataFrame with columns ['date', 'value', 'is_fill', 'raw_value']
      - metadata & raw-row accounting dict
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    raw_text = csv_path.read_text(encoding="utf-8-sig")
    raw_lines = raw_text.splitlines()
    header_idx, header_cols = _find_table_header(raw_lines)
    meta = _parse_metadata_preamble(raw_lines[:header_idx])
    meta["input_file"] = csv_path.name
    meta["input_sha256"] = _sha256_file(csv_path)
    meta["input_bytes"] = csv_path.stat().st_size
    meta["header_line_number_1based"] = header_idx + 1

    table_text = "\n".join(line for line in raw_lines[header_idx:] if line.strip())
    raw_df = pd.read_csv(io.StringIO(table_text), dtype=str)
    raw_df.columns = [c.strip().strip('"') for c in raw_df.columns]

    time_col = next(c for c in raw_df.columns if c.lower() in TIME_HEADERS)
    val_col = next(
        (c for c in raw_df.columns if c != time_col and c.lower() not in {"fillvalue", "fill_value", "_fillvalue"}),
        None,
    )
    if val_col is None:
        raise ValueError(f"Could not find NO2 value column in {raw_df.columns.tolist()}")
    meta["value_column"] = val_col
    if meta["variable"] is None:
        meta["variable"] = val_col

    parsed_dates = pd.to_datetime(raw_df[time_col].str.strip().str.strip('"'), errors="coerce", utc=True)
    if parsed_dates.isna().any():
        bad_count = int(parsed_dates.isna().sum())
        raise ValueError(f"Found {bad_count} unparseable date rows in {csv_path.name}")

    obs_dates = parsed_dates.dt.tz_localize(None).dt.normalize()
    raw_numeric = pd.to_numeric(raw_df[val_col].str.strip().str.strip('"'), errors="coerce")

    declared_fill = meta.get("declared_fill_value")
    if declared_fill is None:
        fill_col = next((c for c in raw_df.columns if c.lower() in {"fillvalue", "fill_value", "_fillvalue"}), None)
        if fill_col:
            vals = pd.to_numeric(raw_df[fill_col], errors="coerce").dropna()
            if not vals.empty:
                declared_fill = float(vals.iloc[0])
                meta["declared_fill_value"] = declared_fill

    if declared_fill is not None:
        tol = max(1e-6, abs(float(declared_fill)) * 1e-5)
        is_fill = raw_numeric.notna() & np.isclose(raw_numeric, float(declared_fill), rtol=0.0, atol=tol)
    else:
        is_fill = pd.Series(False, index=raw_numeric.index)

    other_non_numeric = raw_numeric.isna() & ~is_fill
    clean_values = raw_numeric.where(~is_fill, np.nan).astype(float)

    daily_raw = pd.DataFrame(
        {
            "date": obs_dates,
            "value": clean_values,
            "is_fill": is_fill.astype(bool),
            "is_other_missing": other_non_numeric.astype(bool),
            "raw_value": raw_numeric.astype(float),
        }
    )

    duplicate_dates = int(daily_raw["date"].duplicated().sum())
    if duplicate_dates > 0:
        raise ValueError(f"Found {duplicate_dates} duplicate dates in {csv_path.name}")

    daily_raw = daily_raw.sort_values("date").reset_index(drop=True)
    meta["raw_dated_rows"] = int(len(daily_raw))
    meta["duplicate_dates"] = duplicate_dates
    return daily_raw, meta


def reindex_daily_calendar(
    daily_raw: pd.DataFrame,
    meta: Dict[str, object],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Reindex parsed rows onto the complete daily calendar [start, end],
    distinguishing absent dates from rows with declared fill values.
    Never treats missing or absent observations as zero.
    """
    if daily_raw.empty:
        raise ValueError("Cannot reindex an empty daily DataFrame.")

    start_str = meta.get("user_start_date") or daily_raw["date"].min().strftime("%Y-%m-%d")
    end_str = meta.get("user_end_date") or daily_raw["date"].max().strftime("%Y-%m-%d")

    start_dt = min(pd.Timestamp(start_str), daily_raw["date"].min())
    end_dt = max(pd.Timestamp(end_str), daily_raw["date"].max())
    full_calendar = pd.date_range(start=start_dt, end=end_dt, freq="D")

    indexed = daily_raw.set_index("date").reindex(full_calendar)
    indexed.index.name = "date"
    indexed = indexed.reset_index()

    indexed["is_absent_date"] = indexed["is_fill"].isna()
    indexed["is_fill"] = indexed["is_fill"].eq(True)
    indexed["is_other_missing"] = indexed["is_other_missing"].eq(True)
    indexed["status"] = np.where(
        indexed["is_absent_date"],
        "absent_date",
        np.where(
            indexed["is_fill"],
            "fill_value_missing",
            np.where(indexed["value"].isna(), "other_missing", "valid"),
        ),
    )

    absent_dates = [d.strftime("%Y-%m-%d") for d in indexed.loc[indexed["is_absent_date"], "date"]]
    valid_series = indexed.loc[indexed["status"] == "valid", "value"]

    counts = {
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
        "calendar_days": int(len(indexed)),
        "raw_dated_rows": int((~indexed["is_absent_date"]).sum()),
        "fill_value_rows": int(indexed["is_fill"].sum()),
        "other_missing_rows": int(indexed["is_other_missing"].sum()),
        "absent_dates_count": int(len(absent_dates)),
        "valid_observations": int(len(valid_series)),
        "negative_valid_observations": int((valid_series < 0.0).sum()),
        "min_valid_value": float(valid_series.min()) if not valid_series.empty else None,
        "max_valid_value": float(valid_series.max()) if not valid_series.empty else None,
        "overall_daily_coverage_fraction": round(len(valid_series) / float(len(indexed)), 6),
        "absent_dates": absent_dates,
    }
    return indexed, counts


def aggregate_monthly(
    daily_full: pd.DataFrame,
    sparse_min_valid_days: int = DEFAULT_SPARSE_MIN_VALID_DAYS,
    very_sparse_days: int = DEFAULT_VERY_SPARSE_DAYS,
    low_coverage_fraction: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Aggregate valid daily NO2 measurements into monthly means and coverage metrics.
    Flags low-coverage months (<50% proposed project rule and <10 valid days) without filling gaps.
    """
    df = daily_full.copy()
    df["month_period"] = df["date"].dt.to_period("M")

    grouped = (
        df.groupby("month_period", sort=True)
        .agg(
            no2_mean_molec_cm2=("value", "mean"),
            valid_days=("value", lambda s: int(s.notna().sum())),
            calendar_days=("date", "size"),
        )
        .reset_index()
    )
    grouped["month"] = grouped["month_period"].astype(str)
    grouped["coverage_fraction"] = (grouped["valid_days"] / grouped["calendar_days"]).round(4)

    monthly_df = grouped[MONTHLY_COLUMNS].copy()

    sparse_rows = monthly_df[monthly_df["valid_days"] < sparse_min_valid_days]
    low_cov_rows = monthly_df[(monthly_df["valid_days"] / monthly_df["calendar_days"]) < low_coverage_fraction]
    zero_rows = monthly_df[monthly_df["valid_days"] == 0]
    very_sparse_rows = monthly_df[monthly_df["valid_days"] < very_sparse_days]

    def _serialize_month_rows(frame: pd.DataFrame) -> List[Dict[str, object]]:
        return [
            {
                "month": str(r.month),
                "valid_days": int(r.valid_days),
                "calendar_days": int(r.calendar_days),
                "coverage_fraction": float(r.coverage_fraction),
                "no2_mean_molec_cm2": None if pd.isna(r.no2_mean_molec_cm2) else float(r.no2_mean_molec_cm2),
            }
            for r in frame.itertuples(index=False)
        ]

    monthly_qc = {
        "total_months": int(len(monthly_df)),
        "months_with_any_valid_obs": int((monthly_df["valid_days"] > 0).sum()),
        "months_with_zero_valid_obs": zero_rows["month"].tolist(),
        "proposed_coverage_threshold": float(low_coverage_fraction),
        "proposed_coverage_flag_rule": f"coverage_fraction < {low_coverage_fraction:.2f} (proposed project rule)",
        "low_coverage_months_count": int(len(low_cov_rows)),
        "low_coverage_months": _serialize_month_rows(low_cov_rows),
        "sparse_threshold_valid_days": int(sparse_min_valid_days),
        "very_sparse_threshold_valid_days": int(very_sparse_days),
        "sparse_months_count": int(len(sparse_rows)),
        "very_sparse_months_count": int(len(very_sparse_rows)),
        "sparse_months": _serialize_month_rows(sparse_rows),
    }
    return monthly_df, monthly_qc


def validate_accounting(daily_counts: Dict[str, object], monthly_df: pd.DataFrame) -> Dict[str, bool]:
    """Verify exact accounting invariants across raw, calendar, and monthly aggregations."""
    raw_dated = int(daily_counts["raw_dated_rows"])
    valid_obs = int(daily_counts["valid_observations"])
    fill_rows = int(daily_counts["fill_value_rows"])
    other_missing = int(daily_counts["other_missing_rows"])
    absent_cnt = int(daily_counts["absent_dates_count"])
    cal_days = int(daily_counts["calendar_days"])

    checks = {
        "raw_rows_decompose_exactly": raw_dated == (valid_obs + fill_rows + other_missing),
        "calendar_days_equal_raw_plus_absent": cal_days == (raw_dated + absent_cnt),
        "monthly_valid_days_sum_matches_daily": int(monthly_df["valid_days"].sum()) == valid_obs,
        "monthly_calendar_days_sum_matches_daily": int(monthly_df["calendar_days"].sum()) == cal_days,
        "coverage_fraction_within_bounds": bool(
            ((monthly_df["coverage_fraction"] >= 0.0) & (monthly_df["coverage_fraction"] <= 1.0)).all()
        ),
    }

    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"Data quality accounting invariant check failed: {failed}")
    return checks


def plot_no2_monthly(
    monthly_df: pd.DataFrame,
    meta: Dict[str, object],
    daily_counts: Dict[str, object],
    output_path: Path,
    sparse_min_valid_days: int = DEFAULT_SPARSE_MIN_VALID_DAYS,
    low_coverage_fraction: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> Path:
    """Plot monthly NO2 column values and daily coverage, applying the study-spec 2015–2019 baseline and <50% flag."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = monthly_df.copy()
    df["dt"] = pd.to_datetime(df["month"] + "-01")
    df["year"] = df["dt"].dt.year
    df["cal_month"] = df["dt"].dt.month
    df["no2_e15"] = df["no2_mean_molec_cm2"] / 1e15
    df["cov_exact"] = df["valid_days"] / df["calendar_days"]
    df["cov_pct"] = df["cov_exact"] * 100.0
    df = df.sort_values("dt").reset_index(drop=True)

    # Primary baseline context from docs/study-spec.md: 2015–2019 same-month mean and historical min–max range
    base_15_19 = df[df["year"].between(2015, 2019)].groupby("cal_month")["no2_e15"].agg(["mean", "min", "max"])
    has_base_15_19 = not base_15_19.empty
    if has_base_15_19:
        df["base_min"] = df["cal_month"].map(base_15_19["min"])
        df["base_max"] = df["cal_month"].map(base_15_19["max"])
        df["base_mean_15_19"] = df["cal_month"].map(base_15_19["mean"])

    adequate = df[(df["cov_exact"] >= low_coverage_fraction) & df["no2_e15"].notna()]
    flagged = df[(df["valid_days"] > 0) & (df["cov_exact"] < low_coverage_fraction) & df["no2_e15"].notna()]
    zero_cov = df[df["valid_days"] == 0]

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12.6, 8.0),
        sharex=True,
        gridspec_kw={"height_ratios": [1.85, 0.90]},
    )
    fig.patch.set_facecolor("white")

    if has_base_15_19:
        ax1.fill_between(
            df["dt"],
            df["base_min"],
            df["base_max"],
            color="#E5E8E8",
            alpha=0.72,
            label="2015–2019 historical min–max variability (not CI)",
        )
        ax1.plot(
            df["dt"],
            df["base_mean_15_19"],
            color="#5D6D7E",
            linestyle="--",
            linewidth=1.25,
            label="2015–2019 primary same-month mean",
        )

    for idx_yr, yr in enumerate(sorted(df["year"].unique())):
        ma_s = pd.Timestamp(f"{yr}-03-01")
        ma_e = pd.Timestamp(f"{yr}-08-31")
        if ma_e >= df["dt"].min() and ma_s <= df["dt"].max():
            ax1.axvspan(
                max(ma_s, df["dt"].min()),
                min(ma_e, df["dt"].max()),
                color="#FDEDEC" if yr == 2022 else "#FEF9E7",
                alpha=0.60,
                zorder=0,
                label="March–August comparison window" if idx_yr == 0 else None,
            )

    # Connect observed months (zero-observation gaps stay broken)
    ax1.plot(df["dt"], df["no2_e15"], color="#C0392B", linewidth=1.6, zorder=3)
    ax1.scatter(
        adequate["dt"],
        adequate["no2_e15"],
        color="#C0392B",
        s=26,
        zorder=4,
        label=f"Coverage ≥{int(low_coverage_fraction * 100)}%",
    )
    if not flagged.empty:
        ax1.scatter(
            flagged["dt"],
            flagged["no2_e15"],
            facecolor="white",
            edgecolor="#D35400",
            linewidth=1.8,
            s=46,
            marker="D",
            zorder=5,
            label=f"Flagged <{int(low_coverage_fraction * 100)}% coverage (project rule)",
        )
    if not zero_cov.empty:
        ax1.scatter(
            zero_cov["dt"],
            [0.08] * len(zero_cov),
            color="#7B241C",
            marker="x",
            s=55,
            zorder=5,
            label="No valid observations (gap)",
        )

    war_dt = pd.Timestamp("2022-02-24")
    ymax = max(1.0, float(df["no2_e15"].max(skipna=True) or 5.0))
    ax1.set_ylim(0, ymax * 1.15)
    if df["dt"].min() <= war_dt <= df["dt"].max():
        ax1.axvline(war_dt, color="#7B241C", linestyle="-.", linewidth=1.5)
        ax1.text(
            war_dt - pd.Timedelta(days=15),
            ymax * 0.96,
            "Feb 24, 2022\nInvasion onset",
            color="#7B241C",
            fontsize=8.6,
            fontweight="bold",
            ha="right",
            va="top",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#7B241C", alpha=0.92),
        )

    bbox = meta.get("user_bounding_box") or {}
    bbox_txt = (
        f"Kyiv box ({bbox['west']:.3f}°E–{bbox['east']:.3f}°E, {bbox['south']:.2f}°N–{bbox['north']:.2f}°N)"
        if bbox
        else "Kyiv study box"
    )
    ax1.set_title(
        f"Monthly Tropospheric NO₂ Column — {bbox_txt} (OMNO2d v004, {daily_counts['start_date']} to {daily_counts['end_date']})",
        fontsize=11.0,
        fontweight="bold",
        pad=38,
    )
    ax1.set_ylabel("Mean NO₂ (10¹⁵ molecules/cm²)", fontsize=10)
    ax1.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=3,
        frameon=True,
        facecolor="white",
        fontsize=8.0,
    )
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", linestyle=":", alpha=0.5, color="#B2BABB")

    # Bottom panel: monthly sampling coverage (% of calendar days) with 50% proposed project flag
    bar_colors = [
        "#E67E22" if cov < low_coverage_fraction else "#5499C7"
        for cov in df["cov_exact"]
    ]
    ax2.bar(df["dt"], df["cov_pct"], width=22, color=bar_colors, alpha=0.9)
    ax2.axhline(
        low_coverage_fraction * 100.0,
        color="#D35400",
        linestyle=":",
        linewidth=1.4,
        label=f"Proposed project flag (<{int(low_coverage_fraction * 100)}% monthly coverage)",
    )
    if df["dt"].min() <= war_dt <= df["dt"].max():
        ax2.axvline(war_dt, color="#7B241C", linestyle="-.", linewidth=1.3)

    # Annotate key very-sparse months and April 2022 with exact valid/calendar day counts
    key_months = {"2016-03", "2020-11", "2022-04"}
    for row in flagged.itertuples(index=False):
        if row.month in key_months:
            x_pos = row.dt + pd.Timedelta(days=12) if row.month == "2022-04" else row.dt
            y_pos = 56.0 if row.month == "2022-04" else max(row.cov_pct + 7.0, 26.0)
            ax2.annotate(
                f"{row.month}\n({int(row.valid_days)}/{int(row.calendar_days)}d)",
                xy=(row.dt, row.cov_pct),
                xytext=(x_pos, y_pos),
                ha="center",
                va="bottom",
                fontsize=7.3,
                color="#A04000",
                fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.18",
                    facecolor="white",
                    edgecolor="#E67E22",
                    linewidth=0.7,
                    alpha=0.94,
                ),
                arrowprops=dict(arrowstyle="-", color="#E67E22", linewidth=0.8),
            )

    ax2.set_ylabel("Coverage (% days/mo)", fontsize=9.5)
    ax2.set_ylim(0, 108)
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.legend(loc="upper right", frameon=True, facecolor="white", fontsize=8.0)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", linestyle=":", alpha=0.5, color="#B2BABB")

    low_cov_cnt = int((df["cov_exact"] < low_coverage_fraction).sum())
    fig.text(
        0.015,
        0.01,
        (
            f"Source: NASA Giovanni OMNO2d v004 (30% Cloud Screened) | Baseline: 2015–2019 same-month mean & min–max range (not a CI) | "
            f"{daily_counts['valid_observations']:,} valid obs / {daily_counts['calendar_days']:,} days ({daily_counts['fill_value_rows']:,} fill, {daily_counts['absent_dates_count']:,} absent)\n"
            f"Note: {low_cov_cnt}/{len(df)} months flagged <50% coverage (project rule); tropospheric column ≠ street-level exposure; "
            "observed changes alone do not establish war causation."
        ),
        fontsize=7.4,
        color="#566573",
        linespacing=1.35,
    )
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _discover_default_input(raw_dir: Path = DEFAULT_RAW_DIR) -> Path:
    preferred = raw_dir / "NASA_Giovanni_NO2_2015-03-01_to_2022-08-31.csv"
    if preferred.exists():
        return preferred
    csvs = sorted(p for p in raw_dir.glob("*.csv") if not p.name.startswith("."))
    if len(csvs) == 1:
        return csvs[0]
    if not csvs:
        raise FileNotFoundError(
            f"No Giovanni CSV found in {raw_dir}. Pass --input <path-to-csv> or place the raw CSV in {raw_dir}."
        )
    raise ValueError(f"Multiple CSVs found in {raw_dir}; specify --input explicitly.")


def run_pipeline(
    input_csv: Path,
    output_csv: Path = DEFAULT_REPORTS_DIR / "no2_monthly.csv",
    output_chart: Path = DEFAULT_REPORTS_DIR / "no2_monthly.png",
    output_quality: Path = DEFAULT_REPORTS_DIR / "data_quality.json",
    sparse_min_valid_days: int = DEFAULT_SPARSE_MIN_VALID_DAYS,
    low_coverage_fraction: float = DEFAULT_LOW_COVERAGE_FRACTION,
) -> Dict[str, object]:
    """Execute full daily cleaning, calendar reindexing, monthly aggregation, validation, and charting."""
    daily_raw, meta = parse_giovanni_csv(input_csv)
    daily_full, daily_counts = reindex_daily_calendar(daily_raw, meta)
    monthly_df, monthly_qc = aggregate_monthly(
        daily_full,
        sparse_min_valid_days=sparse_min_valid_days,
        low_coverage_fraction=low_coverage_fraction,
    )
    invariant_checks = validate_accounting(daily_counts, monthly_df)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    monthly_df.to_csv(output_csv, index=False)

    plot_no2_monthly(
        monthly_df=monthly_df,
        meta=meta,
        daily_counts=daily_counts,
        output_path=output_chart,
        sparse_min_valid_days=sparse_min_valid_days,
        low_coverage_fraction=low_coverage_fraction,
    )

    quality_report = {
        "provenance": {
            "input_file": meta["input_file"],
            "input_sha256": meta["input_sha256"],
            "input_bytes": meta["input_bytes"],
            "header_line_number_1based": meta["header_line_number_1based"],
            "title": meta["title"],
            "dataset": meta["dataset"],
            "variable": meta["variable"],
            "units": meta["units"],
            "user_start_date": meta["user_start_date"],
            "user_end_date": meta["user_end_date"],
            "user_bounding_box": meta["user_bounding_box"],
            "data_bounding_box": meta["data_bounding_box"],
            "reproducibility_url": meta["reproducibility_url"],
            "declared_fill_value": meta["declared_fill_value"],
        },
        "daily_counts": daily_counts,
        "monthly_summary": monthly_qc,
        "validation_checks": invariant_checks,
        "processing_rules": {
            "missing_values_never_zero_filled": True,
            "negative_valid_values_preserved": True,
            "proposed_coverage_flag_rule": f"coverage_fraction < {low_coverage_fraction:.2f} (proposed project rule)",
            "sparse_month_rule": f"valid_days < {sparse_min_valid_days} (legacy severe-sparsity reference)",
            "causal_claim_caveat": (
                "Tropospheric column NO2 reflects regional atmospheric column density, not street-level exposure; "
                "temporal drops alone cannot establish war causation without matched controls and weather adjustments."
            ),
        },
    }

    output_quality.parent.mkdir(parents=True, exist_ok=True)
    output_quality.write_text(json.dumps(quality_report, indent=2, allow_nan=False, ensure_ascii=False), encoding="utf-8")
    return quality_report


def main(argv: Optional[List[str]] = None) -> int:
    from src.air_analysis import main as air_main

    return air_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
