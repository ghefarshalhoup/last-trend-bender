import { formatDays, MINUS } from '../../../../adapters/format'
import { CHART_UNIT_SCALE } from '../../../../adapters/months'
import type { StudyPackage, TrendWindow } from '../../../../api/types'
import { dateToDecimalYear, monthToDecimalYear, type RateLine, type TimelinePoint } from '../../TrendChart'
import type { AtlasSelection } from '../types'

/** The two analysis periods with a reviewed trend result. Ids match the API's keys. */
export const TREND_WINDOWS = [
  { id: 'full_record', label: 'Full record' },
  { id: 'pre_invasion', label: 'Before the invasion' },
] as const
export type TrendWindowId = (typeof TREND_WINDOWS)[number]['id']
export const DEFAULT_WINDOW: TrendWindowId = 'full_record'

/** Kyiv's conflict start date is fixed by the study; the API carries it per case. */
export const INVASION_DATE = '2022-02-24'

export type Verdict = 'significant' | 'not_significant' | 'not_assessed'

export interface AirTrendReading {
  windowId: TrendWindowId
  windowLabel: string
  /** "March 2015 – August 2022" */
  rangeLabel: string
  window: TrendWindow
  verdict: Verdict
  direction: 'down' | 'up' | 'flat' | null
  /** The one-sentence verdict. */
  verdictText: string
  /** Short form for the map label. */
  verdictShort: string
  /** "−0.042 × 10¹⁵ molecules/cm² per year", or null when not assessed. */
  rateText: string | null
  /** "−0.095 to +0.012", or null. */
  intervalText: string | null
  pValueText: string | null
  mannKendallPText: string | null
  points: TimelinePoint[]
  /** Dashed line for the estimated rate. Drawn through the period's average, for illustration only. */
  rateLine: RateLine | null
  invasionT: number
  /** Set for "before the invasion": later months are outside the analysis. */
  analysisEndT: number | undefined
  featureSelected: boolean
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const longMonth = (ym: string) => `${MONTH_NAMES[Number(ym.slice(5, 7)) - 1] ?? ''} ${ym.slice(0, 4)}`

/** A value in molecules/cm² as a signed number in units of 10¹⁵, three decimals. */
export function signedScaled(value: number): string {
  const scaled = value / CHART_UNIT_SCALE
  const text = Math.abs(scaled).toFixed(3)
  if (Number(text) === 0) return text
  return `${scaled < 0 ? MINUS : '+'}${text}`
}

export function formatP(p: number): string {
  return p < 0.001 ? '< 0.001' : p.toFixed(p < 0.1 ? 3 : 2)
}

export function readAirTrend(study: StudyPackage, selection: AtlasSelection): AirTrendReading {
  const windowId: TrendWindowId = selection.window === 'pre_invasion' ? 'pre_invasion' : DEFAULT_WINDOW
  const window = study.result.statistics.multi_year_seasonality_aware_trend[windowId]
  const slope = window.slope_molec_cm2_per_year
  const assessed = window.status === 'assessed' && slope !== null && window.significant_at_alpha_0_05 !== null
  const verdict: Verdict = !assessed ? 'not_assessed' : window.significant_at_alpha_0_05 ? 'significant' : 'not_significant'
  const direction = slope === null ? null : slope < 0 ? 'down' : slope > 0 ? 'up' : 'flat'
  const way = direction === 'down' ? 'downward' : direction === 'up' ? 'upward' : 'neither up nor down'

  const verdictText =
    verdict === 'not_assessed'
      ? 'No trend result is available for this period.'
      : verdict === 'significant'
        ? `NO₂ shows a statistically significant ${way} trend over this period.`
        : `The estimate points ${way}, but the trend is not statistically significant.`
  const verdictShort = verdict === 'not_assessed' ? 'Trend not assessed' : verdict === 'significant' ? `Significant ${way} trend` : 'No significant trend'

  const points: TimelinePoint[] = study.result.monthly_series.map((m) => ({
    month: m.month,
    t: monthToDecimalYear(m.month),
    value: m.no2_mean_molec_cm2 === null ? null : m.no2_mean_molec_cm2 / CHART_UNIT_SCALE,
    low: m.flagged_below_50_pct,
    note: `${formatDays(m.valid_days, m.calendar_days)} observed`,
  }))

  const t0 = monthToDecimalYear(window.start_month)
  const t1 = monthToDecimalYear(window.end_month)
  const inWindow = points.filter((p) => p.value !== null && p.t >= t0 - 1e-9 && p.t <= t1 + 1e-9)
  let rateLine: RateLine | null = null
  if (assessed && slope !== null && inWindow.length > 1) {
    // Anchor: the average month and average value of the period. The slope itself comes from the API.
    const meanT = inWindow.reduce((sum, p) => sum + p.t, 0) / inWindow.length
    const meanY = inWindow.reduce((sum, p) => sum + (p.value as number), 0) / inWindow.length
    const perYear = slope / CHART_UNIT_SCALE
    rateLine = { t0, t1, y0: meanY + perYear * (t0 - meanT), y1: meanY + perYear * (t1 - meanT) }
  }

  const lower = window.ci_95_lower_molec_cm2_per_year
  const upper = window.ci_95_upper_molec_cm2_per_year
  const mk = assessed ? (window.nonparametric_sensitivity?.hamed_rao_mk?.p_value_hamed_rao ?? null) : null
  return {
    windowId,
    windowLabel: TREND_WINDOWS.find((w) => w.id === windowId)?.label ?? windowId,
    rangeLabel: `${longMonth(window.start_month)} – ${longMonth(window.end_month)}`,
    window,
    verdict,
    direction,
    verdictText,
    verdictShort,
    rateText: !assessed || slope === null ? null : `${signedScaled(slope)} × 10¹⁵ molecules/cm² per year`,
    intervalText: !assessed || lower === null || upper === null ? null : `${signedScaled(lower)} to ${signedScaled(upper)}`,
    pValueText: !assessed || window.p_value === null ? null : formatP(window.p_value),
    mannKendallPText: mk === null ? null : formatP(mk),
    points,
    rateLine,
    invasionT: dateToDecimalYear(INVASION_DATE),
    analysisEndT: windowId === 'pre_invasion' ? t1 + 1 / 24 : undefined,
    featureSelected: selection.feature === 'kyiv',
  }
}

/** Guide text for the trend question. States the result and how far it can be trusted. */
export function airTrendGuide(reading: AirTrendReading): string {
  if (reading.featureSelected) {
    return 'This box is the whole Kyiv study area, half a degree on each side. One number describes all of it, so it cannot show differences between neighbourhoods.'
  }
  if (reading.verdict === 'not_assessed') return 'No trend result exists for this period, so there is no verdict to give.'
  const period = reading.windowId === 'pre_invasion' ? 'Before the invasion' : 'Across the full record'
  if (reading.verdict === 'significant') {
    return `${period}, NO₂ over Kyiv shows a statistically significant trend (p = ${reading.pValueText}). A trend describes the whole period; it does not say what caused it.`
  }
  const tail =
    reading.windowId === 'pre_invasion'
      ? 'Keep that in mind when you open the 2022 comparison.'
      : 'A sharp drop in one season and a weak eight-year trend can both be true.'
  return `${period}, the estimate points ${reading.direction === 'up' ? 'upward' : 'downward'}, but the uncertainty is too wide to call it a trend (p = ${reading.pValueText}). ${tail}`
}
