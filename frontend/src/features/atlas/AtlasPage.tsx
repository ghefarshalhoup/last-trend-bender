import { useCallback, useMemo, useState } from 'react'
import { fetchCatalog, studyEndpointFor, type CatalogBundle } from '../../api/airStudy'
import { useApiResource } from '../../api/useApiResource'
import { DecorativeFrame } from '../../components/Frame/DecorativeFrame'
import { ErrorView, LoadingView } from '../air/StateViews'
import { ElementControls } from '../explorer/ElementControls'
import { resolveElements, type ElementId, type ElementView } from '../explorer/elements'
import { GuideBubble } from '../explorer/GuideBubble'
import { TitleBadge } from '../explorer/TitleBadge'
import { AtlasBase } from './AtlasBase'
import styles from './AtlasPage.module.css'
import { LayerControlsBar } from './LayerControlsBar'
import { LAYERS } from './layers/registry'
import type { AtlasSelection, EvidenceLayer, LayerActions, LayerPresentation } from './layers/types'
import { ATLAS_HEIGHT, ATLAS_WIDTH } from './projection'

/** Illustrated-atlas preview (#/atlas). One fixed map; elements swap the evidence drawn over it. */
export function AtlasPage() {
  const { state, retry } = useApiResource(fetchCatalog)
  if (state.status === 'idle' || state.status === 'loading') return <LoadingView />
  if (state.status === 'error') return <ErrorView error={state.error} onRetry={retry} />
  return <Atlas catalog={state.data} />
}

const NEUTRAL_GUIDE = 'This atlas shows what satellites recorded over Ukraine. Choose an element to see its evidence on the map.'

/** The shell owns which element is active. Everything else about a selection belongs to the layer host. */
function Atlas({ catalog }: { catalog: CatalogBundle }) {
  const [active, setActive] = useState<ElementId | null>(null)
  const elements = useMemo(() => resolveElements(catalog.elements), [catalog.elements])
  const layer = active ? (LAYERS[active] ?? null) : null
  const endpoint = active ? studyEndpointFor(catalog.elements, active) : null
  const chrome = { elements, active, onSelect: setActive, onClear: () => setActive(null) }

  if (layer && endpoint) return <LayerHost key={layer.id} layer={layer} endpoint={endpoint} {...chrome} />
  return <AtlasLayout {...chrome} guide={NEUTRAL_GUIDE} />
}

interface ChromeProps {
  elements: ElementView[]
  active: ElementId | null
  onSelect: (id: ElementId) => void
  onClear: () => void
}

/** Loads one layer's data and turns data + shared selection into the four outputs. */
function LayerHost({ layer, endpoint, ...chrome }: ChromeProps & { layer: EvidenceLayer; endpoint: string }) {
  const [selection, setSelection] = useState<AtlasSelection>(layer.defaultSelection)
  const loader = useCallback((signal: AbortSignal) => layer.load(endpoint, signal), [layer, endpoint])
  const { state, retry } = useApiResource(loader)

  const actions = useMemo<LayerActions>(
    () => ({
      selectPeriod: (period) => setSelection((s) => ({ ...s, period })),
      selectComparison: (comparison) => setSelection((s) => ({ ...s, comparison })),
      selectFeature: (feature) => setSelection((s) => ({ ...s, feature })),
    }),
    [],
  )
  const presentation = useMemo(
    () => (state.status === 'success' ? layer.present(state.data, selection, actions) : null),
    [state, layer, selection, actions],
  )

  if (state.status === 'error') {
    return (
      <AtlasLayout {...chrome} guide="I could not reach this element’s record.">
        <div className={styles.errorCard} role="alert" data-testid="layer-error">
          <p><strong>The evidence did not load.</strong></p>
          <p>{state.error.message}</p>
          <button type="button" className={styles.button} onClick={retry}>Try again</button>
        </div>
      </AtlasLayout>
    )
  }
  if (!presentation) return <AtlasLayout {...chrome} guide={layer.loadingText} />
  return <AtlasLayout {...chrome} guide={presentation.guide} layer={layer} presentation={presentation} selection={selection} actions={actions} />
}

interface LayoutProps extends ChromeProps {
  guide: string
  layer?: EvidenceLayer
  presentation?: LayerPresentation
  selection?: AtlasSelection
  actions?: LayerActions
  children?: React.ReactNode
}

/** Layout only: header, controls, the fixed map with the layer over it, guide, key and evidence widget. */
function AtlasLayout({ elements, active, onSelect, onClear, guide, layer, presentation, selection, actions, children }: LayoutProps) {
  const accent = elements.find((e) => e.id === active)?.accent
  return (
    <div className={styles.app} data-active={active ?? 'none'} data-testid="atlas-page">
      <DecorativeFrame className={styles.frame}>
        <header className={styles.header}>
          <TitleBadge />
          <ElementControls elements={elements} selected={active} onSelect={onSelect} onClear={onClear} />
        </header>

        <div className={styles.main} data-evidence={presentation ? 'open' : 'closed'}>
          <div className={styles.mapColumn}>
            {presentation && selection && actions ? (
              <LayerControlsBar controls={presentation.controls} selection={selection} actions={actions} />
            ) : null}
            <div className={styles.mapArea}>
              <div className={styles.atlas} data-testid="atlas-frame">
                <svg viewBox={`0 0 ${ATLAS_WIDTH} ${ATLAS_HEIGHT}`} className={styles.svg} role="img" aria-label="Illustrated map of Ukraine">
                  <AtlasBase />
                  {presentation?.mapSvg}
                </svg>
                {presentation?.mapHtml}
              </div>
            </div>
            <div className={styles.overlays}>
              <div className={styles.guide}>
                {children}
                <GuideBubble text={guide} accent={accent} />
              </div>
            </div>
          </div>

          {presentation && layer ? (
            <aside className={styles.evidence} aria-label="Evidence" data-testid="evidence-widget">
              <h2 className={styles.evidenceTitle}>{layer.title}</h2>
              <div className={styles.keyCard}>{presentation.mapKey}</div>
              {presentation.evidence}
            </aside>
          ) : null}
        </div>
        <p className={styles.foot}>
          Illustrated-atlas preview · geography: Natural Earth · <a href="#/">Open the tile-map version</a>
        </p>
      </DecorativeFrame>
    </div>
  )
}
