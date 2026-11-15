"""Build reviewed, frontend-ready data exports for the four-element illustrated atlas.

Generates deterministic, read-only JSON artifacts under ``reports/`` from the
reviewed pipeline outputs and frozen audit inputs without altering Milestone 1
Air artifacts (``reports/air_no2_results.json``):

- ``reports/atlas_catalog.json``: Full 25-metric catalog across Air, Fire,
  Earth (``land``), and Water, including units, dates, supported baselines
  (withholding Fire ``2015-2019``), spatial support, method IDs, uncertainty/status,
  sources, and limitations.
- ``reports/atlas_fire_ukraine.json``: Fire study package with agreed primary
  normalization (``detections / 1,000 km^2 / CMR observed day``), strictly separated
  matched-date (``169d/yr`` ``UKR-ADM0``) sensitivity and legacy unnormalized
  rates, confidence/type breakdowns, CMR orbit-outage quality flags, seasonal
  ``0.25 deg`` grid cells, regional context boxes, and Fire-vs-dryness scatter data.
- ``reports/atlas_fire_cells.json``: Complete ``0.25 deg x 0.25 deg`` monthly
  FIRMS spatial grid cells (``2019-03`` to ``2022-08``) across all confidence and
  source-type filter slices plus full cell registry and CMR month coverage.
- ``reports/atlas_water_ukraine.json``: Water regional context package
  (``prectotcorr`` + ``vpd_kpa`` first, plus secondary hydrologic indicators)
  with GeoJSON regional study boxes, seasonal/matched-month baselines, full
  2015-2022 monthly series, and coarse-resolution caveats.
- ``reports/atlas_earth_ukraine.json``: Earth (``land``) regional context package
  (``gwettop`` primary + depth/thermal/albedo indicators) with identical regional
  box structure and uncertainty/drought caveats.
- ``reports/atlas_air_weather_ukraine.json``: Regional meteorological context for
  Air secondary variables (``ws10m``, ``cloud_amt``, ``ps``, ``clrsky_sfc_sw_dwn``,
  ``cloud_radiative_attenuation_wm2``) and Kyiv daily wind/cloud sensitivity,
  kept additive so ``/api/air/kyiv`` stays unchanged.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.audit_exports import FROZEN_DIR, load_ukraine_adm0_path
from src.fire_pipeline import (
    STUDY_MONTHS,
    STUDY_YEARS,
    discover_fire_inputs,
    load_and_validate_firms_archives,
)
from src.four_elements_analysis import (
    CONFLICT_START_DATE,
    DEFAULT_REPORTS_DIR,
    INTERVAL_SCALE_UNITS,
    MARCH_AUGUST_MONTHS,
    METRIC_SPEC_BY_ID,
    PROPOSED_REGIONS,
)
from src.kyiv_sensitivities import build_krakow_prague_comparison, build_kyiv_no2_sensitivities
from src.stats_rigor import clean_float, safe_pct_change, write_strict_json
from src.weather_power_pipeline import STUDY_BOXES, PowerBoxSpec, bbox_area_km2

SCHEMA_VERSION = "1.0.0"

MONTH_NAMES: Dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

BOX_BY_ID: Dict[str, PowerBoxSpec] = {box.region_id: box for box in STUDY_BOXES}
UKRAINE_BOX_IDS: Tuple[str, ...] = (
    "donbas_kharkiv_east",
    "south_steppe_belt",
    "kyiv_north_belt",
    "kyiv_no2_box",
    "central_interior_cand",
    "west_ukraine_cand",
)
EXTERNAL_WEATHER_BOX_IDS: Tuple[str, ...] = ("poland_krakow", "czechia_prague")
FIRE_OUTAGE_MONTHS: frozenset[str] = frozenset({"2022-03", "2022-07", "2022-08"})

PRIMARY_INDICATORS_BY_ELEMENT: Dict[str, str] = {
    "air": "no2_mean_molec_cm2",
    "fire": "fire_type0_per_1k_km2_day",
    "water": "prectotcorr",
    "land": "gwettop",
}

FIRE_PRIMARY_METHOD_ID = "firms_type0_per_1k_km2_cmr_obsday_box_area_v1"
FIRE_MATCHED_SENSITIVITY_METHOD_ID = "firms_matched_169d_ukr_adm0_land_sensitivity_v1"
FIRE_LEGACY_METHOD_ID = "firms_legacy_detections_per_observed_day_v1"


@dataclass(frozen=True)
class CatalogVariableSpec:
    metric_id: str
    element_id: str  # matches frontend ElementId: air | fire | land | water
    element_label: str
    label: str
    short_label: str
    units: str
    is_interval_scale: bool
    is_primary_indicator: bool
    display_order: int
    date_start: str
    date_end: str
    seasonal_window: str
    n_years_available: int
    method_id: str
    resolution: str
    sampling_method: str
    presentation_type: str
    supports_fine_heatmap: bool
    supports_spatial_cells: bool
    sources: Tuple[str, ...]
    limitations: Tuple[str, ...]


# Canonical 25 curated metrics (Air=6, Fire=7, Water=6, Earth/land=6).
CATALOG_VARIABLES: Tuple[CatalogVariableSpec, ...] = (
    # ---- Air (6) ----
    CatalogVariableSpec(
        metric_id="no2_mean_molec_cm2",
        element_id="air",
        element_label="Air",
        label="Tropospheric NO2 Column (OMNO2d v004)",
        short_label="NO2",
        units="molecules/cm^2",
        is_interval_scale=False,
        is_primary_indicator=True,
        display_order=1,
        date_start="2015-03",
        date_end="2022-08",
        seasonal_window="March-August",
        n_years_available=8,
        method_id="omi_omno2d_v004_box_mean_v1",
        resolution="0.25 deg OMI grid averaged over Kyiv 0.5 deg box",
        sampling_method="Area mean across snapped 0.25 deg pixel centers inside Kyiv box (30.273-30.773E, 50.2-50.7N)",
        presentation_type="kyiv_study_box",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA Aura OMI OMNO2d v004 via Giovanni",),
        limitations=(
            "Only Kyiv study box has NO2 retrievals in this archive; not a city street-level map.",
            "April 2022 has low valid retrieval coverage (8/30 days; 26.7%) due to cloud cover.",
            "Observed 2022 drop reflects combined weather ventilation and emission shifts; single-season record does not establish war causation.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="ws10m",
        element_id="air",
        element_label="Air",
        label="10m Wind Speed",
        short_label="Wind speed",
        units="m/s",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=2,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Coarse 0.5 deg x 0.625 deg reanalysis regional context; cannot resolve urban canyon wind dispersion.",
            "Used as an atmospheric-ventilation confounder check alongside OMI NO2, not as war-damage evidence.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="cloud_amt",
        element_id="air",
        element_label="Air",
        label="Total Cloud Amount",
        short_label="Cloud amount",
        units="%",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=3,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_ceres_3x3_coslat_v1",
        resolution="1.0 deg CERES sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER CERES SYN1deg",),
        limitations=(
            "Coarse 1.0 deg regional box average explaining OMI cloud screening gaps (e.g., April 2022).",
            "Represents synoptic cloudiness context rather than direct anthropogenic plumes.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="ps",
        element_id="air",
        element_label="Air",
        label="Surface Barometric Pressure",
        short_label="Pressure",
        units="kPa",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=4,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Regional synoptic pressure context only; small relative % fluctuations reflect atmospheric pressure baselines (~99 kPa).",
        ),
    ),
    CatalogVariableSpec(
        metric_id="clrsky_sfc_sw_dwn",
        element_id="air",
        element_label="Air",
        label="Clear-Sky Downward Shortwave Radiation",
        short_label="Clear-sky sunlight",
        units="MJ/m^2/day",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=5,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_ceres_3x3_coslat_v1",
        resolution="1.0 deg CERES sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER CERES SYN1deg",),
        limitations=(
            "Clear-sky radiative baseline from 1.0 deg CERES model estimates; does not directly isolate localized smoke aerosols.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="cloud_radiative_attenuation_wm2",
        element_id="air",
        element_label="Air",
        label="Cloud-Related Sunlight Reduction (SWclr - SWall)",
        short_label="Cloud sunlight reduction",
        units="W/m^2",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=6,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_ceres_attenuation_diff_v1",
        resolution="1.0 deg CERES difference derived over 3x3 cos(lat) lattice",
        sampling_method="(CLRSKY_SFC_SW_DWN - ALLSKY_SFC_SW_DWN) * 1e6 / 86400",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER CERES SYN1deg (derived)",),
        limitations=(
            "Derived signed radiative difference (W/m^2); relative % change is strictly withheld as non-meaningful across near-zero values.",
            "Coarse 1.0 deg context only; cannot isolate local dust/smoke plumes from clouds.",
        ),
    ),
    # ---- Fire (7) ----
    CatalogVariableSpec(
        metric_id="fire_type0_per_1k_km2_day",
        element_id="fire",
        element_label="Fire",
        label="VIIRS Presumed Vegetation Fire Density (type 0)",
        short_label="Vegetation fire density",
        units="det / 1000 km^2 / day",
        is_interval_scale=False,
        is_primary_indicator=True,
        display_order=1,
        date_start="2019-03",
        date_end="2022-08",
        seasonal_window="March-August only",
        n_years_available=4,
        method_id=FIRE_PRIMARY_METHOD_ID,
        resolution="375 m VIIRS S-NPP pixels summarized over study boxes and 0.25 deg grid cells",
        sampling_method="Type-0 detection count divided by (box_area_km2 / 1000) and CMR VNP14IMG observed satellite days",
        presentation_type="spatial_cells_and_regional_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=True,
        sources=("NASA FIRMS VIIRS S-NPP Archive Export (SV-C2)", "NASA CMR VNP14IMG coverage"),
        limitations=(
            "2015-2019 baseline is strictly unsupported/disabled because this archive begins in 2019-03 (only 2019-2021 pre-war baseline is valid).",
            "Hotspot pixel counts are not burned area in km^2: repeated overpasses and multi-pixel fire fronts cluster detections (~1.42 det/cell-day).",
            "2022 contains a 16-day satellite observation gap (notably 2022-07-27 through 2022-08-10 orbit outage, plus 2022-03-05).",
            "Matched-date (169d/yr) UKR-ADM0 polygon clipping shifts absolute ratios (~63.9% vs 104.3% in Donbas) and is kept strictly separate.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="fire_type2_per_1k_km2_day",
        element_id="fire",
        element_label="Fire",
        label="VIIRS Other Static Land Source Density (type 2)",
        short_label="Static heat sources",
        units="det / 1000 km^2 / day",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=2,
        date_start="2019-03",
        date_end="2022-08",
        seasonal_window="March-August only",
        n_years_available=4,
        method_id="firms_type2_per_1k_km2_cmr_obsday_box_area_v1",
        resolution="375 m VIIRS S-NPP pixels summarized over study boxes and 0.25 deg grid cells",
        sampling_method="Type-2 static land source count divided by (box_area_km2 / 1000) and CMR VNP14IMG observed satellite days",
        presentation_type="spatial_cells_and_regional_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=True,
        sources=("NASA FIRMS VIIRS S-NPP Archive Export (SV-C2)", "NASA CMR VNP14IMG coverage"),
        limitations=(
            "2015-2019 baseline is strictly unsupported/disabled (archive begins 2019-03).",
            "Tracks stationary industrial/metallurgical/gas-flare hotspots; sharp 2022 drops in frontline corridors (e.g. -83% in Donbas-Kharkiv) reflect facility shutdowns/destruction rather than fire absence.",
            "Boxes with zero baseline type-2 detections (e.g. Kyiv 0.5 deg box) withhold % change.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="t2m",
        element_id="fire",
        element_label="Fire",
        label="2m Air Temperature",
        short_label="Air temperature",
        units="°C",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=3,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Interval-scale °C unit: absolute difference is reported while relative % change is strictly withheld (null).",
            "Regional fire-weather context only (0.5 deg box average), not local flame temperature.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="t2m_max",
        element_id="fire",
        element_label="Fire",
        label="Monthly Peak 2m Air Temperature (T2M_MAX)",
        short_label="Peak temperature",
        units="°C",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=4,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of monthly extreme maximum 2m air temperature (T2M_MAX)",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Interval-scale °C unit: relative % change is strictly withheld (null).",
            "Coarse 0.5 deg box average cannot capture fine-scale heat domes.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="dtr_c",
        element_id="fire",
        element_label="Fire",
        label="Diurnal Temperature Range (T2M_RANGE)",
        short_label="Temperature range",
        units="°C",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=5,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of daily Tmax - Tmin magnitude",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Regional synoptic dryness/clear-sky context indicator; coarse 0.5 deg resolution.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="allsky_sfc_sw_dwn",
        element_id="fire",
        element_label="Fire",
        label="All-Sky Downward Shortwave Sunlight",
        short_label="All-sky sunlight",
        units="MJ/m^2/day",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=6,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_ceres_3x3_coslat_v1",
        resolution="1.0 deg CERES sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER CERES SYN1deg",),
        limitations=(
            "Coarse 1.0 deg surface insolation context used in radiation/PET fire-weather checks.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="pet_fao56_mm_day",
        element_id="fire",
        element_label="Fire",
        label="FAO-56 Penman-Monteith Potential Evapotranspiration (PET)",
        short_label="Evaporation demand (PET)",
        units="mm/day",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=7,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_fao56_pm_v1",
        resolution="0.5 deg MERRA-2 / 1.0 deg CERES derived over 3x3 cos(lat) lattice",
        sampling_method="Monthly FAO-56 Penman-Monteith reference ET using regional box elevation; strict daily PM sensitivity checked (RMSE 0.119 mm/day)",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER MERRA-2/CERES (derived FAO-56 PM)",),
        limitations=(
            "Measures atmospheric evaporative demand over coarse regional boxes, not actual irrigation or localized drought stress.",
        ),
    ),
    # ---- Water (6) ----
    CatalogVariableSpec(
        metric_id="prectotcorr",
        element_id="water",
        element_label="Water",
        label="Bias-Corrected Total Precipitation (PRECTOTCORR)",
        short_label="Rainfall",
        units="mm/day",
        is_interval_scale=False,
        is_primary_indicator=True,
        display_order=1,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Regional 0.5 deg environmental context ONLY: averages smooth localized storm deficits and do NOT rule out sub-regional or short-term drought.",
            "Does not measure reservoir levels, drinking-water infrastructure damage, or contamination.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="vpd_kpa",
        element_id="water",
        element_label="Water",
        label="Vapor Pressure Deficit (VPD)",
        short_label="VPD (drying demand)",
        units="kPa",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=2,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_vpd_tetens_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 derived over 3x3 cos(lat) lattice",
        sampling_method="e_s(T2M) * (1 - RH2M / 100) using Tetens saturation vapor pressure formula",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2 (derived)",),
        limitations=(
            "Regional atmospheric drying-demand context only; coarse 0.5 deg boxes cannot produce local drought heatmaps or rule out local soil/water stress.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="qv2m",
        element_id="water",
        element_label="Water",
        label="2m Specific Humidity",
        short_label="Specific humidity",
        units="g/kg",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=3,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Coarse 0.5 deg regional moisture context only; not direct hydrological damage evidence.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="rh2m",
        element_id="water",
        element_label="Water",
        label="2m Relative Humidity",
        short_label="Relative humidity",
        units="%",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=4,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Coarse 0.5 deg regional atmospheric humidity context only; cannot substitute for catchment drought or water quality data.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="evptrns_mm_day",
        element_id="water",
        element_label="Water",
        label="Vegetation Transpiration Flux (EVPTRNS)",
        short_label="Transpiration",
        units="mm/day",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=5,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean converted from MJ/m^2/day transpiration energy flux via Bolton lambda(T) = max(2.2, 2.501 - 0.002361 * T2M) MJ/kg",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Reanalysis land-surface model estimate at 0.5 deg resolution; does not directly observe field-scale crop stress or destroyed irrigation.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="precip_minus_pet_mm_day",
        element_id="water",
        element_label="Water",
        label="Climatic Water Balance (Rainfall minus PET)",
        short_label="Water balance (P - PET)",
        units="mm/day",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=6,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_water_balance_diff_v1",
        resolution="0.5 deg MERRA-2 / 1.0 deg CERES derived over 3x3 cos(lat) lattice",
        sampling_method="PRECTOTCORR - PET_FAO56 in mm/day",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER MERRA-2/CERES (derived)",),
        limitations=(
            "Signed interval difference crossing zero: relative % change is strictly withheld (null); inspect abs_diff (mm/day) instead.",
            "Coarse regional context only; does not rule out localized seasonal drought or measure water-system damage.",
        ),
    ),
    # ---- Earth / land (6) ----
    CatalogVariableSpec(
        metric_id="gwettop",
        element_id="land",
        element_label="Earth",
        label="Surface Soil Wetness (0-5 cm, GWETTOP)",
        short_label="Surface soil wetness",
        units="fraction",
        is_interval_scale=False,
        is_primary_indicator=True,
        display_order=1,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Regional 0.5 deg environmental context ONLY: broad box means do not rule out localized drought and do NOT directly observe cratering, landmines, or soil contamination.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="gwetroot",
        element_id="land",
        element_label="Earth",
        label="Root-Zone Soil Wetness (0-100 cm, GWETROOT)",
        short_label="Root-zone wetness",
        units="fraction",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=2,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "0.5 deg reanalysis soil moisture context; cannot resolve farm-level soil disruption or war land degradation.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="gwetprof",
        element_id="land",
        element_label="Earth",
        label="Full-Profile Soil Wetness (GWETPROF)",
        short_label="Full-profile wetness",
        units="fraction",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=3,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "0.5 deg deep soil moisture context; seasonal box means do not establish or rule out localized agricultural stress.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="ts",
        element_id="land",
        element_label="Earth",
        label="Earth Skin Surface Temperature (TS)",
        short_label="Surface temperature",
        units="°C",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=4,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_3x3_coslat_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2",),
        limitations=(
            "Interval-scale °C unit: relative % change is strictly withheld (null); use abs_diff (°C).",
            "Coarse 0.5 deg thermal context only; cannot produce sub-kilometer land-surface temperature heatmaps.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="ts_minus_t2m_c",
        element_id="land",
        element_label="Earth",
        label="Surface-minus-Air Temperature Difference (Ts - T2m)",
        short_label="Surface-air diff",
        units="°C",
        is_interval_scale=True,
        is_primary_indicator=False,
        display_order=5,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_merra2_thermal_decoupling_v1",
        resolution="0.5 deg x 0.625 deg MERRA-2 derived over 3x3 cos(lat) lattice",
        sampling_method="TS - T2M in °C",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER v9.x MERRA-2 (derived)",),
        limitations=(
            "Signed difference near zero: relative % change is strictly withheld (null).",
            "Coarse regional surface-energy context only.",
        ),
    ),
    CatalogVariableSpec(
        metric_id="allsky_srf_alb",
        element_id="land",
        element_label="Earth",
        label="All-Sky Surface Albedo",
        short_label="Albedo",
        units="dimensionless",
        is_interval_scale=False,
        is_primary_indicator=False,
        display_order=6,
        date_start="2015-01",
        date_end="2022-12",
        seasonal_window="March-August (monthly series full-year)",
        n_years_available=8,
        method_id="nasa_power_ceres_3x3_coslat_v1",
        resolution="1.0 deg CERES sampled over 3x3 cos(lat) lattice",
        sampling_method="Cos(lat)-weighted mean of 3x3 box-spanning NASA POWER grid points",
        presentation_type="regional_study_boxes",
        supports_fine_heatmap=False,
        supports_spatial_cells=False,
        sources=("NASA POWER CERES SYN1deg",),
        limitations=(
            "Coarse 1.0 deg surface reflectance indicator; snow cover, cloudiness, and regional crop phenology dominate box averages.",
        ),
    ),
)

CATALOG_BY_ID: Dict[str, CatalogVariableSpec] = {v.metric_id: v for v in CATALOG_VARIABLES}

# Plain-language one-sentence definitions for all 25 curated metrics.
PLAIN_DEFINITIONS_BY_METRIC_ID: Dict[str, str] = {
    "no2_mean_molec_cm2": (
        "Satellite-measured nitrogen dioxide (NO2) gas density in the tropospheric "
        "(lower-atmosphere) air column above the study box, reflecting fuel combustion from "
        "traffic, power generation, and industry."
    ),
    "ws10m": (
        "Average wind speed measured 10 meters above ground, controlling how quickly air pollution "
        "is blown away and dispersed."
    ),
    "cloud_amt": (
        "Percentage of the sky covered by clouds, which cools daytime surfaces and causes missing "
        "days in satellite NO2 observations."
    ),
    "ps": (
        "Air pressure at the ground surface, tracking passing high-pressure fair weather versus "
        "low-pressure storm systems (levels also vary with ground elevation)."
    ),
    "clrsky_sfc_sw_dwn": (
        "Incoming sunlight energy on a cloudless day, set mainly by season, latitude, and "
        "atmospheric haze as the clear-sky solar ceiling."
    ),
    "cloud_radiative_attenuation_wm2": (
        "Average sunlight power blocked or reflected by clouds before reaching the ground (clear-sky "
        "minus all-sky solar radiation, converted to W/m^2)."
    ),
    "fire_type0_per_1k_km2_day": (
        "Number of satellite-detected vegetation fire hotspots (nominal/high confidence) per 1,000 "
        "square kilometers per satellite-observed day; counts pixel hotspots across overpasses, "
        "not distinct fires or burned area."
    ),
    "fire_type2_per_1k_km2_day": (
        "Number of persistent stationary heat detections (steelworks, industrial plants, and gas "
        "flares) per 1,000 square kilometers per satellite-observed day."
    ),
    "t2m": (
        "Monthly average air temperature 2 meters above the ground, describing regional baseline "
        "warmth across seasons."
    ),
    "t2m_max": (
        "Monthly extreme maximum air temperature at 2 meters height (single hottest reading of the "
        "month, not the mean of daily highs), capturing heat extremes that dry surface fuels."
    ),
    "dtr_c": (
        "Monthly average of the daily spread between daytime high and nighttime low temperatures, "
        "which widens during sunny dry spells and shrinks under clouds."
    ),
    "allsky_sfc_sw_dwn": (
        "Actual average solar energy reaching the ground after cloud shading, driving surface "
        "heating and water evaporation."
    ),
    "pet_fao56_mm_day": (
        "Standardized FAO-56 Penman-Monteith evaporation demand from a hypothetical well-watered "
        "reference grass surface given local sun, heat, humidity, and wind."
    ),
    "prectotcorr": (
        "Bias-corrected total precipitation (rain and melted snowfall) reaching the land surface as "
        "millimeters of liquid water per day across the study box."
    ),
    "vpd_kpa": (
        "Atmospheric drying pull (vapor pressure deficit): gap between saturation vapor pressure at "
        "air temperature and actual vapor pressure, showing how strongly dry air draws moisture."
    ),
    "qv2m": (
        "Actual mass of water vapor mixed into every kilogram of moist near-surface air, measuring "
        "true atmospheric moisture content."
    ),
    "rh2m": (
        "Percentage of water vapor the air holds compared with the maximum it could hold at its "
        "current temperature."
    ),
    "evptrns_mm_day": (
        "Model-estimated daily water transpired by vegetation canopies through leaves into the "
        "atmosphere (MERRA-2 transpiration energy flux converted via temperature-dependent latent "
        "heat)."
    ),
    "precip_minus_pet_mm_day": (
        "Climatic water balance (total precipitation minus FAO-56 reference evaporation demand): "
        "positive indicates moisture surplus and negative indicates net drying pressure."
    ),
    "gwettop": (
        "MERRA-2 modeled moisture saturation in the top 5 cm of soil (from 0 completely water-free "
        "to 1 fully saturated)."
    ),
    "gwetroot": (
        "MERRA-2 modeled moisture saturation across the 0-1 m plant root zone (from 0 water-free "
        "to 1 fully saturated), tracking crop water reserves."
    ),
    "gwetprof": (
        "MERRA-2 modeled water saturation across the full vertical soil column to bedrock, changing "
        "more slowly across seasons than surface soil."
    ),
    "ts": (
        "Modeled radiometric skin temperature of the ground surface itself, rising relative to air "
        "temperature when soils dry out."
    ),
    "ts_minus_t2m_c": (
        "24-hour monthly mean temperature difference between the modeled ground skin and air 2 "
        "meters above it (-1.4 to +2.0 °C across study boxes), reflecting surface heating versus "
        "evaporative cooling."
    ),
    "allsky_srf_alb": (
        "Fraction of incoming sunlight reflected off the land surface back into space, varying "
        "with winter snow, bare soil, and crop greenness."
    ),
}


def _finite(value: Optional[float], digits: Optional[int] = 4) -> Optional[float]:
    return clean_float(value, digits)


def _box_geojson_feature(box: PowerBoxSpec, audit_row: Mapping[str, Any], include_in_ukr_map: bool) -> Dict[str, Any]:
    area = _finite(bbox_area_km2(box.west, box.south, box.east, box.north), 2)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [box.west, box.south],
                [box.east, box.south],
                [box.east, box.north],
                [box.west, box.north],
                [box.west, box.south],
            ]],
        },
        "properties": {
            "region_id": box.region_id,
            "name": box.name,
            "role": box.role,
            "area_km2": area,
            "elevation_m": _finite(box.elevation_m, 1),
            "center": {
                "lat": _finite((box.south + box.north) / 2.0, 4),
                "lon": _finite((box.west + box.east) / 2.0, 4),
            },
            "bounds": [[box.south, box.west], [box.north, box.east]],
            "is_ukraine_study_area": include_in_ukr_map,
            "pct_box_inside_ukr_adm0": audit_row.get("pct_box_inside_ukr_adm0"),
            "estimated_ukr_land_km2": audit_row.get("estimated_ukr_land_km2"),
            "lattice_points_inside_ukr_adm0": audit_row.get("lattice_points_inside_ukr_adm0"),
            "lattice_points_total": audit_row.get("lattice_points_total"),
            "description": box.description,
        },
    }


def _compute_change(
    target_val: Optional[float],
    base_val: Optional[float],
    is_interval_scale: bool,
    digits: int = 4,
    baseline_supported: bool = True,
    unsupported_reason: Optional[str] = None,
) -> Dict[str, Any]:
    if not baseline_supported:
        return {
            "abs_diff": None,
            "pct_change": None,
            "pct_change_status": unsupported_reason or "withheld_insufficient_baseline",
        }
    if target_val is None or base_val is None or not math.isfinite(target_val) or not math.isfinite(base_val):
        return {
            "abs_diff": None,
            "pct_change": None,
            "pct_change_status": "withheld_missing_data",
        }
    diff, pct, status = safe_pct_change(target_val, base_val)
    if is_interval_scale:
        return {
            "abs_diff": _finite(diff, digits),
            "pct_change": None,
            "pct_change_status": "withheld_interval_scale",
        }
    return {
        "abs_diff": _finite(diff, digits),
        "pct_change": _finite(pct, 2),
        "pct_change_status": status,
    }


def _summarize_years(series: pd.Series, years: Sequence[int]) -> Dict[str, Any]:
    sub = series[series.index.isin(years)].dropna()
    vals = [float(v) for v in sub.tolist() if math.isfinite(float(v))]
    if not vals:
        return {
            "mean": None,
            "min": None,
            "max": None,
            "sd": None,
            "available_years": [],
            "status": "missing",
        }
    arr = np.asarray(vals, dtype=float)
    sd = float(np.std(arr, ddof=1)) if len(arr) >= 2 else None
    return {
        "mean": _finite(float(np.mean(arr)), 4),
        "min": _finite(float(np.min(arr)), 4),
        "max": _finite(float(np.max(arr)), 4),
        "sd": _finite(sd, 4),
        "available_years": [int(y) for y in sub.index.tolist()],
        "status": "computed",
    }


def _supported_baselines_for_spec(spec: CatalogVariableSpec) -> List[Dict[str, Any]]:
    is_fire = spec.metric_id.startswith("fire_")
    if is_fire:
        return [
            {
                "baseline_id": "2015-2019",
                "label": "2015–2019",
                "years": [2015, 2016, 2017, 2018, 2019],
                "supported": False,
                "role": "unsupported",
                "status": "withheld_insufficient_baseline",
                "unsupported_reason": "VIIRS S-NPP Archive Export in this repository starts in 2019-03; 2015-2018 data is absent so 2015-2019 baseline must stay disabled.",
            },
            {
                "baseline_id": "2019-2021",
                "label": "2019–2021",
                "years": [2019, 2020, 2021],
                "supported": True,
                "role": "primary",
                "status": "supported",
                "unsupported_reason": None,
            },
        ]
    return [
        {
            "baseline_id": "2015-2019",
            "label": "2015–2019",
            "years": [2015, 2016, 2017, 2018, 2019],
            "supported": True,
            "role": "primary",
            "status": "supported",
            "unsupported_reason": None,
        },
        {
            "baseline_id": "2019-2021",
            "label": "2019–2021",
            "years": [2019, 2020, 2021],
            "supported": True,
            "role": "sensitivity_recent",
            "status": "supported",
            "unsupported_reason": None,
        },
    ]


def _serialize_variable_spec(spec: CatalogVariableSpec) -> Dict[str, Any]:
    ukr_regions = ["kyiv_no2_box"] if spec.metric_id == "no2_mean_molec_cm2" else list(UKRAINE_BOX_IDS)
    if spec.element_id == "fire" and spec.metric_id.startswith("fire_"):
        ukr_regions = ["ukraine_national", *UKRAINE_BOX_IDS]
    ext_regions = [] if (spec.metric_id == "no2_mean_molec_cm2" or spec.metric_id.startswith("fire_")) else list(EXTERNAL_WEATHER_BOX_IDS)

    return {
        "metric_id": spec.metric_id,
        "element_id": spec.element_id,
        "element_label": spec.element_label,
        "label": spec.label,
        "short_label": spec.short_label,
        "plain_definition": PLAIN_DEFINITIONS_BY_METRIC_ID[spec.metric_id],
        "units": spec.units,
        "is_interval_scale": spec.is_interval_scale,
        "is_primary_indicator": spec.is_primary_indicator,
        "display_order": spec.display_order,
        "dates": {
            "start": spec.date_start,
            "end": spec.date_end,
            "seasonal_window": spec.seasonal_window,
            "monthly_granularity": "YYYY-MM",
            "n_years_available": spec.n_years_available,
        },
        "supported_baselines": _supported_baselines_for_spec(spec),
        "spatial_support": {
            "presentation_type": spec.presentation_type,
            "resolution": spec.resolution,
            "sampling_method": spec.sampling_method,
            "supports_fine_heatmap": spec.supports_fine_heatmap,
            "supports_spatial_cells": spec.supports_spatial_cells,
            "ukraine_region_ids": ukr_regions,
            "external_weather_region_ids": ext_regions,
        },
        "method_id": spec.method_id,
        "uncertainty_and_status": {
            "claim_status": "descriptive_regional_context_noncausal" if spec.element_id in {"water", "land"} else "descriptive_noncausal_observation",
            "is_interval_scale": spec.is_interval_scale,
            "pct_change_allowed": not spec.is_interval_scale,
            "pct_change_withheld_reason": (
                "Interval-scale or signed quantity crossing zero; report abs_diff instead of % change."
                if spec.is_interval_scale
                else None
            ),
            "statistical_significance_assessed": False,
        },
        "sources": list(spec.sources),
        "limitations": list(spec.limitations),
    }


def _build_region_lookup(spatial_audit: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    features: List[Dict[str, Any]] = []
    by_id: Dict[str, Any] = {}
    for box in STUDY_BOXES:
        audit_row = spatial_audit.get(box.region_id, {})
        in_ukr = box.region_id in UKRAINE_BOX_IDS
        feat = _box_geojson_feature(box, audit_row, include_in_ukr_map=in_ukr)
        features.append(feat)
        by_id[box.region_id] = feat
    return by_id, features


def build_atlas_catalog(
    spatial_audit: Mapping[str, Any],
    generated_at_utc: str,
) -> Dict[str, Any]:
    """Build the master 25-metric catalog JSON artifact."""
    _, region_features = _build_region_lookup(spatial_audit)
    variables = [_serialize_variable_spec(spec) for spec in CATALOG_VARIABLES]
    by_element: Dict[str, List[str]] = {"air": [], "fire": [], "land": [], "water": []}
    for spec in CATALOG_VARIABLES:
        by_element[spec.element_id].append(spec.metric_id)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc,
        "case_id": "ukraine",
        "conflict_start": CONFLICT_START_DATE,
        "metric_count": len(variables),
        "primary_indicators_by_element": dict(PRIMARY_INDICATORS_BY_ELEMENT),
        "variable_ids_by_element": by_element,
        "recommended_starter_flow": [
            {"element_id": "air", "element_label": "Air", "metric_id": "no2_mean_molec_cm2", "endpoint": "/api/air/kyiv"},
            {"element_id": "fire", "element_label": "Fire", "metric_id": "fire_type0_per_1k_km2_day", "endpoint": "/api/fire/ukraine"},
            {"element_id": "water", "element_label": "Water", "metric_id": "prectotcorr", "endpoint": "/api/water/ukraine"},
            {"element_id": "land", "element_label": "Earth", "metric_id": "gwettop", "endpoint": "/api/land/ukraine"},
        ],
        "variables": variables,
        "study_regions": {
            "type": "FeatureCollection",
            "features": region_features,
        },
        "global_limitations": [
            "Regional MERRA-2 (0.5 deg x 0.625 deg) and CERES (1.0 deg) box means describe synoptic environmental context, cannot generate local pollution/drought heatmaps, and do not rule out localized drought or prove war-caused damage.",
            "Fire hotspot counts are satellite thermal pixel detections (type 0 vs type 2), not burned area in km^2; 2015-2019 baseline is unavailable and must stay disabled.",
            "Single-season 2022 before-after comparisons are descriptive and cannot isolate causal war attribution without validated counterfactuals.",
        ],
    }


def _build_power_element_package(
    *,
    element_id: str,
    element_label: str,
    study_id: str,
    primary_metric_id: str,
    metric_ids: Sequence[str],
    panel_df: pd.DataFrame,
    spatial_audit: Mapping[str, Any],
    generated_at_utc: str,
    notices: Sequence[str],
    claim_status: Mapping[str, str],
    extra_sections: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Parameterized builder for Water, Earth (land), and Air-weather study packages."""
    ordered_regions = [*UKRAINE_BOX_IDS, *EXTERNAL_WEATHER_BOX_IDS]
    _, all_features = _build_region_lookup(spatial_audit)
    ukr_features = [f for f in all_features if f["properties"]["is_ukraine_study_area"]]
    lats_s = [BOX_BY_ID[r].south for r in UKRAINE_BOX_IDS]
    lats_n = [BOX_BY_ID[r].north for r in UKRAINE_BOX_IDS]
    lons_w = [BOX_BY_ID[r].west for r in UKRAINE_BOX_IDS]
    lons_e = [BOX_BY_ID[r].east for r in UKRAINE_BOX_IDS]

    regions_out: Dict[str, Any] = {}
    for region_id in ordered_regions:
        box = BOX_BY_ID[region_id]
        audit_row = spatial_audit.get(region_id, {})
        rdf = panel_df[panel_df["region_id"] == region_id].sort_values(["year", "month_num"])
        mar_aug_df = rdf[rdf["month_num"].isin(MARCH_AUGUST_MONTHS)]

        metrics_payload: Dict[str, Any] = {}
        for metric_id in metric_ids:
            spec = CATALOG_BY_ID[metric_id]
            annual_series = mar_aug_df.groupby("year")[metric_id].mean()
            b15 = _summarize_years(annual_series, range(2015, 2020))
            b19 = _summarize_years(annual_series, range(2019, 2022))
            t22_raw = annual_series.get(2022)
            t22_val = _finite(float(t22_raw), 4) if t22_raw is not None and pd.notna(t22_raw) else None

            seasonal_summary = {
                "window_label": "March–August",
                "baseline_2015_2019": b15,
                "baseline_2019_2021": b19,
                "target_2022": {
                    "mean": t22_val,
                    "available_years": [2022] if t22_val is not None else [],
                },
                "vs_2015_2019": _compute_change(t22_val, b15["mean"], spec.is_interval_scale),
                "vs_2019_2021": _compute_change(t22_val, b19["mean"], spec.is_interval_scale),
            }

            # Climatology lookup per calendar month (1..12) for monthly anomalies
            clim15: Dict[int, Optional[float]] = {}
            clim19: Dict[int, Optional[float]] = {}
            matched_months: List[Dict[str, Any]] = []
            for cal_m in range(1, 13):
                mdf = rdf[rdf["month_num"] == cal_m].set_index("year")[metric_id]
                mb15 = _summarize_years(mdf, range(2015, 2020))
                mb19 = _summarize_years(mdf, range(2019, 2022))
                clim15[cal_m] = mb15["mean"]
                clim19[cal_m] = mb19["mean"]
                if cal_m in MARCH_AUGUST_MONTHS:
                    mt22_raw = mdf.get(2022)
                    mt22 = _finite(float(mt22_raw), 4) if mt22_raw is not None and pd.notna(mt22_raw) else None
                    matched_months.append({
                        "calendar_month": cal_m,
                        "month_name": MONTH_NAMES[cal_m],
                        "baseline_2015_2019": mb15,
                        "baseline_2019_2021": mb19,
                        "target_2022": {
                            "mean": mt22,
                            "anomaly_vs_2015_2019": _finite(mt22 - mb15["mean"], 4)
                            if (mt22 is not None and mb15["mean"] is not None)
                            else None,
                            "anomaly_vs_2019_2021": _finite(mt22 - mb19["mean"], 4)
                            if (mt22 is not None and mb19["mean"] is not None)
                            else None,
                        },
                        "vs_2015_2019": _compute_change(mt22, mb15["mean"], spec.is_interval_scale),
                        "vs_2019_2021": _compute_change(mt22, mb19["mean"], spec.is_interval_scale),
                    })

            monthly_series: List[Dict[str, Any]] = []
            for row in rdf.itertuples(index=False):
                val_raw = getattr(row, metric_id)
                val = _finite(float(val_raw), 4) if pd.notna(val_raw) else None
                mnum = int(row.month_num)
                c15 = clim15.get(mnum)
                c19 = clim19.get(mnum)
                monthly_series.append({
                    "month": str(row.month),
                    "year": int(row.year),
                    "calendar_month": mnum,
                    "value": val,
                    "anomaly_vs_2015_2019_month_mean": _finite(val - c15, 4)
                    if (val is not None and c15 is not None)
                    else None,
                    "anomaly_vs_2019_2021_month_mean": _finite(val - c19, 4)
                    if (val is not None and c19 is not None)
                    else None,
                })

            metrics_payload[metric_id] = {
                "metric_id": metric_id,
                "units": spec.units,
                "is_interval_scale": spec.is_interval_scale,
                "seasonal_mar_aug": seasonal_summary,
                "matched_months": matched_months,
                "monthly_series": monthly_series,
            }

        regions_out[region_id] = {
            "region_id": region_id,
            "name": box.name,
            "role": box.role,
            "is_ukraine_study_area": region_id in UKRAINE_BOX_IDS,
            "area_km2": _finite(bbox_area_km2(box.west, box.south, box.east, box.north), 2),
            "center": {
                "lat": _finite((box.south + box.north) / 2.0, 4),
                "lon": _finite((box.west + box.east) / 2.0, 4),
            },
            "bounds": [[box.south, box.west], [box.north, box.east]],
            "geometry": _box_geojson_feature(box, audit_row, region_id in UKRAINE_BOX_IDS),
            "spatial_audit": {
                "pct_box_inside_ukr_adm0": audit_row.get("pct_box_inside_ukr_adm0"),
                "estimated_ukr_land_km2": audit_row.get("estimated_ukr_land_km2"),
                "lattice_points_inside_ukr_adm0": audit_row.get("lattice_points_inside_ukr_adm0"),
                "lattice_points_total": audit_row.get("lattice_points_total"),
            },
            "metrics": metrics_payload,
        }

    primary_spec = CATALOG_BY_ID[primary_metric_id]
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc,
        "case_id": "ukraine",
        "element_id": element_id,
        "element_label": element_label,
        "study_id": study_id,
        "conflict_start": CONFLICT_START_DATE,
        "primary_indicator": primary_metric_id,
        "available_variables": [_serialize_variable_spec(CATALOG_BY_ID[m]) for m in metric_ids],
        "supported_baselines": _supported_baselines_for_spec(primary_spec),
        "map": {
            "center": {
                "lat": _finite((min(lats_s) + max(lats_n)) / 2.0, 4),
                "lon": _finite((min(lons_w) + max(lons_e)) / 2.0, 4),
            },
            "bounds": [[min(lats_s), min(lons_w)], [max(lats_n), max(lons_e)]],
            "study_boxes": {
                "type": "FeatureCollection",
                "features": ukr_features,
            },
            "external_weather_boxes": {
                "type": "FeatureCollection",
                "features": [f for f in all_features if not f["properties"]["is_ukraine_study_area"]],
            },
            "rendering": "regional_study_boxes",
            "note": (
                "Regional study-box averages from NASA POWER (0.5 deg x 0.625 deg MERRA-2 / 1.0 deg CERES) provide regional "
                "environmental context only. They cannot produce local drought heatmaps, do not rule out localized drought stress, "
                "and do not directly measure war infrastructure damage."
            ),
        },
        "highlights": {
            "claim_status": dict(claim_status),
            "notices": list(notices),
        },
        "result": {
            "region_order_ukraine": list(UKRAINE_BOX_IDS),
            "region_order_external_weather": list(EXTERNAL_WEATHER_BOX_IDS),
            "regions": regions_out,
        },
        "limitations": list(primary_spec.limitations),
    }
    if extra_sections:
        payload["result"].update(extra_sections)
    return payload


