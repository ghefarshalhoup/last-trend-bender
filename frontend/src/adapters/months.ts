import type { MatchedMonth, MonthChange } from '../api/types'
import type { BaselineOption } from './baselines'
import { monthName } from './format'

/** The API reports columns in molecules/cm². Charts plot them in units of 10¹⁵. */
export const CHART_UNIT_SCALE = 1e15

export function scaleForChart(value: number | null): number | null {
  return value === null ? null : value / CHART_UNIT_SCALE
}

export interface MonthRow {
  calendarMonth: number
  short: string
  long: string
  target: {
    mean: number | null
    validDays: number
    calendarDays: number
    coverage: number
    lowCoverage: boolean
  }
  baseline: {
    mean: number | null
    min: number | null
    max: number | null
    sd: number | null
    meanCoverage: number | null
    flaggedYearsCount: number
    flaggedYearsDetail: string[]
    availableYears: number[]
    unavailableYears: number[]
  }
  change: MonthChange
}

/** Calendar-month rows for the chosen baseline. Null stays null. */
export function buildMonthRows(matched: MatchedMonth[], option: BaselineOption): MonthRow[] {
  return matched.map((month) => {
    const base = month[option.monthKey]
    return {
      calendarMonth: month.calendar_month,
      short: month.month_name,
      long: monthName(month.calendar_month),
      target: {
        mean: month.target_2022.mean_molec_cm2,
        validDays: month.target_2022.valid_days,
        calendarDays: month.target_2022.calendar_days,
        coverage: month.target_2022.coverage_fraction,
        lowCoverage: month.target_2022.flagged_below_50_pct,
      },
      baseline: {
        mean: base.mean_molec_cm2,
        min: base.min_molec_cm2,
        max: base.max_molec_cm2,
        sd: base.sd_molec_cm2,
        meanCoverage: base.mean_coverage_fraction,
        flaggedYearsCount: base.flagged_years_count,
        flaggedYearsDetail: base.flagged_years_detail,
        availableYears: base.available_years,
        unavailableYears: base.unavailable_years,
      },
      change: month[option.changeKey],
    }
  })
}

export interface ChartPoint {
  calendarMonth: number
  short: string
  /** Baseline mean, ×10¹⁵ molecules/cm². null when missing: the line breaks. */
  baseline: number | null
  /** Baseline min–max across the baseline years. This is variability, not a confidence interval. */
  band: [number, number] | null
  /** 2022 monthly mean, ×10¹⁵ molecules/cm². null when missing: the line breaks. */
  y2022: number | null
  lowCoverage2022: boolean
}

export function buildChartPoints(rows: MonthRow[]): ChartPoint[] {
  return rows.map((row) => {
    const low = scaleForChart(row.baseline.min)
    const high = scaleForChart(row.baseline.max)
    return {
      calendarMonth: row.calendarMonth,
      short: row.short,
      baseline: scaleForChart(row.baseline.mean),
      band: low !== null && high !== null ? [low, high] : null,
      y2022: scaleForChart(row.target.mean),
      lowCoverage2022: row.target.lowCoverage,
    }
  })
}
