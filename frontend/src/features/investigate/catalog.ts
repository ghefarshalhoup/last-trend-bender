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
}
export const placeLabel = (id: string) => PLACE_LABELS[id] ?? id

/** Whether the variable has data for the place. */
export function hasDataFor(variable: VariableEntry, placeId: string): boolean {
  const s = variable.spatial_support
  return s.ukraine_region_ids.includes(placeId) || s.external_weather_region_ids.includes(placeId)
}

export function variablesOf(catalog: VariableCatalog, element: ElementId): VariableEntry[] {
  const ids = catalog.variable_ids_by_element[element] ?? []
  return ids.map((id) => catalog.variables.find((v) => v.metric_id === id)).filter((v): v is VariableEntry => Boolean(v))
}