def _build_fire_spatial_cells(
    clean_firms_df: pd.DataFrame,
    fire_results: Mapping[str, Any],
    ukr_path: Any,
    step_deg: float = 0.25,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Aggregate validated VIIRS detections onto a deterministic 0.25 deg grid."""
    gap_rows = fire_results.get("missing_observation_gaps", {}).get("satellite_month_coverage", [])
    obs_days_by_month: Dict[str, Dict[str, Any]] = {
        str(row["month"]): {
            "year": int(row["year"]),
            "calendar_month": int(row["calendar_month"]),
            "calendar_days": int(row["calendar_days"]),
            "satellite_observed_days": int(row["satellite_observed_days"]),
            "satellite_missing_days": int(row["satellite_missing_days"]),
            "satellite_coverage_fraction": _finite(float(row["satellite_coverage_fraction"]), 4),
            "has_cmr_outage_gap": str(row["month"]) in FIRE_OUTAGE_MONTHS or int(row["satellite_missing_days"]) > 0,
        }
        for row in gap_rows
    }

    work = clean_firms_df[clean_firms_df["mnum"].isin(STUDY_MONTHS)].copy()
    work["cell_lat"] = ((work["latitude"] / step_deg).round() * step_deg).round(2)
    work["cell_lon"] = ((work["longitude"] / step_deg).round() * step_deg).round(2)
    work["is_nh"] = work["confidence"].isin(["n", "h"])

    work["t0_all"] = (work["type"] == 0).astype(int)
    work["t0_nh"] = ((work["type"] == 0) & work["is_nh"]).astype(int)
    work["t2_all"] = (work["type"] == 2).astype(int)
    work["t2_nh"] = ((work["type"] == 2) & work["is_nh"]).astype(int)
    work["t3_all"] = (work["type"] == 3).astype(int)

    # Unique active cell centers evaluated against UKR-ADM0 polygon and study boxes once
    unique_cells = (
        work[["cell_lat", "cell_lon"]]
        .drop_duplicates()
        .sort_values(["cell_lat", "cell_lon"])
        .reset_index(drop=True)
    )
    coords = unique_cells[["cell_lon", "cell_lat"]].to_numpy(dtype=float)
    in_ukr_arr = ukr_path.contains_points(coords)
    unique_cells["in_ukr_adm0"] = in_ukr_arr

    cell_meta: Dict[Tuple[float, float], Dict[str, Any]] = {}
    grid_index: List[Dict[str, Any]] = []
    half = step_deg / 2.0
    for idx, row in enumerate(unique_cells.itertuples(index=False)):
        clat = float(row.cell_lat)
        clon = float(row.cell_lon)
        cell_id = f"{clat:.2f}_{clon:.2f}"
        regions = ["ukraine_national"] + [
            box_id
            for box_id in UKRAINE_BOX_IDS
            if (BOX_BY_ID[box_id].south <= clat <= BOX_BY_ID[box_id].north)
            and (BOX_BY_ID[box_id].west <= clon <= BOX_BY_ID[box_id].east)
        ]
        meta = {
            "cell_id": cell_id,
            "lat": clat,
            "lon": clon,
            "bounds": [
                [_finite(clat - half, 3), _finite(clon - half, 3)],
                [_finite(clat + half, 3), _finite(clon + half, 3)],
            ],
            "in_ukr_adm0": bool(row.in_ukr_adm0),
            "region_ids": regions,
        }
        cell_meta[(clat, clon)] = meta
        grid_index.append(meta)

    # Monthly complete-grid rows across 2019-03 .. 2022-08
    monthly_agg = (
        work.groupby(["month", "year", "mnum", "cell_lat", "cell_lon"], as_index=False)
        .agg(
            type0_all_count=("t0_all", "sum"),
            type0_nh_count=("t0_nh", "sum"),
            type2_all_count=("t2_all", "sum"),
            type2_nh_count=("t2_nh", "sum"),
            type3_all_count=("t3_all", "sum"),
            frp_sum_mw=("frp", "sum"),
        )
        .sort_values(["month", "cell_lat", "cell_lon"])
    )

    monthly_rows: List[Dict[str, Any]] = []
    for row in monthly_agg.itertuples(index=False):
        meta = cell_meta[(float(row.cell_lat), float(row.cell_lon))]
        month_str = str(row.month)
        cov = obs_days_by_month.get(month_str, {})
        monthly_rows.append({
            "month": month_str,
            "year": int(row.year),
            "calendar_month": int(row.mnum),
            "cell_id": meta["cell_id"],
            "lat": meta["lat"],
            "lon": meta["lon"],
            "type0_all_count": int(row.type0_all_count),
            "type0_nh_count": int(row.type0_nh_count),
            "type2_all_count": int(row.type2_all_count),
            "type2_nh_count": int(row.type2_nh_count),
            "type3_all_count": int(row.type3_all_count),
            "frp_sum_mw": _finite(float(row.frp_sum_mw), 2),
            "cmr_observed_days": cov.get("satellite_observed_days"),
            "in_cmr_outage_month": bool(cov.get("has_cmr_outage_gap", False)),
            "in_ukr_adm0": meta["in_ukr_adm0"],
        })

    # Compact per-cell seasonal comparison summary (2019-2021 annual mean vs 2022 Mar-Aug)
    yearly_cell = (
        work.groupby(["cell_lat", "cell_lon", "year"], as_index=False)
        .agg(
            t0_all=("t0_all", "sum"),
            t0_nh=("t0_nh", "sum"),
            t2_all=("t2_all", "sum"),
            t2_nh=("t2_nh", "sum"),
            frp=("frp", "sum"),
        )
    )
    by_cell_year: Dict[Tuple[float, float, int], Tuple[int, int, int, int, float]] = {}
    for row in yearly_cell.itertuples(index=False):
        by_cell_year[(float(row.cell_lat), float(row.cell_lon), int(row.year))] = (
            int(row.t0_all),
            int(row.t0_nh),
            int(row.t2_all),
            int(row.t2_nh),
            float(row.frp),
        )

    seasonal_cells: List[Dict[str, Any]] = []
    for meta in grid_index:
        clat = float(meta["lat"])
        clon = float(meta["lon"])
        y2019 = by_cell_year.get((clat, clon, 2019), (0, 0, 0, 0, 0.0))
        y2020 = by_cell_year.get((clat, clon, 2020), (0, 0, 0, 0, 0.0))
        y2021 = by_cell_year.get((clat, clon, 2021), (0, 0, 0, 0, 0.0))
        y2022 = by_cell_year.get((clat, clon, 2022), (0, 0, 0, 0, 0.0))
        base_t0_nh_mean = (y2019[1] + y2020[1] + y2021[1]) / 3.0
        base_t0_all_mean = (y2019[0] + y2020[0] + y2021[0]) / 3.0
        base_t2_all_mean = (y2019[2] + y2020[2] + y2021[2]) / 3.0
        seasonal_cells.append({
            "cell_id": meta["cell_id"],
            "lat": clat,
            "lon": clon,
            "in_ukr_adm0": meta["in_ukr_adm0"],
            "region_ids": meta["region_ids"],
            "type0_nh_2019_2021_mean": _finite(base_t0_nh_mean, 2),
            "type0_nh_2022": int(y2022[1]),
            "type0_nh_abs_diff": _finite(y2022[1] - base_t0_nh_mean, 2),
            "type0_all_2019_2021_mean": _finite(base_t0_all_mean, 2),
            "type0_all_2022": int(y2022[0]),
            "type0_all_abs_diff": _finite(y2022[0] - base_t0_all_mean, 2),
            "type2_all_2019_2021_mean": _finite(base_t2_all_mean, 2),
            "type2_all_2022": int(y2022[2]),
            "frp_sum_mw_2022": _finite(y2022[4], 2),
        })

    cells_package = {
        "schema_version": SCHEMA_VERSION,
        "case_id": "ukraine",
        "element_id": "fire",
        "study_id": "ukraine",
        "grid_step_deg": step_deg,
        "season_window": "March-August (2019-2022)",
        "completeness_note": (
            "cell_registry lists every 0.25 deg cell observed across 2019-03..2022-08; any (month, cell_id) pair "
            "omitted from monthly_cells had zero FIRMS VIIRS SV-C2 detections during that month's CMR-observed days."
        ),
        "cmr_month_coverage": [
            {"month": m, **obs_days_by_month[m]}
            for m in sorted(obs_days_by_month)
        ],
        "cell_registry": grid_index,
        "monthly_cells": monthly_rows,
    }
    return seasonal_cells, cells_package


def build_fire_study_package(
    fire_results: Mapping[str, Any],
    firms_matched_audit: Mapping[str, Any],
    spatial_audit: Mapping[str, Any],
    panel_df: pd.DataFrame,
    seasonal_cells: Sequence[Dict[str, Any]],
    generated_at_utc: str,
) -> Dict[str, Any]:
    """Build reviewed Fire study package separating primary, matched-date, and legacy rates."""
    _, all_features = _build_region_lookup(spatial_audit)
    ukr_features = [f for f in all_features if f["properties"]["is_ukraine_study_area"]]

    nat_meta = next((r for r in fire_results.get("proposed_regions", []) if r["region_id"] == "ukraine_national"), {})
    nat_bbox = nat_meta.get("bounding_box", {"south": 44.3, "north": 52.5, "west": 22.0, "east": 40.3})
    nat_area_km2 = bbox_area_km2(
        float(nat_bbox["west"]),
        float(nat_bbox["south"]),
        float(nat_bbox["east"]),
        float(nat_bbox["north"]),
    )

    area_by_region: Dict[str, float] = {
        "ukraine_national": nat_area_km2,
        **{
            rid: bbox_area_km2(BOX_BY_ID[rid].west, BOX_BY_ID[rid].south, BOX_BY_ID[rid].east, BOX_BY_ID[rid].north)
            for rid in UKRAINE_BOX_IDS
        },
    }

    pre2022_by_region: Dict[str, List[Dict[str, Any]]] = {}
    for item in fire_results.get("pre_2022_comparability", []):
        pre2022_by_region.setdefault(str(item["study_region_id"]), []).append(dict(item))

    # Index fire monthly_series by (region_id, filter_mode)
    monthly_by_rf: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in fire_results.get("monthly_series", []):
        monthly_by_rf.setdefault((str(row["region_id"]), str(row["filter_mode"])), []).append(dict(row))

    audit_regional = firms_matched_audit.get("regional_matched_outage", {})
    filter_modes = (
        ("type0_vegetation_nominal_high", "type0_nh", "Presumed vegetation (type 0), nominal/high confidence"),
        ("type0_vegetation_all_conf", "type0_all", "Presumed vegetation (type 0), all confidences"),
        ("type2_static_industrial", "type2_all", "Other static land source (type 2), all confidences"),
    )

    fire_regions_out: Dict[str, Any] = {}
    ordered_fire_regions = ("ukraine_national", *UKRAINE_BOX_IDS)
    for rid in ordered_fire_regions:
        area_km2 = area_by_region[rid]
        scale_1k = area_km2 / 1000.0
        reg_comp = fire_results.get("regional_comparisons", {}).get(rid, {})
        matched_audit_reg = audit_regional.get(rid, {})

        seasonal_by_filter: Dict[str, Any] = {}
        monthly_by_filter: Dict[str, List[Dict[str, Any]]] = {}
        matched_months_by_filter: Dict[str, List[Dict[str, Any]]] = {}

        for fmode, audit_key, fdesc in filter_modes:
            mar_aug = reg_comp.get(fmode, {}).get("mar_aug", {})
            yearly = mar_aug.get("yearly", {})
            base_rate_day = mar_aug.get("baseline_2019_2021", {}).get("mean_rate_per_observed_day")
            t22_rate_day = mar_aug.get("target_2022", {}).get("rate_per_observed_day")
            primary_base_raw = float(base_rate_day) / scale_1k if base_rate_day is not None else None
            primary_2022_raw = float(t22_rate_day) / scale_1k if t22_rate_day is not None else None
            primary_base = _finite(primary_base_raw, 4) if primary_base_raw is not None else None
            primary_2022 = _finite(primary_2022_raw, 4) if primary_2022_raw is not None else None

            annual_primary: Dict[str, Any] = {}
            for yr in ("2019", "2020", "2021", "2022"):
                yrow = yearly.get(yr, {})
                yrate = yrow.get("rate_per_observed_day")
                annual_primary[yr] = {
                    "rate_per_1k_km2_obs_day": _finite(float(yrate) / scale_1k, 4) if yrate is not None else None,
                    "detections": yrow.get("detections"),
                    "satellite_observed_days": yrow.get("satellite_observed_days"),
                    "legacy_rate_per_observed_day": _finite(yrow.get("rate_per_observed_day"), 4),
                    "unique_0_01deg_cell_days": yrow.get("unique_0_01deg_cell_days"),
                    "frp_sum_mw": _finite(yrow.get("frp_sum_mw"), 2),
                }

            seasonal_by_filter[fmode] = {
                "filter_mode": fmode,
                "label": fdesc,
                "primary_metric": {
                    "method_id": FIRE_PRIMARY_METHOD_ID,
                    "units": "det / 1000 km^2 / day",
                    "annual": annual_primary,
                    "baseline_2019_2021_mean": primary_base,
                    "target_2022": primary_2022,
                    "vs_2019_2021": _compute_change(primary_2022_raw, primary_base_raw, is_interval_scale=False),
                    "vs_2015_2019": _compute_change(
                        primary_2022,
                        None,
                        is_interval_scale=False,
                        baseline_supported=False,
                        unsupported_reason="withheld_insufficient_baseline",
                    ),
                },
                "matched_dates_169d_ukr_adm0_sensitivity": {
                    "method_id": FIRE_MATCHED_SENSITIVITY_METHOD_ID,
                    "sensitivity_only": True,
                    "note": "Pooled 169 common CMR-observed dates/year inside UKR-ADM0 polygon land area; kept strictly separate from primary box-area normalization.",
                    **(matched_audit_reg.get(audit_key, {}) if matched_audit_reg else {"status": "not_tabulated_at_national_level"}),
                },
                "legacy_unnormalized_rate": {
                    "method_id": FIRE_LEGACY_METHOD_ID,
                    "legacy_only": True,
                    "units": "detections / observed_day",
                    "baseline_2019_2021_mean_rate": _finite(base_rate_day, 4),
                    "target_2022_rate": _finite(t22_rate_day, 4),
                    "vs_2019_2021": {
                        "abs_diff": _finite(mar_aug.get("vs_baseline_2019_2021", {}).get("rate_per_day_abs_change"), 4),
                        "pct_change": _finite(mar_aug.get("vs_baseline_2019_2021", {}).get("rate_per_day_pct_change"), 2),
                        "pct_change_status": mar_aug.get("vs_baseline_2019_2021", {}).get("rate_per_day_pct_status", "withheld_missing_data"),
                    },
                    "baseline_2019_2021_mean_detections": _finite(mar_aug.get("baseline_2019_2021", {}).get("mean_detections"), 2),
                    "target_2022_detections": mar_aug.get("target_2022", {}).get("detections"),
                },
            }

            raw_mrows = sorted(monthly_by_rf.get((rid, fmode), []), key=lambda x: str(x["month"]))
            out_mrows: List[Dict[str, Any]] = []
            by_cal_year: Dict[Tuple[int, int], float] = {}
            for mr in raw_mrows:
                rate_day = mr.get("detections_per_observed_day")
                rate_norm_raw = float(rate_day) / scale_1k if rate_day is not None else None
                rate_norm = _finite(rate_norm_raw, 4) if rate_norm_raw is not None else None
                mstr = str(mr["month"])
                yr_i = int(mr["year"])
                c_i = int(mr["calendar_month"])
                if rate_norm_raw is not None and math.isfinite(rate_norm_raw):
                    by_cal_year[(c_i, yr_i)] = rate_norm_raw
                out_mrows.append({
                    "month": mstr,
                    "year": yr_i,
                    "calendar_month": c_i,
                    "detections": int(mr["detections"]),
                    "satellite_observed_days": int(mr["satellite_observed_days"]),
                    "calendar_days": int(mr["calendar_days"]),
                    "satellite_coverage_fraction": _finite(mr.get("satellite_coverage_fraction"), 4),
                    "has_cmr_outage_gap": mstr in FIRE_OUTAGE_MONTHS or int(mr["satellite_observed_days"]) < int(mr["calendar_days"]),
                    "rate_per_1k_km2_obs_day": rate_norm,
                    "legacy_detections_per_observed_day": _finite(rate_day, 4),
                    "unique_0_01deg_cell_days": int(mr["unique_0_01deg_cell_days"]),
                    "day_detections": int(mr["day_detections"]),
                    "night_detections": int(mr["night_detections"]),
                    "frp_sum_mw": _finite(mr.get("frp_sum_mw"), 2),
                    "frp_median_mw": _finite(mr.get("frp_median_mw"), 2),
                })
            monthly_by_filter[fmode] = out_mrows

            mm_list: List[Dict[str, Any]] = []
            for cal_m in MARCH_AUGUST_MONTHS:
                vals_b = [by_cal_year[(cal_m, y)] for y in (2019, 2020, 2021) if (cal_m, y) in by_cal_year]
                base_m = float(np.mean(vals_b)) if vals_b else None
                t22_m = by_cal_year.get((cal_m, 2022))
                mm_list.append({
                    "calendar_month": cal_m,
                    "month_name": MONTH_NAMES[cal_m],
                    "baseline_2019_2021_mean": _finite(base_m, 4),
                    "baseline_2019_2021_min": _finite(min(vals_b), 4) if vals_b else None,
                    "baseline_2019_2021_max": _finite(max(vals_b), 4) if vals_b else None,
                    "target_2022": _finite(t22_m, 4),
                    "vs_2019_2021": _compute_change(t22_m, base_m, is_interval_scale=False),
                    "vs_2015_2019": _compute_change(
                        t22_m,
                        None,
                        is_interval_scale=False,
                        baseline_supported=False,
                        unsupported_reason="withheld_insufficient_baseline",
                    ),
                })
            matched_months_by_filter[fmode] = mm_list

        audit_row = spatial_audit.get(rid, {})
        box_obj = BOX_BY_ID.get(rid)
        bbox_dict = (
            {"south": box_obj.south, "north": box_obj.north, "west": box_obj.west, "east": box_obj.east}
            if box_obj is not None
            else nat_bbox
        )
        name = box_obj.name if box_obj is not None else str(nat_meta.get("name", "Ukraine (Full Country Export)"))
        role = box_obj.role if box_obj is not None else "national_aggregate"

        fire_regions_out[rid] = {
            "region_id": rid,
            "name": name,
            "role": role,
            "area_km2": _finite(area_km2, 2),
            "bounding_box": bbox_dict,
            "spatial_audit": audit_row if audit_row else {"note": "National export extent bounding Ukraine ADM0 + Black Sea offshore points."},
            "pre_2022_comparator_matches": pre2022_by_region.get(rid, []),
            "seasonal_comparisons_mar_aug": seasonal_by_filter,
            "matched_months_mar_aug": matched_months_by_filter,
            "monthly_series": monthly_by_filter,
        }

    # Fire-context NASA POWER variables across the 6 Ukraine boxes (reuse shared builder)
    fire_weather_pkg = _build_power_element_package(
        element_id="fire",
        element_label="Fire",
        study_id="ukraine",
        primary_metric_id="t2m",
        metric_ids=("t2m", "t2m_max", "dtr_c", "allsky_sfc_sw_dwn", "pet_fao56_mm_day"),
        panel_df=panel_df,
        spatial_audit=spatial_audit,
        generated_at_utc=generated_at_utc,
        notices=(),
        claim_status={},
    )

    # Fire-vs-dryness scatter points across the 6 Ukraine boxes (2019-2022 Mar-Aug)
    scatter_df = panel_df[
        panel_df["region_id"].isin(UKRAINE_BOX_IDS)
        & panel_df["year"].isin(STUDY_YEARS)
        & panel_df["month_num"].isin(STUDY_MONTHS)
    ].sort_values(["region_id", "year", "month_num"])
    fire_dryness_scatter: List[Dict[str, Any]] = []
    for row in scatter_df.itertuples(index=False):
        rid = str(row.region_id)
        fire_dryness_scatter.append({
            "region_id": rid,
            "role": BOX_BY_ID[rid].role,
            "month": str(row.month),
            "year": int(row.year),
            "calendar_month": int(row.month_num),
            "is_2022_war_year": int(row.year) == 2022,
            "in_cmr_outage_month": str(row.month) in FIRE_OUTAGE_MONTHS,
            "fire_type0_per_1k_km2_day": _finite(float(row.fire_type0_per_1k_km2_day), 4)
            if pd.notna(row.fire_type0_per_1k_km2_day)
            else None,
            "vpd_kpa": _finite(float(row.vpd_kpa), 4) if pd.notna(row.vpd_kpa) else None,
            "pet_fao56_mm_day": _finite(float(row.pet_fao56_mm_day), 4) if pd.notna(row.pet_fao56_mm_day) else None,
            "prectotcorr": _finite(float(row.prectotcorr), 4) if pd.notna(row.prectotcorr) else None,
            "gwettop": _finite(float(row.gwettop), 4) if pd.notna(row.gwettop) else None,
            "t2m_max": _finite(float(row.t2m_max), 3) if pd.notna(row.t2m_max) else None,
        })

    fire_vars = [
        _serialize_variable_spec(CATALOG_BY_ID[m])
        for m in (
            "fire_type0_per_1k_km2_day",
            "fire_type2_per_1k_km2_day",
            "t2m",
            "t2m_max",
            "dtr_c",
            "allsky_sfc_sw_dwn",
            "pet_fao56_mm_day",
        )
    ]
    missing_gaps = fire_results.get("missing_observation_gaps", {})
    repeated_summary = fire_results.get("repeated_detections_summary", {})
    raw_bounds = [
        [float(nat_bbox["south"]), float(nat_bbox["west"])],
        [float(nat_bbox["north"]), float(nat_bbox["east"])],
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc,
        "case_id": "ukraine",
        "element_id": "fire",
        "element_label": "Fire",
        "study_id": "ukraine",
        "conflict_start": CONFLICT_START_DATE,
        "primary_indicator": "fire_type0_per_1k_km2_day",
        "cells_endpoint": "/api/fire/ukraine/cells",
        "available_variables": fire_vars,
        "supported_baselines": _supported_baselines_for_spec(CATALOG_BY_ID["fire_type0_per_1k_km2_day"]),
        "normalization": {
            "primary_method_id": FIRE_PRIMARY_METHOD_ID,
            "primary_label": "VIIRS presumed vegetation detections (type 0) per 1,000 km^2 of box area per CMR-observed satellite day",
            "primary_units": "det / 1000 km^2 / day",
            "separately_reported_methods": [
                {
                    "method_id": FIRE_MATCHED_SENSITIVITY_METHOD_ID,
                    "role": "sensitivity_check",
                    "description": "169 common matched calendar dates/year clipped to UKR-ADM0 polygon land area; stored under matched_dates_169d_ukr_adm0_sensitivity.",
                },
                {
                    "method_id": FIRE_LEGACY_METHOD_ID,
                    "role": "legacy_reference",
                    "description": "Unnormalized detections per observed day; stored under legacy_unnormalized_rate.",
                },
            ],
        },
        "filters": {
            "default_type_filter": "type0_vegetation_nominal_high",
            "supported_filter_modes": [
                {"filter_mode": m_id, "label": lbl}
                for m_id, _, lbl in filter_modes
            ],
        },
        "quality_flags": {
            "unsupported_baseline_2015_2019": True,
            "unsupported_baseline_reason": "VIIRS SV-C2 export begins 2019-03; 2015-2019 comparison is disabled/withheld.",
            "cmr_orbit_outage_2022": {
                "missing_dates_count_2022": missing_gaps.get("2022_missing_dates_count"),
                "missing_dates_2022": missing_gaps.get("2022_missing_dates", []),
                "primary_outage_window": "2022-07-27 to 2022-08-10 (15 consecutive days; plus 2022-03-05)",
                "satellite_month_coverage": missing_gaps.get("satellite_month_coverage", []),
            },
            "repeated_overpass_clustering": {
                "definition": repeated_summary.get("definition"),
                "all_types_overall": repeated_summary.get("all_types_overall"),
                "type0_vegetation_overall": repeated_summary.get("type0_vegetation_overall"),
            },
            "static_source_caveat": "Type-2 detections track industrial/gas-flare sources; frontline drops reflect shutdown/damage rather than reduced fire risk.",
        },
        "map": {
            "center": {"lat": 48.4, "lon": 31.15},
            "bounds": raw_bounds,
            "study_boxes": {
                "type": "FeatureCollection",
                "features": ukr_features,
            },
            "grid_step_deg": 0.25,
            "rendering": "spatial_cells_and_regional_boxes",
            "note": (
                "0.25 deg spatial grid cells aggregate raw 375 m VIIRS hotspot detections (2019-2022 Mar-Aug). "
                "Hotspot counts reflect thermal pixel detections, not burned area in km^2; 2022-07/2022-08 contain a 15-day S-NPP outage."
            ),
        },
        "highlights": {
            "claim_status": dict(fire_results.get("status", {})),
            "notices": [
                "2015-2019 baseline is disabled for VIIRS Fire metrics because archived detections start in March 2019.",
                "One primary normalization (detections / 1,000 km^2 / CMR observed day) is presented; matched-date (169d UKR-ADM0) sensitivity and legacy rates are kept strictly separate.",
                "March-August 2022 excludes 16 unobserved satellite days from the CMR denominator (notably Jul 27 - Aug 10 S-NPP orbit outage).",
            ],
        },
        "result": {
            "region_order": list(ordered_fire_regions),
            "regions": fire_regions_out,
            "seasonal_spatial_cells_025deg": list(seasonal_cells),
            "context_weather_regions": {
                rid: {
                    "region_id": rdata["region_id"],
                    "name": rdata["name"],
                    "role": rdata["role"],
                    "metrics": rdata["metrics"],
                }
                for rid, rdata in fire_weather_pkg["result"]["regions"].items()
                if rid in UKRAINE_BOX_IDS
            },
            "fire_dryness_scatter": fire_dryness_scatter,
            "top_static_type2_cells": firms_matched_audit.get("top_static_type2_cells", []),
        },
        "limitations": list(fire_results.get("limitations", [])),
    }


def generate_atlas_exports(reports_dir: Path = DEFAULT_REPORTS_DIR) -> Dict[str, Path]:
    """Regenerate all six atlas JSON artifacts in ``reports_dir`` deterministically."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at_utc = datetime.now(timezone.utc).isoformat()

    panel_df = pd.read_csv(reports_dir / "four_elements_monthly_panel.csv")
    air_results = json.loads((reports_dir / "air_no2_results.json").read_text(encoding="utf-8"))
    no2_regional_path = reports_dir / "atlas_no2_regional.json"
    no2_regional = (
        json.loads(no2_regional_path.read_text(encoding="utf-8"))
        if no2_regional_path.is_file()
        else None
    )
    fire_results = json.loads((reports_dir / "fire_viirs_results.json").read_text(encoding="utf-8"))
    kyiv_four_results = json.loads((reports_dir / "kyiv_four_elements_results.json").read_text(encoding="utf-8"))
    spatial_audit = json.loads((FROZEN_DIR / "spatial_mask_audit.json").read_text(encoding="utf-8"))
    firms_matched_audit = json.loads((FROZEN_DIR / "firms_cmr_matched_audit.json").read_text(encoding="utf-8"))

    power_specs = [
        s for s in CATALOG_VARIABLES
        if s.metric_id != "no2_mean_molec_cm2" and not s.metric_id.startswith("fire_")
    ]
    kyiv_no2_sensitivities = build_kyiv_no2_sensitivities(
        air_results=air_results,
        panel_df=panel_df,
        kyiv_four_results=kyiv_four_results,
    )
    krakow_prague_comparison = build_krakow_prague_comparison(
        panel_df,
        power_specs,
        air_results=air_results,
        no2_regional=no2_regional,
    )

    fire_inputs = discover_fire_inputs()
    clean_firms_df, _ = load_and_validate_firms_archives(fire_inputs)
    ukr_path = load_ukraine_adm0_path()
    seasonal_cells, cells_package = _build_fire_spatial_cells(clean_firms_df, fire_results, ukr_path)

    catalog = build_atlas_catalog(spatial_audit, generated_at_utc)
    fire_pkg = build_fire_study_package(
        fire_results=fire_results,
        firms_matched_audit=firms_matched_audit,
        spatial_audit=spatial_audit,
        panel_df=panel_df,
        seasonal_cells=seasonal_cells,
        generated_at_utc=generated_at_utc,
    )
    water_pkg = _build_power_element_package(
        element_id="water",
        element_label="Water",
        study_id="ukraine",
        primary_metric_id="prectotcorr",
        metric_ids=("prectotcorr", "vpd_kpa", "qv2m", "rh2m", "evptrns_mm_day", "precip_minus_pet_mm_day"),
        panel_df=panel_df,
        spatial_audit=spatial_audit,
        generated_at_utc=generated_at_utc,
        notices=(
            "Regional MERRA-2/CERES study-box values (0.5 deg x 0.625 deg / 1.0 deg) provide hydrologic background context only.",
            "Box-scale averages do not rule out localized seasonal drought and do not observe reservoir, pipe, or water-quality damage.",
            "Rainfall (prectotcorr) and VPD (vpd_kpa) are featured primary context metrics; relative % change is withheld for signed water balance (P - PET).",
        ),
        claim_status={
            "overall": "regional_environmental_context_only",
            "localized_drought_exclusion": "not_established_coarse_box_averages",
            "direct_water_damage_evidence": "not_available_in_reanalysis_layer",
        },
    )
    earth_pkg = _build_power_element_package(
        element_id="land",
        element_label="Earth",
        study_id="ukraine",
        primary_metric_id="gwettop",
        metric_ids=("gwettop", "gwetroot", "gwetprof", "ts", "ts_minus_t2m_c", "allsky_srf_alb"),
        panel_df=panel_df,
        spatial_audit=spatial_audit,
        generated_at_utc=generated_at_utc,
        notices=(
            "Regional MERRA-2/CERES study-box soil wetness (0.5 deg) and albedo (1.0 deg) provide broad land-surface context only.",
            "Coarse regional wetness means do not rule out localized drought and do not directly observe cratering, landmines, or soil contamination.",
            "Surface temperature (ts) and surface-air difference (ts_minus_t2m_c) withhold relative % change on interval-scale °C units.",
        ),
        claim_status={
            "overall": "regional_environmental_context_only",
            "localized_drought_exclusion": "not_established_coarse_box_averages",
            "direct_land_damage_evidence": "not_available_in_reanalysis_layer",
        },
    )
    air_weather_pkg = _build_power_element_package(
        element_id="air",
        element_label="Air",
        study_id="weather",
        primary_metric_id="ws10m",
        metric_ids=("ws10m", "cloud_amt", "ps", "clrsky_sfc_sw_dwn", "cloud_radiative_attenuation_wm2"),
        panel_df=panel_df,
        spatial_audit=spatial_audit,
        generated_at_utc=generated_at_utc,
        notices=(
            "Additive regional meteorology context paired with Milestone 1 Kyiv OMI NO2 (/api/air/kyiv remains unchanged).",
            "Daily NO2-wind/cloud stratification confirms wind and cloud confounding; cloud radiative attenuation withholds % change.",
        ),
        claim_status={
            "overall": "kyiv_no2_confounder_and_regional_weather_context",
            "causal_attribution": "not_established",
        },
        extra_sections={
            "kyiv_daily_wind_cloud_sensitivity": kyiv_four_results.get("kyiv_daily_wind_cloud_sensitivity", {}),
            "kyiv_no2_companion_endpoint": "/api/air/kyiv",
            "kyiv_no2_sensitivities": kyiv_no2_sensitivities,
            "krakow_prague_2022_comparison": krakow_prague_comparison,
        },
    )

    outputs: Dict[str, Tuple[Path, Dict[str, Any]]] = {
        "atlas_catalog": (reports_dir / "atlas_catalog.json", catalog),
        "atlas_fire_ukraine": (reports_dir / "atlas_fire_ukraine.json", fire_pkg),
        "atlas_fire_cells": (reports_dir / "atlas_fire_cells.json", cells_package),
        "atlas_water_ukraine": (reports_dir / "atlas_water_ukraine.json", water_pkg),
        "atlas_earth_ukraine": (reports_dir / "atlas_earth_ukraine.json", earth_pkg),
        "atlas_air_weather_ukraine": (reports_dir / "atlas_air_weather_ukraine.json", air_weather_pkg),
    }

    paths: Dict[str, Path] = {}
    for key, (path, obj) in outputs.items():
        if key == "atlas_catalog":
            write_strict_json(path, obj)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(obj, allow_nan=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        paths[key] = path
    return paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build atlas-ready four-element JSON exports.")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = generate_atlas_exports(args.reports_dir)
    for key, path in paths.items():
        size_kb = path.stat().st_size / 1024.0
        print(f"wrote {key}: {path} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
