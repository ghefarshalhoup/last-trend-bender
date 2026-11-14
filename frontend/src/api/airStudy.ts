import { ApiError, getJson } from './client'
import type { CaseEntry, CasesResponse, ElementEntry, StudyPackage } from './types'

const AIR_ELEMENT_ID = 'air'
const CASE_ID = 'ukraine'

export interface AirStudyBundle {
  caseEntry: CaseEntry
  /** Every element of the case, in catalog order, so the UI can show what is unavailable. */
  elements: ElementEntry[]
  study: StudyPackage
}

export async function fetchAirStudy(signal?: AbortSignal): Promise<AirStudyBundle> {
  const catalog = await getJson<CasesResponse>('/api/cases', { signal })
  const caseEntry = catalog.cases?.find((entry) => entry.case_id === CASE_ID)
  if (!caseEntry) {
    throw new ApiError('unavailable', 'The case catalog does not include Ukraine.', { code: 'case_not_found' })
  }

  const air = caseEntry.elements.find((element) => element.element_id === AIR_ELEMENT_ID)
  const study = air?.studies?.[0]
  if (!air || air.status !== 'available' || !study) {
    throw new ApiError('unavailable', 'Air data for Ukraine is not ready yet.', {
      code: air?.reason ?? 'element_unavailable',
    })
  }

  const payload = await getJson<unknown>(study.endpoint, { signal })
  return { caseEntry, elements: caseEntry.elements, study: parseStudyPackage(payload) }
}

// ---------------------------------------------------------------------------
// A light shape check. It is not a second validator (the backend already
// validates the contract strictly); it makes contract drift fail with a clear
// message here instead of an undefined-property crash deep in a component.
// ---------------------------------------------------------------------------

const REQUIRED_COMPARISONS = ['primary_2015_2019_valid_day', 'sensitivity_2019_2021_valid_day']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function fail(path: string): never {
  throw new ApiError('schema', `The study response is missing or malformed at "${path}".`, { code: 'schema_mismatch', details: path })
}

export function parseStudyPackage(payload: unknown): StudyPackage {
  if (!isRecord(payload)) fail('(root)')
  const { map, charts, highlights, result } = payload
  if (!isRecord(map)) fail('map')
  if (!Array.isArray(map.bounds) || map.bounds.length !== 2) fail('map.bounds')
  if (!isRecord(map.study_boundary) || !isRecord(map.study_boundary.geometry)) fail('map.study_boundary.geometry')
  if (!isRecord(map.center) || typeof map.center.lat !== 'number') fail('map.center')
  if (typeof map.note !== 'string') fail('map.note')
  if (!Array.isArray(charts)) fail('charts')
  if (!isRecord(highlights)) fail('highlights')
  if (!Array.isArray(highlights.notices)) fail('highlights.notices')
  if (!Array.isArray(highlights.coverage_warnings)) fail('highlights.coverage_warnings')
  if (!isRecord(highlights.claim_status)) fail('highlights.claim_status')
  if (!isRecord(result)) fail('result')
  if (!isRecord(result.comparisons)) fail('result.comparisons')
  for (const id of REQUIRED_COMPARISONS) {
    if (!isRecord(result.comparisons[id])) fail(`result.comparisons.${id}`)
  }
  if (!Array.isArray(result.matched_months) || result.matched_months.length === 0) fail('result.matched_months')
  if (!Array.isArray(result.limitations)) fail('result.limitations')
  if (!isRecord(result.statistics)) fail('result.statistics')
  if (!isRecord(result.statistics.before_after_seasonal_inference)) fail('result.statistics.before_after_seasonal_inference')
  if (!isRecord(result.statistics.multi_year_seasonality_aware_trend)) fail('result.statistics.multi_year_seasonality_aware_trend')
  if (!isRecord(result.coverage_sensitivity)) fail('result.coverage_sensitivity')
  return payload as unknown as StudyPackage
}
