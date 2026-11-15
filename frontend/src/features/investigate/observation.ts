/**
 * The avatar's one observation: built only from the focused card's own fields
 * (place, variable, period, test result, the descriptive 2022 comparison, coverage).
 * No relationships between cards, no causes. Each sentence maps to one field.
 */
import { placeLabel, type VariableEntry } from './catalog'
import { spanText, type SeriesState, type TrendResult, type WindowId } from './series'
import { displayUnit, fmt, readCard } from './verdict'

export interface ObservationInput {
  variable: VariableEntry
  placeId: string
  window: WindowId
  state: SeriesState
  trend: TrendResult | undefined
  /** Plain reason when the place has no record for this variable. */
  noDataReason: string
}

/** Months in the tested period that the satellite saw on fewer than half the days. */
export function coverageCount(state: SeriesState, window: WindowId): { low: number; total: number } {
  if (state.status !== 'ready' || !state.series) return { low: 0, total: 0 }
  const used = state.series.points.filter((p) => p.value !== null && (window === 'full_record' || p.month <= '2022-02'))
  return { low: used.filter((p) => p.low).length, total: used.length }
}

export function observe({ variable, placeId, window, state, trend, noDataReason }: ObservationInput): string {
  const place = placeLabel(placeId)
  const name = variable.short_label
  if (state.status === 'loading') return `Loading ${name} for ${place}…`
  if (state.status === 'error') return `${name} for ${place} did not load. Press “Try again” on the card.`
  if (!state.series) return noDataReason

  const series = state.series
  const reading = readCard(variable, series, trend)
  const span = spanText(series, window) ?? 'the available months'
  const parts: string[] = []

  if (reading.verdict === 'significant') {
    const way = reading.direction === 'down' ? 'fall' : 'rise'
    parts.push(`For ${place}, the long-term test of ${name} found a significant ${way} of ${reading.rateText} over ${span}.`)
  } else if (reading.verdict === 'not_significant') {
    parts.push(`For ${place}, the long-term test of ${name} did not detect a clear trend over ${span}.`)
  } else if (trend?.status === 'insufficient_evidence') {
    parts.push(`For ${place}, there is too little data for a reliable long-term test of ${name} (${span}).`)
  } else {
    parts.push(`For ${place}, no long-term test result is available yet for ${name}.`)
  }

  const s = series.seasonal
  if (s) {
    if (s.pct !== null && Math.abs(s.pct) >= 0.05) {
      parts.push(`Separately, March–August 2022 averaged ${Math.abs(s.pct).toFixed(0)}% ${s.pct < 0 ? 'below' : 'above'} the ${s.baselineLabel} average.`)
    } else if (s.absDiff !== null) {
      const { scale, unit } = displayUnit(variable)
      const diff = s.absDiff / scale
      const size = fmt(Math.abs(diff))
      parts.push(
        Number(size) === 0
          ? `Separately, March–August 2022 was about the same as in ${s.baselineLabel}.`
          : `Separately, March–August 2022 averaged ${size} ${unit} ${diff < 0 ? 'lower' : 'higher'} than in ${s.baselineLabel}.`,
      )
    }
  }

  const { low, total } = coverageCount(state, window)
  if (low > 0) parts.push(`${low} of ${total} months had limited satellite observations (hollow points).`)
  return parts.join(' ')
}
