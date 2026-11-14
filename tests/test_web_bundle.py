"""Validation tests for src/build_web_bundle.py and static web/ deliverables."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from src.build_web_bundle import WEB_VARIABLES, build_web_bundle
from src.weather_power_pipeline import STUDY_BOXES

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
WEB_DIR = REPO_ROOT / "web"


def _reject_nonfinite(constant: str) -> None:
    raise ValueError(f"Non-standard JSON constant found: {constant}")


class WebBundleTests(unittest.TestCase):
    def test_committed_bundle_strict_finite_and_complete(self) -> None:
        bundle_path = WEB_DIR / "data" / "ukraine_4elements_bundle.json"
        self.assertTrue(bundle_path.is_file(), f"Missing {bundle_path}")
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)

        self.assertEqual(bundle["case_id"], "ukraine")
        self.assertEqual(bundle["conflict_start"], "2022-02-24")
        self.assertEqual(bundle["status"]["before_after_significance"], "not_assessed")
        self.assertEqual(bundle["status"]["causal_attribution"], "not_established")

        expected_region_ids = {b.region_id for b in STUDY_BOXES}
        self.assertEqual(set(bundle["regions"].keys()), expected_region_ids)

        expected_metric_ids = {v[1] for v in WEB_VARIABLES}
        self.assertEqual({v["metric_id"] for v in bundle["variable_catalog"]}, expected_metric_ids)
        self.assertTrue(all("is_interval_scale" in v for v in bundle["variable_catalog"]))
        kyiv_series = bundle["regions"]["kyiv_no2_box"]["series"]
        self.assertTrue(expected_metric_ids.issubset(set(kyiv_series.keys())))
        self.assertTrue(any(kyiv_series["no2_mean_molec_cm2"]["flags"]))
        self.assertTrue(any("orbit gap" in f for f in kyiv_series["fire_type0_per_1k_km2_day"]["flags"]))

    def test_build_web_bundle_writes_to_custom_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "bundle.json"
            bundle = build_web_bundle(reports_dir=REPORTS_DIR, out_path=out_path)
            self.assertTrue(out_path.is_file())
            reloaded = json.loads(out_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)
            self.assertEqual(len(reloaded["regions"]), len(bundle["regions"]))

    def test_static_web_assets_exist_and_have_required_hooks(self) -> None:
        html_path = WEB_DIR / "index.html"
        css_path = WEB_DIR / "app.css"
        js_path = WEB_DIR / "app.js"
        for p in (html_path, css_path, js_path):
            self.assertTrue(p.is_file(), f"Missing web asset {p}")
            self.assertGreater(p.stat().st_size, 1000)

        html = html_path.read_text(encoding="utf-8")
        for required_id in (
            "main-series-canvas",
            "weather-control-canvas",
            "fire-vpd-scatter",
            "regional-contrast-table",
            "stats-rigor-table",
            "case-ledger-dialog",
            'closedby="any"',
            'role="tablist"',
        ):
            self.assertIn(required_id, html)

        css = css_path.read_text(encoding="utf-8")
        self.assertIn("@container", css)
        self.assertIn("scrollbar-gutter", css)

        js = js_path.read_text(encoding="utf-8")
        self.assertIn("closedBy", js)
        self.assertIn("ukraine_4elements_bundle.json", js)

        # Verify every DOM ID queried via getElementById in app.js exists in index.html
        referenced_ids = set(re.findall(r'document\.getElementById\("([^"]+)"\)', js))
        self.assertTrue(len(referenced_ids) >= 20)
        for dom_id in sorted(referenced_ids):
            self.assertIn(f'id="{dom_id}"', html, f"app.js references missing HTML id '{dom_id}'")


if __name__ == "__main__":
    unittest.main()
