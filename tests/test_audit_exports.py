"""Unit and offline regeneration tests for src.audit_exports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.audit_exports import (
    FROZEN_DIR,
    compute_kyiv_pet_sensitivities,
    regenerate_audit_summaries,
)


class AuditExportsTests(unittest.TestCase):
    def test_kyiv_pet_sensitivities_match_frozen_summary(self) -> None:
        frozen_native = json.loads((FROZEN_DIR / "nasa_power" / "native_grid_vs_3x3_summary.json").read_text(encoding="utf-8"))
        fresh = compute_kyiv_pet_sensitivities()
        for key, val in fresh.items():
            self.assertAlmostEqual(float(val), float(frozen_native[key]), places=5)

    def test_offline_regenerate_audit_summaries_matches_frozen_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            outs = regenerate_audit_summaries(out_dir=Path(tmpdir), fetch_upstream=False)

            fresh_mask = json.loads(outs["spatial_mask_audit"].read_text(encoding="utf-8"))
            frozen_mask = json.loads((FROZEN_DIR / "spatial_mask_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(set(fresh_mask.keys()), set(frozen_mask.keys()))
            for rid, f_entry in fresh_mask.items():
                c_entry = frozen_mask[rid]
                self.assertEqual(f_entry["lattice_points_inside_ukr_adm0"], c_entry["lattice_points_inside_ukr_adm0"])
                self.assertEqual(f_entry["firms_detections_in_box"], c_entry["firms_detections_in_box"])
                self.assertEqual(f_entry["firms_detections_inside_ukr_adm0"], c_entry["firms_detections_inside_ukr_adm0"])
                self.assertAlmostEqual(float(f_entry["pct_box_inside_ukr_adm0"]), float(c_entry["pct_box_inside_ukr_adm0"]), places=2)

            fresh_cmr = json.loads(outs["firms_cmr_matched_audit"].read_text(encoding="utf-8"))
            frozen_cmr = json.loads((FROZEN_DIR / "firms_cmr_matched_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(fresh_cmr["top_static_type2_cells"], frozen_cmr["top_static_type2_cells"])
            for rid, subsets in fresh_cmr["regional_matched_outage"].items():
                for sid, svals in subsets.items():
                    cvals = frozen_cmr["regional_matched_outage"][rid][sid]
                    self.assertEqual(svals["base_raw_count"], cvals["base_raw_count"])
                    self.assertEqual(svals["target_2022_raw_count"], cvals["target_2022_raw_count"])
                    for k in (
                        "pct_change_cmr_obs_days_box_area",
                        "pct_change_matched_dates_169d",
                        "rate_base_matched_ukr_land_per_1k_km2_day",
                        "rate_2022_matched_ukr_land_per_1k_km2_day",
                    ):
                        if cvals[k] is None:
                            self.assertIsNone(svals[k])
                        else:
                            self.assertAlmostEqual(float(svals[k]), float(cvals[k]), places=4)


if __name__ == "__main__":
    unittest.main()
