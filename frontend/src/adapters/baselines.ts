import type { AirResult, Comparison } from '../api/types'
import { monthsRangeLabel, yearsRangeLabel } from './format'

/**
 * The two baselines the screen offers. `id` selects the exported seasonal
 * comparison; `monthKey` / `changeKey` select the matching fields in
 * `result.matched_months`. The numbers all come from the API.
 */
export interface BaselineOption {
  id: 'primary_2015_2019_valid_day' | 'sensitivity_2019_2021_valid_day'
  monthKey: 'primary_2015_2019' | 'sensitivity_2019_2021'
  changeKey: 'vs_primary_2015_2019' | 'vs_sensitivity_2019_2021'
  role: 'Primary' | 'Sensitivity'
}

export const BASELINES: readonly BaselineOption[] = [
  {
    id: 'primary_2015_2019_valid_day',
    monthKey: 'primary_2015_2019',
    changeKey: 'vs_primary_2015_2019',
    role: 'Primary',
  },
  {
    id: 'sensitivity_2019_2021_valid_day',
    monthKey: 'sensitivity_2019_2021',
    changeKey: 'vs_sensitivity_2019_2021',
    role: 'Sensitivity',
  },
]

export const DEFAULT_BASELINE: BaselineOption = BASELINES[0] as BaselineOption

export interface SeasonalSummary {
  option: BaselineOption
  comparison: Comparison
  /** Same baseline with the months that were under 50% coverage in 2022 left out. */
  excludingLowCoverage: Comparison | null
  /** Same baseline using only months with at least 50% coverage in every year. */
  strictCoverage: Comparison | null
  baselineYears: string
  monthsLabel: string
  targetYear: number
}

export function getSeasonalSummary(result: AirResult, option: BaselineOption): SeasonalSummary {
  const comparison = result.comparisons[option.id] as Comparison
  const sensitivity = result.coverage_sensitivity
  return {
    option,
    comparison,
    excludingLowCoverage: sensitivity.excluding_target_flagged_months?.[option.id] ?? null,
    strictCoverage: sensitivity.strict_all_years_unflagged?.[option.id] ?? null,
    baselineYears: yearsRangeLabel(comparison.baseline_years_requested),
    monthsLabel: monthsRangeLabel(comparison.months_included),
    targetYear: comparison.target_year,
  }
}
