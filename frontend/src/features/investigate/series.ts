import { getJson } from '../../api/client'
import type { StudyPackage } from '../../api/types'
import type { VariableEntry } from './catalog'

/** The two analysis periods. Only periods with a reviewed result are offered. */
export const WINDOWS = [
  { id: 'full_record', label: 'Full record' },
  { id: 'pre_invasion', label: 'Before the invasion' },
] as const
export type WindowId = (typeof WINDOWS)[number]['id']

/** One trend verdict, as the analysis pipeline writes it (docs/trend-results-schema.md). */
export interface TrendResult {
  region_id: string
  metric_id: string
  window_id: WindowId
  status: 'assessed' | 'insufficient_evidence' | 'not_assessed'
  start_month: string | null
  end_month: string | null
  n_months: number | null
  slope_per_year: number | null
  ci_low: number | null
  ci_high: number | null
  p_value: number | null
  /** p-value after correcting for the many tests run (Benjamini–Hochberg). */
  p_value_fdr?: number | null
  significant: boolean | null
  method: string | null
  caveats?: string[]
}

export interface TrendsPayload {
  status: 'available' | 'not_available'
  results: TrendResult[]
}

export async function fetchTrends(signal?: AbortSignal): Promise<TrendsPayload> {
  return getJson<TrendsPayload>('/api/trends', { signal })
}

export const trendKey = (regionId: string, metricId: string, windowId: string) => `${regionId}|${metricId}|${windowId}`

export function indexTrends(payload: TrendsPayload): Map<string, TrendResult> {
  const map = new Map<string, TrendResult>()
  for (const r of payload.results) map.set(trendKey(r.region_id, r.metric_id, r.window_id), r)
  return map
}

export interface SeriesPoint {
  month: string
  value: number | null
  /** Quality flag (under half the days observed). Drawn hollow. */
  low: boolean
  note?: string
}

/** Descriptive 2022 change for March–August. Not a significance test. */
export interface SeasonalChange {
  baselineLabel: string
  absDiff: number | null
  pct: number | null
  /** Why % is not shown (e.g. temperatures in °C). */
  pctWithheld: string | null
}

export interface VariableSeries {
  points: SeriesPoint[]
  seasonal: SeasonalChange | null
  /** Trend results carried by the variable's own payload (Kyiv NO₂). /api/trends takes precedence. */
  embeddedTrends: Partial<Record<WindowId, TrendResult>>
}

/** Which endpoint holds which variable. The catalog names the element; this names the file. */
export function endpointFor(variable: VariableEntry): string {
  if (variable.metric_id === 'no2_mean_molec_cm2') return '/api/air/kyiv'
  switch (variable.element_id) {
    case 'air':
      return '/api/air/weather'
    case 'fire':
      return '/api/fire/ukraine'
    case 'water':
      return '/api/water/ukraine'
    case 'land':
      return '/api/land/ukraine'
  }
}

export async function fetchPayload(endpoint: string, signal?: AbortSignal): Promise<unknown> {
  return getJson<unknown>(endpoint, { signal })
}

type Rec = Record<string, unknown>
const isRec = (v: unknown): v is Rec => typeof v === 'object' && v !== null && !Array.isArray(v)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const at = (v: unknown, ...path: string[]): unknown => path.reduce<unknown>((o, k) => (isRec(o) ? o[k] : undefined), v)

const FIRE_FILTERS: Record<string, string> = {
  fire_type0_per_1k_km2_day: 'type0_vegetation_nominal_high',
  fire_type2_per_1k_km2_day: 'type2_static_industrial',
}

/**
 * Reads one variable for one place out of its payload. Every number comes from the API;
 * nothing is computed here except unit-free bookkeeping. Returns null when the place has no data.
 */
