"""Shape validated data into API responses.

Nothing here computes science. The map geometry restates the contract's
bounding boxes as GeoJSON, and ``highlights`` only points to or copies
values that already exist in the contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.atlas_repository import AtlasStore
from backend.catalog import (
    AIR_ELEMENT_ID,
    AIR_INDICATOR,
    AIR_KYIV_CHARTS,
    AIR_STUDY_ENDPOINT,
    AIR_STUDY_ID,
    AIR_STUDY_NAME,
    ATLAS_ELEMENTS,
    CASE_ID,
    CASE_NAME,
    CONFLICT_START,
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


def build_cases(data: AirKyivData, atlas: Optional[AtlasStore] = None) -> Dict[str, Any]:
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

    artifacts = atlas.all_artifacts() if atlas is not None else {}
    other_elements: List[Dict[str, Any]] = []
    for spec in ATLAS_ELEMENTS:
        artifact = artifacts.get(spec.dataset_key)
        if artifact is not None and artifact.ready:
            other_elements.append(
                {
                    "element_id": spec.element_id,
                    "label": spec.label,
                    "status": "available",
                    "indicator": spec.indicator,
                    "reason": None,
                    "studies": [
                        {
                            "study_id": spec.study_id,
                            "name": spec.study_name,
                            "endpoint": spec.endpoint,
                        }
                    ],
                }
            )
        else:
            other_elements.append(
                {
                    "element_id": spec.element_id,
                    "label": spec.label,
                    "status": "unavailable",
                    "indicator": spec.indicator,
                    "reason": "data_not_ready",
                    "studies": [],
                }
            )

    return {
        "cases": [
            {"case_id": CASE_ID, "name": CASE_NAME, "conflict_start": CONFLICT_START, "elements": [air, *other_elements]}
        ]
    }


def filter_fire_cells(
    raw: Dict[str, Any],
    *,
    month: Optional[str] = None,
    year: Optional[int] = None,
    calendar_month: Optional[int] = None,
    region_id: Optional[str] = None,
    type_mode: str = "all",
    confidence_mode: str = "all",
    inside_ukr_only: bool = False,
) -> Dict[str, Any]:
    """Return a filtered view over validated monthly Fire 0.25 deg grid cells."""
    if not any([month, year is not None, calendar_month is not None, region_id, inside_ukr_only, type_mode != "all", confidence_mode != "all"]):
        return raw

    registry = raw["cell_registry"]
    if region_id is not None or inside_ukr_only:
        filtered_registry = [
            cell
            for cell in registry
            if (region_id is None or region_id in cell["region_ids"])
            and (not inside_ukr_only or cell["in_ukr_adm0"])
        ]
        allowed_ids = {cell["cell_id"] for cell in filtered_registry}
    else:
        filtered_registry = registry
        allowed_ids = None

    count_key = None
    if type_mode == "type0":
        count_key = "type0_nh_count" if confidence_mode == "nominal_high" else "type0_all_count"
    elif type_mode == "type2":
        count_key = "type2_nh_count" if confidence_mode == "nominal_high" else "type2_all_count"
    elif type_mode == "type3":
        count_key = "type3_all_count"

    filtered_rows = []
    for row in raw["monthly_cells"]:
        if month is not None and row["month"] != month:
            continue
        if year is not None and row["year"] != year:
            continue
        if calendar_month is not None and row["calendar_month"] != calendar_month:
            continue
        if allowed_ids is not None and row["cell_id"] not in allowed_ids:
            continue
        if count_key is not None:
            if row[count_key] <= 0:
                continue
        elif confidence_mode == "nominal_high":
            if (row["type0_nh_count"] + row["type2_nh_count"]) <= 0:
                continue
        filtered_rows.append(row)

    filtered_cov = [
        cov
        for cov in raw["cmr_month_coverage"]
        if (month is None or cov["month"] == month)
        and (year is None or cov["year"] == year)
        and (calendar_month is None or cov["calendar_month"] == calendar_month)
    ]

    return {
        "schema_version": raw["schema_version"],
        "case_id": raw["case_id"],
        "element_id": raw["element_id"],
        "study_id": raw["study_id"],
        "grid_step_deg": raw["grid_step_deg"],
        "season_window": raw["season_window"],
        "completeness_note": raw["completeness_note"],
        "applied_filters": {
            "month": month,
            "year": year,
            "calendar_month": calendar_month,
            "region_id": region_id,
            "type_mode": type_mode,
            "confidence_mode": confidence_mode,
            "inside_ukr_only": inside_ukr_only,
        },
        "cmr_month_coverage": filtered_cov,
        "cell_registry": filtered_registry,
        "monthly_cells": filtered_rows,
    }
