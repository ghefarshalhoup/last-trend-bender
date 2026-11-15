# Trend results: the one file the atlas cards read

**For Husam.** Write `reports/trend_results.json`. The backend serves it unchanged at `/api/trends`; every card in the atlas looks up its verdict there by `region_id` + `metric_id` + `window_id`. No file, or no row for a combination → the card says **"Not assessed"** and shows no rate. Kyiv NO₂ already carries its own result in `air_no2_results.json`; a row here for it overrides that.

```json
{
  "schema_version": "1.0.0",
  "generated_at_utc": "2026-11-15T10:00:00Z",
  "alpha": 0.05,
  "multiple_testing": "Benjamini-Hochberg across all rows with status=assessed",
  "results": [
    {
      "region_id": "donbas_kharkiv_east",
      "metric_id": "t2m",
      "window_id": "full_record",
      "status": "assessed",
      "start_month": "2015-01",
      "end_month": "2022-12",
      "n_months": 96,
      "slope_per_year": 0.051,
      "ci_low": -0.012,
      "ci_high": 0.114,
      "p_value": 0.11,
      "p_value_fdr": 0.34,
      "significant": false,
      "method": "Month-fixed-effects OLS with Newey-West HAC standard errors",
      "caveats": ["Regional box average; not a local measurement."]
    }
  ]
}
```

| Field | Rule |
| --- | --- |
| `region_id` | One of the 8 study boxes in `/api/variables` → `study_regions` |
| `metric_id` | One of the 25 ids in `/api/variables` |
| `window_id` | `full_record` (whole series) or `pre_invasion` (series up to 2022-02) |
| `status` | `assessed`, `insufficient_evidence` (e.g. Fire: 4 seasons) or `not_assessed` |
| `slope_per_year`, `ci_low`, `ci_high` | In the variable's **own units** per year (NO₂ in molecules/cm²; the UI rescales) |
| `p_value` | Raw p of the primary test |
| `p_value_fdr` | BH-adjusted p (optional but strongly wanted: ~200 tests) |
| `significant` | The verdict the UI shows. Decide it on `p_value_fdr` if present and say so in `multiple_testing` |
| `caveats` | Short plain sentences; the card shows up to five |

For `insufficient_evidence` / `not_assessed` rows, set the numbers to `null`. Check the file with `curl localhost:8000/api/trends`.

## How the file is produced

`python -m src.trend_results` writes it, together with `reports/no2_regional/` and `reports/atlas_no2_regional.json`, from committed inputs. The choices behind it are recorded in [decisions.md](decisions.md).

- **Test:** the Kyiv NO₂ trend function, applied unchanged to every monthly series, for the full record and for months up to 2022-02.
- **Multiple testing:** Benjamini-Hochberg within each variable (its places × periods); `significant` means `p_value_fdr < 0.05`. `fdr_family_size` records the family.
- **Fire:** `insufficient_evidence` (four comparable seasons).
- **NO₂ coverage rule:** the trend uses every month with a mean. It is only called significant if it is confirmed on months with at least 50% daily coverage: all year where possible, otherwise April–September. `coverage_sensitivity` records which check was used and its numbers.
- **Extra fields** (ignored by the cards today): `theil_sen_slope_per_year`, `p_value_hamed_rao`, `coverage_sensitivity`, `fdr_family_size`, `unconfirmed_estimate`.
- **Kharkiv city** is NO₂-only and enters the atlas through `extra_places` in `reports/atlas_no2_regional.json` (`/api/air/no2`).

Regional raw exports live in `data/frozen/no2_regional/` (untouched Giovanni CSVs).
