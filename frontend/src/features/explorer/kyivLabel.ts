import type { SeasonalSummary } from '../../adapters/baselines'
import { formatPercent } from '../../adapters/format'
import type { MonthRow } from '../../adapters/months'

/**
 * The result line attached to the Kyiv study box. With no month chosen it is
 * the seasonal headline (labelled March–August); with a month it is that month,
 * labelled as such, so a month never reads as the seasonal result.
 */
export function kyivResultLabel(summary: SeasonalSummary, month: MonthRow | null): string {
  if (month) {
    const pct = month.change.pct_change === null ? 'change unavailable' : formatPercent(month.change.pct_change)
    const low = month.target.lowCoverage ? ' ▲' : ''
    return `${month.long} 2022: ${pct} · ${month.target.validDays}/${month.target.calendarDays} days${low}`
  }
  const pct = summary.comparison.pct_change === null ? 'change unavailable' : formatPercent(summary.comparison.pct_change)
  return `${summary.monthsLabel} ${summary.targetYear}: ${pct}`
}
