"""Runtime settings, read from environment variables.

Every path setting is resolved against the repository root when it is
relative, so the server behaves the same whichever directory it is
started from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

ENV_PREFIX = "WAR_TRACKER_"
ENV_REPORTS_DIR = f"{ENV_PREFIX}REPORTS_DIR"
ENV_AIR_RESULTS_FILE = f"{ENV_PREFIX}AIR_KYIV_RESULTS"
ENV_CORS_ORIGINS = f"{ENV_PREFIX}CORS_ORIGINS"

DEFAULT_REPORTS_DIR = "reports"
DEFAULT_AIR_RESULTS_FILE = "air_no2_results.json"
DEFAULT_CORS_ORIGINS: Tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def resolve_path(value: str | os.PathLike[str], base: Path) -> Path:
    """Return an absolute path; relative values are anchored at ``base``."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def parse_origins(raw: Optional[str]) -> Tuple[str, ...]:
    """Parse a comma-separated origin list; blank entries are ignored."""
    if raw is None:
        return DEFAULT_CORS_ORIGINS
    origins = tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())
    if "*" in origins and len(origins) > 1:
        raise ValueError(f"{ENV_CORS_ORIGINS}: '*' cannot be combined with explicit origins")
    return origins


@dataclass(frozen=True)
class Settings:
    """Backend configuration.

    ``reports_dir`` holds the chart PNGs. ``air_kyiv_results`` is the JSON
    result contract; a relative value is resolved inside ``reports_dir``.
    """

    reports_dir: Path = field(default_factory=lambda: REPO_ROOT / DEFAULT_REPORTS_DIR)
    air_kyiv_results: Path = field(
        default_factory=lambda: REPO_ROOT / DEFAULT_REPORTS_DIR / DEFAULT_AIR_RESULTS_FILE
    )
    cors_origins: Tuple[str, ...] = DEFAULT_CORS_ORIGINS

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        env = os.environ if env is None else env
        reports_dir = resolve_path(env.get(ENV_REPORTS_DIR, DEFAULT_REPORTS_DIR), REPO_ROOT)
        results = resolve_path(env.get(ENV_AIR_RESULTS_FILE, DEFAULT_AIR_RESULTS_FILE), reports_dir)
        return cls(
            reports_dir=reports_dir,
            air_kyiv_results=results,
            cors_origins=parse_origins(env.get(ENV_CORS_ORIGINS)),
        )
