import type { ReactNode } from 'react'
import type { ElementId } from '../../explorer/elements'

/**
 * The shared selection. The atlas shell owns it; every part of the screen
 * (map layer, controls, evidence widget, guide) is derived from it.
 * Ids are opaque strings that only the active layer interprets.
 */
export interface AtlasSelection {
  /** Selected time period, or null for the layer's whole-period view. */
  period: string | null
  /** Selected comparison / baseline / display mode, or null when the layer has none. */
  comparison: string | null
  /** Selected map feature, or null. */
  feature: string | null
}

export interface ControlOption {
  id: string
  label: string
  /** Small second line, e.g. "8/30 days". */
  detail?: string
  /** Quality warning in words. Shown with an icon, never by colour alone. */
  warning?: string
}

export interface ControlGroup {
  label: string
  options: ControlOption[]
}

/** A layer lists only the controls it supports. Absent groups are not rendered. */
export interface LayerControls {
  periods?: ControlGroup & { wholePeriodLabel?: string }
  comparisons?: ControlGroup
}

export interface LayerActions {
  selectPeriod: (id: string | null) => void
  selectComparison: (id: string) => void
  selectFeature: (id: string | null) => void
}

/** Everything a layer contributes to the screen for one selection. */
export interface LayerPresentation {
  controls: LayerControls
  /** SVG content in atlas units. Positions must come from `projectLonLat`. */
  mapSvg: ReactNode
  /** HTML anchored over the map (labels). Positioned with `atlasPercent`. */
  mapHtml?: ReactNode
  /** Fixed visual key for the map encoding. The shell shows it at the top of the evidence widget. */
  mapKey: ReactNode
  /** Evidence widget body: summary, plots, sources and quality notices. */
  evidence: ReactNode
  /** Guide text for the current period, comparison and feature. */
  guide: string
}

/**
 * One element's evidence layer. Dataset-specific interpretation lives here, in
 * the layer's adapter. The shell only manages selection and layout.
 */
export interface EvidenceLayer<Data = unknown> {
  id: ElementId
  /** Heading of the evidence widget. */
  title: string
  loadingText: string
  defaultSelection: AtlasSelection
  /** Fetch the layer's data from the endpoint the catalog names. No science here. */
  load: (endpoint: string, signal: AbortSignal) => Promise<Data>
  present: (data: Data, selection: AtlasSelection, actions: LayerActions) => LayerPresentation
}
