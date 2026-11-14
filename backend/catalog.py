"""Static catalogue: cases, elements and the chart allowlist.

Only entries listed here are ever served. Chart files are resolved from
this allowlist, never from a path supplied by a request or by the JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

CASE_ID = "ukraine"
CASE_NAME = "Ukraine"
CONFLICT_START = "2022-02-24"

AIR_ELEMENT_ID = "air"
AIR_STUDY_ID = "kyiv"
AIR_STUDY_NAME = "Kyiv, Ukraine"
AIR_INDICATOR = "Tropospheric NO₂ column (OMI OMNO2d v004)"
AIR_STUDY_ENDPOINT = "/api/air/kyiv"

FIRE_ELEMENT_ID = "fire"
FIRE_STUDY_ID = "ukraine"
FIRE_STUDY_NAME = "Ukraine Regions & 0.25° Cells"
FIRE_INDICATOR = "VIIRS Vegetation Fire Density (SV-C2, per 1,000 km²/day)"
FIRE_STUDY_ENDPOINT = "/api/fire/ukraine"

LAND_ELEMENT_ID = "land"
LAND_STUDY_ID = "ukraine"
LAND_STUDY_NAME = "Ukraine Regional Boxes (Context)"
LAND_INDICATOR = "Surface Soil Wetness (0–5 cm, MERRA-2 GWETTOP)"
LAND_STUDY_ENDPOINT = "/api/land/ukraine"

WATER_ELEMENT_ID = "water"
WATER_STUDY_ID = "ukraine"
WATER_STUDY_NAME = "Ukraine Regional Boxes (Context)"
WATER_INDICATOR = "Bias-Corrected Rainfall & VPD (MERRA-2)"
WATER_STUDY_ENDPOINT = "/api/water/ukraine"

FIRE_VALID_REGION_IDS = (
    "ukraine_national",
    "donbas_kharkiv_east",
    "south_steppe_belt",
    "kyiv_north_belt",
    "kyiv_no2_box",
    "central_interior_cand",
    "west_ukraine_cand",
)


@dataclass(frozen=True)
class ChartSpec:
    chart_id: str
    filename: str
    title: str


# Keys match the ``charts`` object in reports/air_no2_results.json.
AIR_KYIV_CHARTS: Dict[str, ChartSpec] = {
    spec.chart_id: spec
    for spec in (
        ChartSpec(
            "monthly_timeline",
            "no2_monthly.png",
            "Monthly tropospheric NO₂ over the Kyiv study box, 2015–2022",
        ),
        ChartSpec(
            "seasonal_comparison",
            "no2_seasonal_comparison.png",
            "March–August 2022 compared with the 2015–2019 and 2019–2021 baselines",
        ),
        ChartSpec(
            "matched_months",
            "no2_matched_months.png",
            "Matched calendar months, March–August",
        ),
    )
}


@dataclass(frozen=True)
class AtlasElementSpec:
    element_id: str
    label: str
    dataset_key: str
    indicator: str
    study_id: str
    study_name: str
    endpoint: str


ATLAS_ELEMENTS: List[AtlasElementSpec] = [
    AtlasElementSpec(
        element_id=FIRE_ELEMENT_ID,
        label="Fire",
        dataset_key="fire_ukraine",
        indicator=FIRE_INDICATOR,
        study_id=FIRE_STUDY_ID,
        study_name=FIRE_STUDY_NAME,
        endpoint=FIRE_STUDY_ENDPOINT,
    ),
    AtlasElementSpec(
        element_id=LAND_ELEMENT_ID,
        label="Earth",
        dataset_key="land_ukraine",
        indicator=LAND_INDICATOR,
        study_id=LAND_STUDY_ID,
        study_name=LAND_STUDY_NAME,
        endpoint=LAND_STUDY_ENDPOINT,
    ),
    AtlasElementSpec(
        element_id=WATER_ELEMENT_ID,
        label="Water",
        dataset_key="water_ukraine",
        indicator=WATER_INDICATOR,
        study_id=WATER_STUDY_ID,
        study_name=WATER_STUDY_NAME,
        endpoint=WATER_STUDY_ENDPOINT,
    ),
]
