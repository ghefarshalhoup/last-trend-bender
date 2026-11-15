import type { CatalogBundle } from '../api/airStudy'
import type { CasesResponse, StudyPackage } from '../api/types'
import casesJson from './fixtures/cases.json'
import studyJson from './fixtures/air-kyiv.json'

// Snapshot of real backend responses, used ONLY by tests. The app itself never imports them.
export const casesFixture = casesJson as unknown as CasesResponse
export const studyFixture = studyJson as unknown as StudyPackage

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function makeStudy(mutate?: (study: StudyPackage) => void): StudyPackage {
  const study = clone(studyFixture)
  mutate?.(study)
  return study
}

export function makeCatalog(): CatalogBundle {
  const caseEntry = clone(casesFixture).cases[0]!
  return { caseEntry, elements: caseEntry.elements }
}
