"""Shape validated data into API responses.

Nothing here computes science. The map geometry restates the contract's
bounding boxes as GeoJSON, and ``highlights`` only points to or copies
values that already exist in the contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.catalog import (
    AIR_ELEMENT_ID,
    AIR_INDICATOR,
    AIR_KYIV_CHARTS,
    AIR_STUDY_ENDPOINT,
    AIR_STUDY_ID,
    AIR_STUDY_NAME,
    CASE_ID,
    CASE_NAME,
    CONFLICT_START,
    PENDING_ELEMENTS,
    PENDING_REASON,
)
from backend.repository import AirKyivData

HEADLINE_COMPARISON_ID = "primary_2015_2019_valid_day"

MAP_NOTE = (
    "The polygon is the study window used for the area average. It is not a "
    "pollution heatmap: each NO₂ value describes the whole box, not places inside it."
)


def _bbox_feature(bbox: Dict[str, float], properties: Dict[str, Any]) -> Dict[str, Any]:
    west, south, east, north = bbox["west"], bbox["south"], bbox["east"], bbox["north"]
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": properties}


def build_map(raw: Dict[str, Any]) -> Dict[str, Any]:
    region = raw["region"]
    user_box = region["user_bounding_box"]
    return {
        "center": {"lat": region["center"]["lat"], "lon": region["center"]["lon"]},
        "bounds": [[user_box["south"], user_box["west"]], [user_box["north"], user_box["east"]]],
        "study_boundary": _bbox_feature(
            user_box,
            {
                "kind": "study_boundary",
                "region_id": region["region_id"],
                "name": region["name"],
                "source": "region.user_bounding_box",
            },
        ),
        "sampled_grid_center_extent": _bbox_feature(
            region["data_bounding_box"],
            {
                "kind": "sampled_grid_center_extent",
                "source": "region.data_bounding_box",
                "note": region["spatial_note"],
            },
        ),
        "rendering": "boundary_only",
        "note": MAP_NOTE,
    }


def build_chart_links(data: AirKyivData) -> List[Dict[str, Any]]:
    """Link only charts that passed the load checks.

    A chart missing from the contract, pointing at the wrong file, or absent
    on disk is omitted here; ``/api/health`` reports it and the chart route
    answers 503. The study itself stays available.
    """
    raw = data.raw
    assert raw is not None
    return [
        {
            "chart_id": spec.chart_id,
            "title": spec.title,
            "url": f"{AIR_STUDY_ENDPOINT}/charts/{spec.chart_id}",
            "media_type": "image/png",
            "contract": raw["charts"][spec.chart_id],
        }
        for spec in AIR_KYIV_CHARTS.values()
        if data.chart_ready.get(spec.chart_id, False)
    ]


def _notices(raw: Dict[str, Any]) -> List[str]:
    status = raw["status"]
    notices: List[str] = []
    if status["before_after_significance"] != "assessed":
        notices.append(
            f"Before/after significance not assessed (status: {status['before_after_significance']})."
        )
    if status["causal_attribution"] != "established":
        notices.append(f"Causal attribution to the war: {status['causal_attribution']}.")
    if status["reference_region_comparison"] != "assessed":
        notices.append(f"Reference-region comparison: {status['reference_region_comparison']}.")
    return notices


def build_highlights(raw: Dict[str, Any]) -> Dict[str, Any]:
    comparisons = raw["comparisons"]
    headline = comparisons[HEADLINE_COMPARISON_ID]
    trends = raw["statistics"]["multi_year_seasonality_aware_trend"]
    return {
        "claim_status": dict(raw["status"]),
        "notices": _notices(raw),
        "seasonal_differences": {
            "description": (
                "Descriptive March–August differences between 2022 and baseline seasons. "
                "Not a trend, and not tested for significance."
            ),
            "significance_status": raw["statistics"]["before_after_seasonal_inference"]["status"],
            "headline_comparison_id": HEADLINE_COMPARISON_ID,
            "comparison_ids": list(comparisons.keys()),
            "coverage_sensitivity_ids": {
                group: list(entries.keys()) for group, entries in raw["coverage_sensitivity"].items()
            },
            "source": "result.comparisons, result.coverage_sensitivity, result.matched_months",
        },
        "multi_year_trend": {
            "description": (
                "Seasonality-aware linear trend across the monthly record. "
                "Answers a different question from the seasonal differences."
            ),
            "window_ids": list(trends.keys()),
            "source": "result.statistics.multi_year_seasonality_aware_trend",
        },
        "coverage_warnings": [dict(item) for item in headline["flagged_months_in_target"]],
    }


def build_air_study(data: AirKyivData) -> Dict[str, Any]:
    raw = data.raw
    assert raw is not None
    return {
        "case_id": CASE_ID,
        "element_id": AIR_ELEMENT_ID,
        "study_id": AIR_STUDY_ID,
        "schema_version": raw["schema_version"],
        "map": build_map(raw),
        "charts": build_chart_links(data),
        "highlights": build_highlights(raw),
        "result": raw,
    }


def build_cases(data: AirKyivData) -> Dict[str, Any]:
    if data.results_ready:
        air = {
            "element_id": AIR_ELEMENT_ID,
            "label": "Air",
            "status": "available",
            "indicator": AIR_INDICATOR,
            "reason": None,
            "studies": [{"study_id": AIR_STUDY_ID, "name": AIR_STUDY_NAME, "endpoint": AIR_STUDY_ENDPOINT}],
        }
    else:
        air = {
            "element_id": AIR_ELEMENT_ID,
            "label": "Air",
            "status": "unavailable",
            "indicator": AIR_INDICATOR,
            "reason": "data_not_ready",
            "studies": [],
        }
    pending = [
        {**element, "status": "unavailable", "indicator": None, "reason": PENDING_REASON, "studies": []}
        for element in PENDING_ELEMENTS
    ]
    return {
        "cases": [
            {"case_id": CASE_ID, "name": CASE_NAME, "conflict_start": CONFLICT_START, "elements": [air, *pending]}
        ]
    }
