import type { ElementEntry } from '../../api/types'

/**
 * Presentation config for the four elements, in display order.
 * `id` is the catalog's element_id. The catalog calls the fourth element
 * "land"; the story calls it Earth, so only the label is mapped here.
 * Availability always comes from the catalog, never from this file.
 */
export type ElementId = 'air' | 'fire' | 'land' | 'water'

interface Theme {
  id: ElementId
  label: string
  accent: string
  soft: string
}

const THEMES: readonly Theme[] = [
  { id: 'air', label: 'Air', accent: 'var(--element-air)', soft: 'var(--element-air-soft)' },
  { id: 'fire', label: 'Fire', accent: 'var(--element-fire)', soft: 'var(--element-fire-soft)' },
  { id: 'land', label: 'Earth', accent: 'var(--element-earth)', soft: 'var(--element-earth-soft)' },
  { id: 'water', label: 'Water', accent: 'var(--element-water)', soft: 'var(--element-water-soft)' },
]

export interface ElementView extends Theme {
  available: boolean
  /** Short visible text for elements that cannot be opened. */
  statusNote: string | null
}

const NOTE_BY_REASON: Record<string, string> = {
  not_yet_integrated: 'Coming later',
  data_not_ready: 'Data not ready',
}

/**
 * `supported` lists the elements this screen can actually show. The API may
 * already serve data for an element before the screen has a view for it; such
 * an element stays "Coming later" instead of opening an empty state.
 */
export function resolveElements(catalog: ElementEntry[], supported?: readonly string[]): ElementView[] {
  return THEMES.map((theme) => {
    const entry = catalog.find((e) => e.element_id === theme.id)
    const hasView = supported ? supported.includes(theme.id) : true
    const available = hasView && entry?.status === 'available' && (entry.studies?.length ?? 0) > 0
    return {
      ...theme,
      available,
      statusNote: available ? null : (entry?.reason && NOTE_BY_REASON[entry.reason]) || 'Coming later',
    }
  })
}
