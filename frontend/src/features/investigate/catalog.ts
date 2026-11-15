import { getJson } from '../../api/client'
import type { ElementId } from '../explorer/elements'

/** One of the 25 variables, as `/api/variables` describes it. */
export interface VariableEntry {
  metric_id: string
  element_id: ElementId
  label: string
  short_label: string
  units: string
  is_interval_scale: boolean
  display_order: number
  dates: { start: string; end: string; n_years_available: number }
  spatial_support: { ukraine_region_ids: string[]; external_weather_region_ids: string[] }
  method_id: string
  uncertainty_and_status: { pct_change_allowed: boolean; pct_change_withheld_reason: string | null }
  sources: string[]
  limitations: string[]
}

export interface PlaceFeature {
  type: 'Feature'
  geometry: { type: 'Polygon'; coordinates: number[][][] }
  properties: {
    region_id: string
    name: string
    role: string
    area_km2: number
    center: { lat: number; lon: number }
    is_ukraine_study_area: boolean
    description: string
  }
}

export interface VariableCatalog {
  conflict_start: string
  variables: VariableEntry[]
  variable_ids_by_element: Record<string, string[]>
  study_regions: { features: PlaceFeature[] }
}

export async function fetchVariableCatalog(signal?: AbortSignal): Promise<VariableCatalog> {
  return getJson<VariableCatalog>('/api/variables', { signal })
}

/** Short names for the study boxes. The box itself (and its true size) always comes from the API. */
export const PLACE_LABELS: Record<string, string> = {
  kyiv_no2_box: 'Kyiv city',
  kyiv_north_belt: 'North (Kyiv–Chernihiv)',
  donbas_kharkiv_east: 'East front (Donbas–Kharkiv)',
  south_steppe_belt: 'South (Kherson–Crimea edge)',
  central_interior_cand: 'Central interior',
  west_ukraine_cand: 'West Ukraine',
  poland_krakow: 'Kraków, Poland',
  czechia_prague: 'Prague, Czechia',
  kharkiv_city: 'Kharkiv city',
}
export const placeLabel = (id: string) => PLACE_LABELS[id] ?? id

/** Monthly NO₂ for the study boxes beyond Kyiv (`/api/air/no2`), plus places that only exist there. */
export interface No2Regional {
  status: 'available' | 'not_available'
  regions: Record<string, unknown>
  extra_places: PlaceFeature[]
}
export const NO_REGIONAL_NO2: No2Regional = { status: 'not_available', regions: {}, extra_places: [] }
export const NO2_METRIC = 'no2_mean_molec_cm2'

export async function fetchNo2Regional(signal?: AbortSignal): Promise<No2Regional> {
  return getJson<No2Regional>('/api/air/no2', { signal })
}

/** Temperature, sunlight and evaporation demand for the comparison cities (`/api/weather/comparison`). */
export interface ComparisonWeather {
  result: { context_weather_regions: Record<string, { metrics: Record<string, unknown> }> }
}
export const NO_COMPARISON_WEATHER: ComparisonWeather = { result: { context_weather_regions: {} } }

export async function fetchComparisonWeather(signal?: AbortSignal): Promise<ComparisonWeather> {
  return getJson<ComparisonWeather>('/api/weather/comparison', { signal })
}

/** Variable × place pairs that have data beyond the catalog, and the endpoint that serves each. */
export type ExtraSupport = ReadonlyMap<string, string>
export const supportKey = (metricId: string, placeId: string): string => `${metricId}|${placeId}`

export function extraSupport(no2: No2Regional, weather: ComparisonWeather): ExtraSupport {
  const out = new Map<string, string>()
  for (const place of Object.keys(no2.regions)) out.set(supportKey(NO2_METRIC, place), '/api/air/no2')
  for (const [place, region] of Object.entries(weather.result.context_weather_regions)) {
    for (const metric of Object.keys(region.metrics ?? {})) out.set(supportKey(metric, place), '/api/weather/comparison')
  }
  return out
}

/** Whether the variable has data for the place: the catalog's own support, or an extra file. */
export function hasDataFor(variable: VariableEntry, placeId: string, extra: ExtraSupport = new Map()): boolean {
  if (extra.has(supportKey(variable.metric_id, placeId))) return true
  const s = variable.spatial_support
  return s.ukraine_region_ids.includes(placeId) || s.external_weather_region_ids.includes(placeId)
}

export function variablesOf(catalog: VariableCatalog, element: ElementId): VariableEntry[] {
  const ids = catalog.variable_ids_by_element[element] ?? []
  return ids.map((id) => catalog.variables.find((v) => v.metric_id === id)).filter((v): v is VariableEntry => Boolean(v))
}

/** Approximate distance from each comparison city to Ukraine's nearest border. */
export const OUTSIDE_DISTANCE_KM: Record<string, number> = { poland_krakow: 200, czechia_prague: 600 }

/**
 * Why a place lacks a variable: every gap today is "not collected" (never downloaded), with how to get it.
 * Checked against the exports on 2026-11-15; see docs/data-availability.md.
 */
export function noDataReason(variable: VariableEntry, placeId: string): string {
  const place = placeLabel(placeId)
  if (variable.metric_id.startsWith('fire_type') && !UKRAINE_PLACES.has(placeId))
    return `Not collected: NASA FIRMS fire detections were downloaded for Ukraine only. Adding ${place} needs a FIRMS request for that area and a re-run of the fire pipeline.`
  if (placeId === 'kharkiv_city')
    return 'Not collected: only NO₂ was requested for the small Kharkiv city box. Adding this variable needs a NASA POWER request for the box; until then, the East front contains it.'
  if (variable.metric_id === NO2_METRIC)
    return `Not collected: NO₂ was not requested from NASA Giovanni for ${place}. Adding it needs one Giovanni area-average export (OMNO2d) for the box.`
  return `Not collected: ${variable.short_label} has no record for ${place}.`
}

const UKRAINE_PLACES = new Set(['donbas_kharkiv_east', 'south_steppe_belt', 'kyiv_north_belt', 'kyiv_no2_box', 'central_interior_cand', 'west_ukraine_cand', 'kharkiv_city'])
