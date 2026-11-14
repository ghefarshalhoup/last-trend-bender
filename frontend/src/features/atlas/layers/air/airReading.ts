import { BASELINES, DEFAULT_BASELINE, getSeasonalSummary, type BaselineOption, type SeasonalSummary } from '../../../../adapters/baselines'
import { formatDays, formatPercent, yearsRangeLabel } from '../../../../adapters/format'
import { buildMonthRows, type MonthRow } from '../../../../adapters/months'
import type { StudyPackage } from '../../../../api/types'
import type { AtlasSelection } from '../types'

export const KYIV_FEATURE = 'kyiv'

/** What the Air layer shows for one selection. Every number is read from the API result. */
export interface AirReading {
  option: BaselineOption
  summary: SeasonalSummary
  rows: MonthRow[]
  /** Selected month, or null for the whole March–August season. */
  row: MonthRow | null
  periodLabel: string
  baselineYears: string
  /** Percent change against the baseline. null = not available; never shown as zero. */
  pct: number | null
  pctText: string
  validDays: number
  calendarDays: number
  daysText: string
  lowCoverage: boolean
  featureSelected: boolean
}

export function readAir(study: StudyPackage, selection: AtlasSelection): AirReading {
  const option = BASELINES.find((b) => b.id === selection.comparison) ?? DEFAULT_BASELINE
  const summary = getSeasonalSummary(study.result, option)
  const rows = buildMonthRows(study.result.matched_months, option)
  const row = rows.find((r) => String(r.calendarMonth) === selection.period) ?? null
  const pct = row ? row.change.pct_change : summary.comparison.pct_change
  const validDays = row ? row.target.validDays : summary.comparison.target_valid_days
  const calendarDays = row ? row.target.calendarDays : summary.comparison.target_calendar_days
  return {
    option,
    summary,
    rows,
    row,
    periodLabel: `${row ? row.long : summary.monthsLabel} ${summary.targetYear}`,
    baselineYears: summary.baselineYears,
    pct,
    pctText: pct === null ? 'No comparison available' : formatPercent(pct),
    validDays,
    calendarDays,
    daysText: `${formatDays(validDays, calendarDays)} observed`,
    lowCoverage: row ? row.target.lowCoverage : false,
    featureSelected: selection.feature === KYIV_FEATURE,
  }
}

export function baselineLabel(study: StudyPackage, option: BaselineOption): string {
  return yearsRangeLabel(study.result.comparisons[option.id]?.baseline_years_requested ?? [])
}

/** Guide text for the current period, baseline and feature. Describes the observation and its limits. */
export function airGuide(reading: AirReading): string {
  if (reading.featureSelected) {
    return 'This box is the whole Kyiv study area, half a degree on each side. One number describes all of it, so it cannot show differences between neighbourhoods.'
  }
  if (reading.pct === null) {
    return `There is no comparison for ${reading.periodLabel} against ${reading.baselineYears}. A missing value is not a zero.`
  }
  const direction = reading.pct < 0 ? 'lower than' : reading.pct > 0 ? 'higher than' : 'the same as'
  const size = reading.pct === 0 ? '' : `${formatPercent(Math.abs(reading.pct)).replace('+', '')} `
  const finding = `${reading.periodLabel}: NO₂ over the Kyiv box was ${size}${direction} the same months in ${reading.baselineYears}.`
  const coverage = reading.lowCoverage
    ? ` The satellite saw the box on only ${reading.validDays} of ${reading.calendarDays} days, so read this month with caution.`
    : reading.row
      ? ''
      : ' April inside this season had low coverage.'
  return `${finding}${coverage} This shows a change, not its cause.`
}
