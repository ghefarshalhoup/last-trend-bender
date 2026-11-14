import type { ReactNode } from 'react'
import type { ElementId } from '../../explorer/elements'

/**
 * The shared selection. The atlas shell owns it; every part of the screen
 * (map layer, controls, evidence widget, guide) is derived from it.
 * Ids are opaque strings that only the active layer interprets.
 */
export interface AtlasSelection {
  /** Which question is being asked of the data (a layer's view id), e.g. long-term trend or 2022 comparison. */
  view: string | null
  /** Selected analysis period for trend results (only periods with a reviewed result are offered). */
  window: string | null
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
  /** Analysis periods for the trend verdict. */
  windows?: ControlGroup
  periods?: ControlGroup & { wholePeriodLabel?: string }
  comparisons?: ControlGroup
}

/** One question a layer can answer. Each becomes a tab in the investigation scroll. */
export interface LayerView {
  id: string
  label: string
  /** The question in plain words, shown under the tabs. */
  question: string
}

export interface LayerActions {
  selectView: (id: string) => void
  selectWindow: (id: string) => void
  selectPeriod: (id: string | null) => void
  selectComparison: (id: string) => void
  selectFeature: (id: string | null) => void
}

/** Everything a layer contributes to the screen for one selection. */
export interface LayerPresentation {
  /** The questions this layer answers, in tab order. The active one is `selection.view`. */
  views: LayerView[]
  /** Controls for the active view only. */
  controls: LayerControls
  /**
   * SVG content in atlas units. Positions must come from `projectLonLat`.
   * Mark the feature the reader must keep seeing with `data-atlas-focus`; the opened scroll stays clear of it.
   */
  mapSvg: ReactNode
  /** HTML anchored over the map (labels). Positioned with `atlasPercent`. */
  mapHtml?: ReactNode
  /** Investigation body for the active view: timeline or comparison, verdict, quality notices. */
  evidence: ReactNode
  /** "About" tab: what the variable measures, where it comes from, what it cannot tell you. */
  about: ReactNode
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
