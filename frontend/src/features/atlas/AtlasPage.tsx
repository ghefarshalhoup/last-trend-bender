import { useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { fetchCatalog, studyEndpointFor, type CatalogBundle } from '../../api/airStudy'
import { useApiResource } from '../../api/useApiResource'
import { DecorativeFrame } from '../../components/Frame/DecorativeFrame'
import { ErrorView, LoadingView } from '../air/StateViews'
import { resolveElements, type ElementId, type ElementView } from '../explorer/elements'
import { GuideBubble } from '../explorer/GuideBubble'
import { TitleBadge } from '../explorer/TitleBadge'
import { AtlasBase } from './AtlasBase'
import styles from './AtlasPage.module.css'
import { ElementMedallions } from './ElementMedallions'
import { ScrollButton, ScrollOverlay, type ScrollTab } from './EvidenceScroll'
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

const NEUTRAL_GUIDE = 'This atlas shows what satellites recorded over Ukraine. Choose an element in the top-right corner.'

/** The shell owns the active element and whether its scroll is open. Everything else belongs to the layer host. */
function Atlas({ catalog }: { catalog: CatalogBundle }) {
  const [active, setActive] = useState<ElementId | null>(null)
  const [scrollOpen, setScrollOpen] = useState(false)
  const [unread, setUnread] = useState(false)
  const elements = useMemo(() => resolveElements(catalog.elements, Object.keys(LAYERS) as ElementId[]), [catalog.elements])
  const layer = active ? (LAYERS[active] ?? null) : null
  const endpoint = active ? studyEndpointFor(catalog.elements, active) : null
  const scrollRef = useRef<HTMLDivElement>(null)

  const chrome: ChromeProps = {
    elements,
    active,
    scrollOpen,
    unread,
    onSelect: (id) => {
      setActive(id)
      setUnread(!scrollOpen)
    },
    onClear: () => {
      setActive(null)
      setScrollOpen(false)
      setUnread(false)
    },
    onToggleScroll: () => {
      setScrollOpen((open) => !open)
      setUnread(false)
    },
    onCloseScroll: () => {
      setScrollOpen(false)
      scrollRef.current?.querySelector('button')?.focus()
    },
    scrollRef,
  }

  if (layer && endpoint) return <LayerHost key={layer.id} layer={layer} endpoint={endpoint} {...chrome} />
  return <AtlasLayout {...chrome} guide={NEUTRAL_GUIDE} />
}

interface ChromeProps {
  elements: ElementView[]
  active: ElementId | null
  scrollOpen: boolean
  unread: boolean
  onSelect: (id: ElementId) => void
  onClear: () => void
  onToggleScroll: () => void
  onCloseScroll: () => void
  scrollRef: React.RefObject<HTMLDivElement | null>
}

/** Loads one layer's data and turns data + shared selection into the four outputs. */
function LayerHost({ layer, endpoint, ...chrome }: ChromeProps & { layer: EvidenceLayer; endpoint: string }) {
  const [selection, setSelection] = useState<AtlasSelection>(layer.defaultSelection)
  const loader = useCallback((signal: AbortSignal) => layer.load(endpoint, signal), [layer, endpoint])
  const { state, retry } = useApiResource(loader)

  const actions = useMemo<LayerActions>(
    () => ({
      selectView: (view) => setSelection((s) => ({ ...s, view })),
      selectWindow: (window) => setSelection((s) => ({ ...s, window })),
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

const OVERLAY_MAX = 384 // px, 24rem
const OVERLAY_MIN = 256 // px, 16rem: below this the scroll may cover the feature rather than become unreadable
const OVERLAY_GAP = 16

/**
 * Wide screens: width of the opened scroll so it stays right of the layer's focus feature
 * (marked `data-atlas-focus`). Recomputed when the stage resizes. Narrow screens use a bottom sheet.
 */
function useClearOfFocus(stageRef: React.RefObject<HTMLDivElement | null>, open: boolean): React.CSSProperties | undefined {
  const [width, setWidth] = useState<number | null>(null)
  useLayoutEffect(() => {
    const stage = stageRef.current
    if (!open || !stage) return
    const measure = () => {
      const focus = stage.querySelector('[data-atlas-focus]')
      const slot = stage.querySelector<HTMLElement>('[data-overlay-slot]')
      if (!focus || !slot || !window.matchMedia('(min-width: 62rem)').matches) return setWidth(null)
      const slotRight = slot.getBoundingClientRect().right
      const room = slotRight - focus.getBoundingClientRect().right - OVERLAY_GAP
      setWidth(Math.max(OVERLAY_MIN, Math.min(OVERLAY_MAX, room)))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(stage)
    return () => observer.disconnect()
  }, [stageRef, open])
  return width === null ? undefined : { width }
}

/** Shown in the scroll before any element is chosen. */
function NeutralHelp() {
  return (
    <div className={styles.help} data-testid="scroll-help">
      <p>Each element shows a different kind of satellite evidence on the same fixed map of Ukraine.</p>
      <ol>
        <li>Choose an element with the medallions in the top-right corner.</li>
        <li>Pick the analysis period in the bar above the map.</li>
        <li>Open this scroll: read the timeline and the verdict, or switch to the 2022 comparison.</li>
      </ol>
      <p>Elements marked “Coming later” have no evidence yet.</p>
    </div>
  )
}

/** Layout only: title, controls, the fixed map, and the corner pieces that sit over it. */
function AtlasLayout(props: LayoutProps) {
  const { elements, active, scrollOpen, unread, onSelect, onClear, onToggleScroll, onCloseScroll, scrollRef } = props
  const { guide, layer, presentation, selection, actions, children } = props
  const overlayId = useId()
  const stageRef = useRef<HTMLDivElement>(null)
  const overlayStyle = useClearOfFocus(stageRef, scrollOpen)
  const current = elements.find((e) => e.id === active)
  const art = current ? current.id : 'none'

  // Tabs are the layer's questions plus About. The active question is part of the shared selection.
  const [aboutOpen, setAboutOpen] = useState(false)
  const views = presentation?.views ?? []
  const activeView = views.find((v) => v.id === selection?.view) ?? views[0]
  const tabs: ScrollTab[] = presentation
    ? [
        ...views.map((v) => ({ id: v.id, label: v.label, content: v.id === activeView?.id ? presentation.evidence : null })),
        { id: 'about', label: 'About', content: presentation.about },
      ]
    : [{ id: 'help', label: 'How to read', content: <NeutralHelp /> }]
  const activeId = presentation ? (aboutOpen ? 'about' : (activeView?.id ?? 'about')) : 'help'
  const onSelectTab = (id: string) => {
    setAboutOpen(id === 'about')
    if (id !== 'about') actions?.selectView(id)
  }
  const title = layer?.title ?? 'How to read this atlas'
  const scrollLabel = current ? `${current.label} scroll` : 'Atlas scroll'

  return (
    <div className={styles.app} data-active={active ?? 'none'} data-testid="atlas-page">
      <DecorativeFrame className={styles.frame}>
        <header className={styles.header}>
          <TitleBadge />
        </header>

        {/* The bar's space is reserved from the start, so the map never resizes when an element is chosen. */}
        <div className={styles.controlsSlot}>
          {presentation && selection && actions ? (
            <LayerControlsBar controls={presentation.controls} selection={selection} actions={actions} />
          ) : (
            <p className={styles.controlsHint} data-testid="controls-hint">
              Analysis periods appear here once you choose an element.
            </p>
          )}
        </div>

        <div className={styles.stage} data-scroll={scrollOpen ? 'open' : 'closed'} ref={stageRef}>
          <div className={styles.mapArea}>
            <div className={styles.atlas} data-testid="atlas-frame">
              <svg viewBox={`0 0 ${ATLAS_WIDTH} ${ATLAS_HEIGHT}`} className={styles.svg} role="img" aria-label="Illustrated map of Ukraine">
                <AtlasBase />
                {presentation?.mapSvg}
              </svg>
              {presentation?.mapHtml}
            </div>
          </div>

          <div className={styles.topRight}>
            <ElementMedallions elements={elements} active={active} onSelect={onSelect} onClear={onClear} />
          </div>

          <div className={styles.bottomLeft}>
            {children}
            <GuideBubble text={guide} accent={current?.accent} />
          </div>

          <div className={styles.bottomRight} ref={scrollRef}>
            <ScrollButton art={art} label={scrollLabel} open={scrollOpen} unread={unread} controls={overlayId} onToggle={onToggleScroll} />
          </div>

          {scrollOpen ? (
            <div className={styles.overlaySlot} style={overlayStyle} data-overlay-slot="">
              <ScrollOverlay key={art} id={overlayId} title={title} art={art} tabs={tabs} activeId={activeId} onSelectTab={onSelectTab} question={activeId === 'about' ? undefined : activeView?.question} onClose={onCloseScroll} />
            </div>
          ) : null}
        </div>

        <p className={styles.foot}>
          Illustrated-atlas preview · geography: Natural Earth · <a href="#/">Open the tile-map version</a>
        </p>
      </DecorativeFrame>
    </div>
  )
}
