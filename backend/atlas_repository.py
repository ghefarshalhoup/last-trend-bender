"""Read-only strict JSON artifact loaders for four-element atlas datasets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from backend.atlas_schemas import (
    AtlasCatalogContract,
    FireCellsContract,
    FireStudyContract,
    PowerElementStudyContract,
)
from backend.config import Settings
from backend.repository import Problem


def _reject_nonfinite_constant(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant '{token}' is not allowed")


@dataclass(frozen=True)
class AtlasArtifact:
    dataset_key: str
    source_file: Path
    ready: bool
    raw: Optional[Dict[str, Any]] = None
    schema_version: Optional[str] = None
    loaded_at: Optional[str] = None
    problems: List[Problem] = field(default_factory=list)


@dataclass(frozen=True)
class AtlasStore:
    catalog: AtlasArtifact
    fire_ukraine: AtlasArtifact
    fire_ukraine_cells: AtlasArtifact
    water_ukraine: AtlasArtifact
    land_ukraine: AtlasArtifact
    air_weather: AtlasArtifact

    def all_artifacts(self) -> Dict[str, AtlasArtifact]:
        return {
            "atlas_catalog": self.catalog,
            "fire_ukraine": self.fire_ukraine,
            "fire_ukraine_cells": self.fire_ukraine_cells,
            "water_ukraine": self.water_ukraine,
            "land_ukraine": self.land_ukraine,
            "air_weather": self.air_weather,
        }


def load_atlas_artifact(
    path: Path,
    contract_cls: Type[BaseModel],
    dataset_key: str,
) -> AtlasArtifact:
    """Load and strictly validate a JSON atlas artifact without coercing types."""
    if not path.is_file():
        return AtlasArtifact(
            dataset_key=dataset_key,
            source_file=path,
            ready=False,
            problems=[
                Problem(
                    code="results_missing",
                    message=f"Artifact '{path.name}' not found at {path}.",
                )
            ],
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text, parse_constant=_reject_nonfinite_constant)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return AtlasArtifact(
            dataset_key=dataset_key,
            source_file=path,
            ready=False,
            problems=[
                Problem(
                    code="results_corrupt_json",
                    message=f"Could not parse JSON in '{path.name}': {exc}",
                )
            ],
        )

    if not isinstance(payload, dict):
        return AtlasArtifact(
            dataset_key=dataset_key,
            source_file=path,
            ready=False,
            problems=[
                Problem(
                    code="results_invalid",
                    message=f"Top-level JSON value in '{path.name}' must be an object.",
                )
            ],
        )

    try:
        contract_cls.model_validate(payload)
    except ValidationError as exc:
        return AtlasArtifact(
            dataset_key=dataset_key,
            source_file=path,
            ready=False,
            problems=[
                Problem(
                    code="results_invalid",
                    message=f"Contract validation failed for '{path.name}'.",
                    details=[
                        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
                        for err in exc.errors()[:25]
                    ],
                )
            ],
        )

    return AtlasArtifact(
        dataset_key=dataset_key,
        source_file=path,
        ready=True,
        raw=payload,
        schema_version=str(payload.get("schema_version")),
        loaded_at=datetime.now(timezone.utc).isoformat(),
        problems=[],
    )


def load_atlas_store(settings: Settings) -> AtlasStore:
    """Load all four-element atlas artifacts configured in ``settings``."""
    return AtlasStore(
        catalog=load_atlas_artifact(settings.atlas_catalog_results, AtlasCatalogContract, "atlas_catalog"),
        fire_ukraine=load_atlas_artifact(settings.fire_ukraine_results, FireStudyContract, "fire_ukraine"),
        fire_ukraine_cells=load_atlas_artifact(settings.fire_ukraine_cells, FireCellsContract, "fire_ukraine_cells"),
        water_ukraine=load_atlas_artifact(settings.water_ukraine_results, PowerElementStudyContract, "water_ukraine"),
        land_ukraine=load_atlas_artifact(settings.earth_ukraine_results, PowerElementStudyContract, "land_ukraine"),
        air_weather=load_atlas_artifact(settings.air_weather_results, PowerElementStudyContract, "air_weather"),
    )