export function readSeries(variable: VariableEntry, placeId: string, payload: unknown): VariableSeries | null {
  const id = variable.metric_id
  if (id === 'no2_mean_molec_cm2') return placeId === 'kyiv_no2_box' ? readNo2(payload as StudyPackage) : null

  if (id in FIRE_FILTERS) {
    const region = at(payload, 'result', 'regions', placeId)
    const filter = FIRE_FILTERS[id] as string
    const rows = at(region, 'monthly_series', filter)
    if (!Array.isArray(rows)) return null
    const points = rows.filter(isRec).map((r) => {
      const coverage = num(r.satellite_coverage_fraction)
      return {
        month: String(r.month),
        value: num(r.rate_per_1k_km2_obs_day),
        low: coverage !== null && coverage < 0.5,
        note: `${String(r.satellite_observed_days)}/${String(r.calendar_days)} days observed`,
      }
    })
    const cmp = at(region, 'seasonal_comparisons_mar_aug', filter, 'primary_metric', 'vs_2019_2021')
    return { points, seasonal: seasonalFrom(cmp, '2019–2021', variable), embeddedTrends: {} }
  }

  // Monthly regional series: weather, water and earth. Fire-weather lives beside the fire counts.
  const metric =
    variable.element_id === 'fire'
      ? at(payload, 'result', 'context_weather_regions', placeId, 'metrics', id)
      : at(payload, 'result', 'regions', placeId, 'metrics', id)
  const rows = at(metric, 'monthly_series')
  if (!Array.isArray(rows)) return null
  const points = rows.filter(isRec).map((r) => ({ month: String(r.month), value: num(r.value), low: false }))
  return { points, seasonal: seasonalFrom(at(metric, 'seasonal_mar_aug', 'vs_2015_2019'), '2015–2019', variable), embeddedTrends: {} }
}

function seasonalFrom(cmp: unknown, baselineLabel: string, variable: VariableEntry): SeasonalChange | null {
  if (!isRec(cmp)) return null
  const allowed = variable.uncertainty_and_status.pct_change_allowed && cmp.pct_change_status === 'computed'
  return {
    baselineLabel,
    absDiff: num(cmp.abs_diff),
    pct: allowed ? num(cmp.pct_change) : null,
    pctWithheld: allowed ? null : (variable.uncertainty_and_status.pct_change_withheld_reason ?? 'Percent change not reported for this variable.'),
  }
}

function readNo2(study: StudyPackage): VariableSeries {
  const r = study.result
  const points = r.monthly_series.map((m) => ({
    month: m.month,
    value: m.no2_mean_molec_cm2,
    low: m.flagged_below_50_pct,
    note: `${m.valid_days}/${m.calendar_days} days observed`,
  }))
  const cmp = r.comparisons.primary_2015_2019_valid_day
  const seasonal: SeasonalChange | null = cmp
    ? { baselineLabel: '2015–2019', absDiff: cmp.absolute_change_molec_cm2, pct: cmp.pct_change, pctWithheld: null }
    : null
  const embeddedTrends: VariableSeries['embeddedTrends'] = {}
  for (const w of ['full_record', 'pre_invasion'] as const) {
    const t = r.statistics.multi_year_seasonality_aware_trend[w]
    embeddedTrends[w] = {
      region_id: 'kyiv_no2_box',
      metric_id: 'no2_mean_molec_cm2',
      window_id: w,
      status: t.status === 'assessed' ? 'assessed' : 'not_assessed',
      start_month: t.start_month,
      end_month: t.end_month,
      n_months: t.n_months,
      slope_per_year: t.slope_molec_cm2_per_year,
      ci_low: t.ci_95_lower_molec_cm2_per_year,
      ci_high: t.ci_95_upper_molec_cm2_per_year,
      p_value: t.p_value,
      p_value_fdr: null,
      significant: t.significant_at_alpha_0_05,
      method: t.primary_method,
      caveats: t.assumptions_and_caveats,
    }
  }
  return { points, seasonal, embeddedTrends }
}
