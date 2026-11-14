import { MotionConfig } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DEFAULT_BASELINE, getSeasonalSummary, type BaselineOption } from '../../adapters/baselines'
import { buildMonthRows } from '../../adapters/months'
import { AIR_ELEMENT_ID, fetchCatalog, fetchStudy, studyEndpointFor, type CatalogBundle } from '../../api/airStudy'
import { useApiResource } from '../../api/useApiResource'
import { DecorativeFrame } from '../../components/Frame/DecorativeFrame'
import { StudyPanel } from '../air/StudyPanel'
import { ErrorView, LoadingView } from '../air/StateViews'
import styles from './AirExplorer.module.css'
import { ElementControls } from './ElementControls'
import { resolveElements, type ElementId } from './elements'
import { GuideBubble } from './GuideBubble'
import { kyivResultLabel } from './kyivLabel'
import { MapLegend } from './MapLegend'
import { TitleBadge } from './TitleBadge'
import { UkraineMap, type MapCommand } from './UkraineMap'

/** Top level: load the catalog (availability only), then hand over to the explorer. */
export function ExplorerPage() {
  const { state, retry } = useApiResource(fetchCatalog)
  if (state.status === 'idle' || state.status === 'loading') return <LoadingView />
  if (state.status === 'error') return <ErrorView error={state.error} onRetry={retry} />
  return <Explorer catalog={state.data} />
}

function Explorer({ catalog }: { catalog: CatalogBundle }) {
  // Four independent pieces of state. None of them derives from another.
  const [active, setActive] = useState<ElementId | null>(null) // selected element
  const [panelOpen, setPanelOpen] = useState(false) //            evidence panel visibility
  const [baseline, setBaseline] = useState<BaselineOption>(DEFAULT_BASELINE)
  const [month, setMonth] = useState<number | null>(null)
  const [command, setCommand] = useState<MapCommand>({ kind: 'ukraine', nonce: 0 }) // camera requests only
  const [explored, setExplored] = useState(false) //               has the reader opened Kyiv yet

  const elements = useMemo(() => resolveElements(catalog.elements), [catalog.elements])
  const airEndpoint = studyEndpointFor(catalog.elements, AIR_ELEMENT_ID)

  // The study is requested the first time Air is selected, then kept.
  const [airRequested, setAirRequested] = useState(false)
  const loadStudy = useCallback((signal: AbortSignal) => fetchStudy(airEndpoint as string, signal), [airEndpoint])
  const { state: studyState, retry: retryStudy } = useApiResource(loadStudy, { enabled: airRequested && airEndpoint !== null })
  const study = studyState.status === 'success' ? studyState.data : null

  const airActive = active === 'air'
  const view = useMemo(() => {
    if (!study) return null
    const summary = getSeasonalSummary(study.result, baseline)
    const rows = buildMonthRows(study.result.matched_months, baseline)
    return { summary, rows, selectedRow: rows.find((r) => r.calendarMonth === month) ?? null }
  }, [study, baseline, month])

  const nonce = useRef(0)
  const moveCamera = (kind: MapCommand['kind']) => setCommand({ kind, nonce: ++nonce.current })

  const selectElement = (id: ElementId) => {
    setActive(id)
    if (id === 'air') setAirRequested(true)
  }
  const explore = () => {
    if (!study) return
    setExplored(true)
    setPanelOpen(true)
    moveCamera('kyiv')
  }
  const closePanel = () => setPanelOpen(false)
  const clearElement = () => {
    setActive(null)
    setPanelOpen(false)
    setExplored(false)
    moveCamera('ukraine')
  }

  // On narrow screens the panel stacks under the map; bring it into view when it opens.
  const panelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (panelOpen && window.matchMedia('(max-width: 61.99rem)').matches) {
      panelRef.current?.scrollIntoView({ block: 'start' })
    }
  }, [panelOpen])

  const showPanel = airActive && panelOpen && study !== null && view !== null
  const guideText = !airActive
    ? 'I came to read what satellites saw over Ukraine. Choose an element to begin.'
    : studyState.status === 'loading' || studyState.status === 'idle'
      ? 'Reading the Air record for Kyiv…'
      : studyState.status === 'error'
        ? 'I could not reach the Air record.'
        : showPanel
          ? 'Kyiv’s record is open. Pick a baseline, then a month.'
          : explored
            ? 'Panel closed. Air is still selected. Press Explore Kyiv to reopen it.'
            : 'Air is open. Find the Kyiv · NO₂ study box, or press Explore Kyiv.'

  return (
    <MotionConfig reducedMotion="user">
      <div className={styles.app} data-active={active ?? 'none'} data-panel={showPanel ? 'open' : 'closed'}>
        <DecorativeFrame className={styles.frame}>
          <header className={styles.header}>
            <TitleBadge />
            <ElementControls elements={elements} selected={active} onSelect={selectElement} onClear={clearElement} />
          </header>

          <div className={styles.main}>
            <div className={styles.mapArea}>
              <UkraineMap
                map={airActive && study ? study.map : null}
                command={command}
                resultLabel={airActive && explored && view ? kyivResultLabel(view.summary, view.selectedRow) : null}
                onExplore={explore}
              />

              <div className={styles.topRight}>
                <button type="button" className={styles.mapButton} onClick={() => moveCamera('ukraine')} data-testid="reset-ukraine">
                  Reset Ukraine view
                </button>
                {airActive && study && !showPanel ? (
                  <button type="button" className={`${styles.mapButton} ${styles.primary}`} onClick={explore} data-testid="explore-kyiv">
                    Explore Kyiv
                  </button>
                ) : null}
                <MapLegend airActive={airActive && study !== null} mapNote={study?.map.note ?? null} />
              </div>

              <div className={styles.bottomLeft}>
                {airActive && (studyState.status === 'error') ? (
                  <div className={styles.errorCard} role="alert" data-testid="study-error">
                    <p><strong>The Kyiv study did not load.</strong></p>
                    <p>{studyState.error.message}</p>
                    <div className={styles.errorActions}>
                      <button type="button" className={styles.mapButton} onClick={retryStudy}>Try again</button>
                      <button type="button" className={styles.mapButton} onClick={clearElement}>Clear element</button>
                    </div>
                  </div>
                ) : null}
                {airActive && (studyState.status === 'loading') ? (
                  <p className={styles.loadingNote} role="status">Loading the Kyiv study…</p>
                ) : null}
                <GuideBubble text={guideText} accent={airActive ? 'var(--element-air)' : undefined} />
              </div>
            </div>

            {showPanel ? (
              <div className={styles.panelArea} ref={panelRef} data-testid="panel-area">
                <StudyPanel
                  study={study}
                  elements={catalog.elements}
                  baseline={baseline}
                  onBaselineChange={setBaseline}
                  summary={view.summary}
                  rows={view.rows}
                  selectedMonth={month}
                  onSelectMonth={setMonth}
                  onClose={closePanel}
                  onClear={clearElement}
                />
              </div>
            ) : null}
          </div>
        </DecorativeFrame>
      </div>
    </MotionConfig>
  )
}

