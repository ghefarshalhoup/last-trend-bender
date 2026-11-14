import type { ElementId } from '../../explorer/elements'
import { airLayer } from './air/airLayer'
import type { EvidenceLayer } from './types'

/**
 * Registered evidence layers, one per element. To add Fire: write
 * `layers/fire/fireLayer.tsx` implementing `EvidenceLayer` and add it here.
 * The shell, the base map and the widget layout need no changes.
 * See docs/illustrated-atlas-poc.md.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const LAYERS: Partial<Record<ElementId, EvidenceLayer<any>>> = {
  air: airLayer,
}
