import { MINUS } from '../../adapters/format'
import type { VariableEntry } from './catalog'
import type { SeriesPoint, TrendResult, VariableSeries, WindowId } from './series'

export type Verdict = 'significant' | 'not_significant' | 'not_assessed'

/** Display scale per variable: NO₂ columns read as ×10¹⁵, everything else as served. */
export function displayUnit(v: VariableEntry): { scale: number; unit: string } {
  if (v.metric_id === 'no2_mean_molec_cm2') return { scale: 1e15, unit: '×10¹⁵ molecules/cm²' }
  return { scale: 1, unit: v.units.replace('^2', '²').replace('m^2', 'm²') }
}

/** Three significant digits, true minus sign, optional plus. */
export function fmt(value: number, signed = false): string {
  const abs = Math.abs(value)
  const digits = abs === 0 ? 0 : abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : Math.min(4, 2 - Math.floor(Math.log10(abs)))
  const text = abs.toFixed(digits)
  if (Number(text) === 0) return text
  return `${value < 0 ? MINUS : signed ? '+' : ''}${text}`
}

export function formatP(p: number): string {
  return p < 0.001 ? '< 0.001' : p.toFixed(p < 0.1 ? 3 : 2)
}

export interface CardReading {
  verdict: Verdict
  direction: 'up' | 'down' | 'flat' | null
  /** Short badge: "Significant rise", "No significant trend", "Not assessed". */
  badge: string
  /** One plain sentence. */
  sentence: string
  rateText: string | null
  intervalText: string | null
  pText: string | null
  pFdrText: string | null
  method: string | null
  nMonths: number | null
  caveats: string[]
  /** "2022 (Mar–Aug) vs 2015–2019: −28.0%", or null. */
  seasonalText: string | null
  /** Why the percent is not shown, when it is not. */
  seasonalNote: string | null
}

const yearsSpanned = (points: SeriesPoint[]) => new Set(points.filter((p) => p.value !== null).map((p) => p.month.slice(0, 4))).size

/** Reasons in words; never a number when there is no result. */
function notAssessedSentence(result: TrendResult | undefined, series: VariableSeries): string {
  // The analysis gives its own reason first (e.g. four fire seasons, or too many poorly observed months).
  if (result?.status === 'insufficient_evidence') return result.caveats?.[0] ?? 'Too little data for a reliable trend test.'
  const years = yearsSpanned(series.points)
  if (years < 5) return `Only ${years} years of data: too short for a trend test.`
  return 'The trend test has not been run for this place yet.'
}

export function readCard(variable: VariableEntry, series: VariableSeries, result: TrendResult | undefined): CardReading {
  const { scale, unit } = displayUnit(variable)
  const assessed = result?.status === 'assessed' && result.slope_per_year !== null && result.significant !== null
  const slope = assessed ? (result.slope_per_year as number) : null
  const direction = slope === null ? null : slope < 0 ? 'down' : slope > 0 ? 'up' : 'flat'
  const verdict: Verdict = !assessed ? 'not_assessed' : result.significant ? 'significant' : 'not_significant'
  const way = direction === 'down' ? 'downward' : direction === 'up' ? 'upward' : 'flat'

  const badge =
    verdict === 'not_assessed' ? (result?.status === 'insufficient_evidence' ? 'Too little data' : 'Not assessed') : verdict === 'significant' ? `Significant ${direction === 'down' ? 'fall' : 'rise'}` : 'No significant trend'
  const sentence =
    verdict === 'not_assessed'
      ? notAssessedSentence(result, series)
      : verdict === 'significant'
        ? `A statistically significant ${way} trend over this period.`
        : `The estimate points ${way}, but the trend is not statistically significant.`

  const s = series.seasonal
  let seasonalText: string | null = null
  if (s) {
    if (s.pct !== null) seasonalText = `${s.pct > 0 ? '+' : s.pct < 0 ? MINUS : ''}${Math.abs(s.pct).toFixed(1)}%`
    else if (s.absDiff !== null) seasonalText = `${fmt(s.absDiff / scale, true)} ${unit}`
  }

  return {
    verdict,
    direction,
    badge,
    sentence,
    rateText: slope === null ? null : `${fmt(slope / scale, true)} ${unit} per year`,
    intervalText:
      assessed && result.ci_low !== null && result.ci_high !== null ? `${fmt(result.ci_low / scale, true)} to ${fmt(result.ci_high / scale, true)}` : null,
    pText: assessed && result.p_value !== null ? formatP(result.p_value) : null,
    pFdrText: assessed && result.p_value_fdr != null ? formatP(result.p_value_fdr) : null,
    method: assessed ? result.method : null,
    nMonths: assessed ? result.n_months : null,
    caveats: result?.caveats ?? [],
    seasonalText: seasonalText === null || !s ? null : `${seasonalText} vs ${s.baselineLabel}`,
    seasonalNote: s && s.pct === null && s.absDiff !== null ? 'Shown as a difference, not a percent.' : null,
  }
}

/** /api/trends wins; the variable's own payload is the fallback (Kyiv NO₂ ships its own). */
export function pickTrend(fromApi: TrendResult | undefined, series: VariableSeries, window: WindowId): TrendResult | undefined {
  return fromApi ?? series.embeddedTrends[window]
}
