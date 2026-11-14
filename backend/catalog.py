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


# Elements that exist in the product but have no integrated data yet.
# Confirm labels with G before the frontend relies on them.
PENDING_ELEMENTS: List[Dict[str, str]] = [
    {"element_id": "fire", "label": "Fire"},
    {"element_id": "land", "label": "Land"},
    {"element_id": "water", "label": "Water"},
]

PENDING_REASON = "not_yet_integrated"
