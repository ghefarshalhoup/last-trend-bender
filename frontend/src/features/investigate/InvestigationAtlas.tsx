import { useId, useMemo, useRef, useState } from 'react'
import type { CatalogBundle } from '../../api/airStudy'
import { DecorativeFrame } from '../../components/Frame/DecorativeFrame'
import { AtlasBase } from '../atlas/AtlasBase'
import pageStyles from '../atlas/AtlasPage.module.css'
import { ElementMedallions } from '../atlas/ElementMedallions'
import { ScrollButton, ScrollOverlay } from '../atlas/EvidenceScroll'
import { ATLAS_HEIGHT, ATLAS_WIDTH, atlasPercent, projectLonLat, ringPath } from '../atlas/projection'
import { resolveElements, type ElementId } from '../explorer/elements'
import { GuideBubble } from '../explorer/GuideBubble'
import { TitleBadge } from '../explorer/TitleBadge'
import { hasDataFor, placeLabel, variablesOf, type PlaceFeature, type VariableCatalog, type VariableEntry } from './catalog'
import styles from './InvestigationAtlas.module.css'
import { endpointFor, indexTrends, readSeries, trendKey, WINDOWS, type TrendsPayload, type WindowId } from './series'
import { usePayloads } from './usePayloads'
import { VariableCard, type SeriesState } from './VariableCard'
import { pickTrend, readCard } from './verdict'

export const MAX_CARDS = 4
const ALL_ELEMENTS: ElementId[] = ['air', 'fire', 'land', 'water']

/** The guided example: Kyiv NO₂ beside the two weather variables that most affect it. */
export const GUIDED_EXAMPLE = {
  place: 'kyiv_no2_box',
  window: 'full_record' as WindowId,
  element: 'air' as ElementId,
  cards: ['no2_mean_molec_cm2', 'ws10m', 'cloud_amt'],
}

interface Props {
  cases: CatalogBundle
  catalog: VariableCatalog
  trends: TrendsPayload
}

type Phase = 'choose' | 'investigate'

/**
 * Two phases. 1: choose a place on the map and an analysis period. 2: the map becomes the
 * background and each chosen variable opens as a card with its timeline and verdict.
 */
export function InvestigationAtlas({ cases, catalog, trends }: Props) {
  const [phase, setPhase] = useState<Phase>('choose')
  const [place, setPlace] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [window, setWindow] = useState<WindowId>('full_record')
  const [element, setElement] = useState<ElementId | null>(null)
  const [cards, setCards] = useState<string[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [example, setExample] = useState(false)
  const [scrollOpen, setScrollOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const overlayId = useId()

  const elements = useMemo(() => resolveElements(cases.elements, ALL_ELEMENTS), [cases.elements])
  const places = catalog.study_regions.features
  const trendIndex = useMemo(() => indexTrends(trends), [trends])
  const byId = useMemo(() => new Map(catalog.variables.map((v) => [v.metric_id, v])), [catalog.variables])
  const openVars = cards.map((id) => byId.get(id)).filter((v): v is VariableEntry => Boolean(v))
  const { states, retry } = usePayloads(phase === 'investigate' ? openVars.map(endpointFor) : [])

  const edit = () => {
    setExample(false)
    setNotice(null)
  }
  const choosePlace = (id: string) => {
    edit()
    setPlace(id)
  }
  const investigate = () => {
    if (!place) return setNotice('Choose a place on the map first.')
    edit()
    setPhase('investigate')
  }
  const toggleCard = (v: VariableEntry) => {
    edit()
    if (cards.includes(v.metric_id)) return setCards((c) => c.filter((id) => id !== v.metric_id))
    if (place && !hasDataFor(v, place)) return setNotice(`${v.short_label} has no data for ${placeLabel(place)}.`)
    if (cards.length >= MAX_CARDS) return setNotice(`Up to ${MAX_CARDS} cards at once. Remove one first.`)
    setCards((c) => [...c, v.metric_id])
  }
  const startExample = () => {
    setPlace(GUIDED_EXAMPLE.place)
    setWindow(GUIDED_EXAMPLE.window)
    setElement(GUIDED_EXAMPLE.element)
    setCards(GUIDED_EXAMPLE.cards)
    setNotice(null)
    setPhase('investigate')
    setExample(true)
  }

  const cardState = (v: VariableEntry): SeriesState => {
    const s = states[endpointFor(v)]
    if (!s || s.status === 'loading') return { status: 'loading' }
    if (s.status === 'error') return { status: 'error', message: s.error.message }
    return { status: 'ready', series: place ? readSeries(v, place, s.data) : null }
  }
  const trendFor = (v: VariableEntry, st: SeriesState) =>
    st.status === 'ready' && st.series && place ? pickTrend(trendIndex.get(trendKey(place, v.metric_id, window)), st.series, window) : undefined

  const guide = guideText({ phase, place, element, example, notice, openVars, cardState, trendFor })
  const current = elements.find((e) => e.id === element)
  const art = current?.id ?? 'none'

  return (
    <div className={pageStyles.app} data-active={element ?? 'none'} data-testid="atlas-page">
      <DecorativeFrame className={pageStyles.frame}>
        <header className={pageStyles.header}>
          <TitleBadge />
        </header>

        <div className={pageStyles.controlsSlot}>
          <div className={styles.bar} data-testid="layer-controls" data-phase={phase}>
            {phase === 'choose' ? (
              <>
                <div className={styles.group}>
                  <span className={styles.step}>1 · Place</span>
                  <span className={styles.placeName} data-testid="chosen-place">{place ? placeLabel(place) : 'Press a place on the map'}</span>
                  <span className={styles.outside}>
                    Outside Ukraine:
                    {places.filter((f) => !f.properties.is_ukraine_study_area).map((f) => (
                      <button key={f.properties.region_id} type="button" className={styles.chip} aria-pressed={place === f.properties.region_id} onClick={() => choosePlace(f.properties.region_id)} data-testid={`place-${f.properties.region_id}`}>
                        {placeLabel(f.properties.region_id)}
                      </button>
                    ))}
                  </span>
                </div>
                <PeriodGroup window={window} onChange={(w) => { edit(); setWindow(w) }} label="2 · Period" />
                <div className={styles.actions}>
                  <button type="button" className={styles.primary} onClick={investigate} data-testid="investigate">Investigate</button>
                  <button type="button" className={styles.secondary} onClick={startExample} data-testid="guided-example">Start guided example</button>
                </div>
              </>
            ) : (
              <>
                <div className={styles.group}>
                  <span className={styles.step}>Place</span>
                  <span className={styles.placeName} data-testid="chosen-place">{place ? placeLabel(place) : ''}</span>
                  <button type="button" className={styles.chip} onClick={() => { edit(); setPhase('choose') }} data-testid="change-place">Change place</button>
                </div>
                <PeriodGroup window={window} onChange={(w) => { edit(); setWindow(w) }} label="Period" />
                <VariablePicker catalog={catalog} element={element} place={place} cards={cards} onToggle={toggleCard} />
              </>
            )}
          </div>
        </div>

        <div className={pageStyles.stage} data-scroll={scrollOpen ? 'open' : 'closed'} data-phase={phase}>
          <div className={pageStyles.mapArea}>
            <div className={`${pageStyles.atlas} ${phase === 'investigate' ? styles.dimmed : ''}`} data-testid="atlas-frame">
              <svg viewBox={`0 0 ${ATLAS_WIDTH} ${ATLAS_HEIGHT}`} className={pageStyles.svg} role="img" aria-label="Illustrated map of Ukraine">
                <AtlasBase />
                <PlaceBoxes places={places} selected={place} hover={phase === 'choose' ? hover : null} />
              </svg>
              {phase === 'choose' ? <PlacePins places={places} selected={place} onChoose={choosePlace} onHover={setHover} /> : null}
            </div>
          </div>

          {phase === 'investigate' ? (
            <section className={styles.cards} aria-label="Variable cards" data-testid="card-area">
              {openVars.length === 0 ? (
                <p className={styles.empty} data-testid="cards-empty">Choose an element at the top right, then pick its variables in the bar above. Each opens here as a card.</p>
              ) : (
                openVars.map((v) => {
                  const st = cardState(v)
                  const el = elements.find((e) => e.id === v.element_id) ?? elements[0]!
                  return (
                    <VariableCard
                      key={v.metric_id}
                      variable={v}
                      element={el}
                      placeId={place ?? ''}
                      window={window}
                      invasionDate={catalog.conflict_start}
                      state={st}
                      trend={trendFor(v, st)}
                      onRemove={() => toggleCard(v)}
                      onRetry={() => retry(endpointFor(v))}
                    />
                  )
                })
              )}
            </section>
          ) : null}

          <div className={pageStyles.topRight}>
            <ElementMedallions elements={elements} active={element} onSelect={(id) => { edit(); setElement(id) }} onClear={() => { edit(); setElement(null) }} />
          </div>
          <div className={`${pageStyles.bottomLeft} ${styles.guide}`}>
            <GuideBubble text={guide} accent={current?.accent} />
          </div>
          <div className={pageStyles.bottomRight} ref={scrollRef}>
            <ScrollButton art={art} label="How to read" open={scrollOpen} unread={false} controls={overlayId} onToggle={() => setScrollOpen((o) => !o)} />
          </div>
          {scrollOpen ? (
            <div className={pageStyles.overlaySlot} data-overlay-slot="">
              <ScrollOverlay
                id={overlayId}
                title="How to read this atlas"
                art={art}
                tabs={[{ id: 'help', label: 'How to read', content: <HowToRead /> }]}
                activeId="help"
                onSelectTab={() => undefined}
                onClose={() => {
                  setScrollOpen(false)
                  scrollRef.current?.querySelector('button')?.focus()
                }}
              />
            </div>
          ) : null}
        </div>

        <p className={pageStyles.foot}>
          Data: NASA OMI (Giovanni), NASA FIRMS VIIRS, NASA POWER (MERRA-2, CERES) · geography: Natural Earth · <a href="#/">Open the tile-map version</a>
        </p>
      </DecorativeFrame>
    </div>
  )
}

function PeriodGroup({ window, onChange, label }: { window: WindowId; onChange: (w: WindowId) => void; label: string }) {
  return (
    <div role="group" aria-label="Analysis period" className={styles.group}>
      <span className={styles.step}>{label}</span>
      {WINDOWS.map((w) => (
        <button key={w.id} type="button" className={styles.chip} aria-pressed={window === w.id} onClick={() => onChange(w.id)} data-testid={`window-${w.id}`}>
          {w.label}
        </button>
      ))}
    </div>
  )
}

function VariablePicker({ catalog, element, place, cards, onToggle }: { catalog: VariableCatalog; element: ElementId | null; place: string | null; cards: string[]; onToggle: (v: VariableEntry) => void }) {
  if (!element) return <p className={styles.hint} data-testid="variables-hint">Choose an element at the top right to list its variables.</p>
  return (
    <div role="group" aria-label="Variables" className={`${styles.group} ${styles.variables}`} data-testid="variable-picker">
      <span className={styles.step}>Variables · {cards.length}/{MAX_CARDS} open</span>
      {variablesOf(catalog, element).map((v) => {
        const here = place ? hasDataFor(v, place) : true
        return (
          <button
            key={v.metric_id}
            type="button"
            className={styles.chip}
            aria-pressed={cards.includes(v.metric_id)}
            aria-disabled={!here}
            data-testid={`variable-${v.metric_id}`}
            onClick={() => onToggle(v)}
          >
            {v.short_label}
            {here ? null : <span className={styles.noData}> · no data here</span>}
          </button>
        )
      })}
    </div>
  )
}

/** The chosen place's true box; in phase 1 also the box under the pointer. */
function PlaceBoxes({ places, selected, hover }: { places: PlaceFeature[]; selected: string | null; hover: string | null }) {
  const draw = (id: string | null, kind: 'selected' | 'hover') => {
    const f = places.find((p) => p.properties.region_id === id)
    if (!f) return null
    return (
      <path
        d={ringPath(f.geometry.coordinates[0] as number[][])}
        className={kind === 'selected' ? styles.boxSelected : styles.boxHover}
        data-testid={kind === 'selected' ? 'place-box' : 'place-box-hover'}
        data-atlas-focus={kind === 'selected' ? '' : undefined}
      />
    )
  }
  return (
    <g>
      {hover && hover !== selected ? draw(hover, 'hover') : null}
      {draw(selected, 'selected')}
    </g>
  )
}

function PlacePins({ places, selected, onChoose, onHover }: { places: PlaceFeature[]; selected: string | null; onChoose: (id: string) => void; onHover: (id: string | null) => void }) {
  return (
    <>
      {places
        .filter((f) => f.properties.is_ukraine_study_area)
        .map((f) => {
          const { region_id, center, area_km2 } = f.properties
          const [x, y] = projectLonLat(center.lon, center.lat)
          const pos = atlasPercent(x, y)
          return (
            <button
              key={region_id}
              type="button"
              className={styles.pin}
              style={{ left: pos.left, top: pos.top }}
              aria-pressed={selected === region_id}
              aria-label={`${placeLabel(region_id)}, ${Math.round(area_km2).toLocaleString('en')} square kilometres`}
              onClick={() => onChoose(region_id)}
              onMouseEnter={() => onHover(region_id)}
              onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(region_id)}
              onBlur={() => onHover(null)}
              data-testid={`place-${region_id}`}
            >
              <span className={styles.pinDot} aria-hidden="true" />
              <span className={styles.pinLabel} aria-hidden="true">{placeLabel(region_id)}</span>
            </button>
          )
        })}
    </>
  )
}

function HowToRead() {
  return (
    <div className={styles.help} data-testid="scroll-help">
      <ol>
        <li>Press a place on the map and pick a period, then press Investigate.</li>
        <li>Choose an element (top right), then up to four of its variables. Each opens as a card.</li>
        <li>Press i on a card to turn it over: what the variable is, its source, and how it was tested.</li>
      </ol>
      <h3>The verdict on every card</h3>
      <ul className={styles.key}>
        <li><strong>● Significant</strong> The trend is unlikely to be chance (p below 0.05). Solid rate line.</li>
        <li><strong>○ No significant trend</strong> The data are consistent with no change. Dashed rate line.</li>
        <li><strong>– Not assessed</strong> No test result for this place and period. No rate is shown.</li>
      </ul>
      <p>The red line marks the invasion, 24 February 2022. Hollow points are months the satellite saw on under half the days. A significant trend does not say what caused it.</p>
    </div>
  )
}

interface GuideInput {
  phase: Phase
  place: string | null
  element: ElementId | null
  example: boolean
  notice: string | null
  openVars: VariableEntry[]
  cardState: (v: VariableEntry) => SeriesState
  trendFor: (v: VariableEntry, st: SeriesState) => ReturnType<typeof pickTrend>
}

function guideText({ phase, place, element, example, notice, openVars, cardState, trendFor }: GuideInput): string {
  if (notice) return notice
  if (phase === 'choose') {
    if (!place) return 'Press a place on the map, or start the guided example. Each place is a study box; its true size appears when you point at it.'
    return `${placeLabel(place)} is chosen. Pick a period and press Investigate.`
  }
  if (example) {
    // Numbers come from the NO₂ card itself, so the story cannot drift from the data.
    const no2 = openVars.find((v) => v.metric_id === 'no2_mean_molec_cm2')
    const st = no2 ? cardState(no2) : null
    const r = no2 && st?.status === 'ready' && st.series ? readCard(no2, st.series, trendFor(no2, st)) : null
    if (!r) return 'Guided example: loading Kyiv’s NO₂ record…'
    const trend = r.verdict === 'significant' ? 'is significant' : r.verdict === 'not_significant' ? 'is not significant' : 'has not been tested'
    return `Guided example: Kyiv’s NO₂ in March–August 2022 was ${r.seasonalText ?? 'not comparable'}, yet the long-term trend ${trend}. Wind and cloud show the weather in the same months: could weather alone explain the drop?`
  }
  if (!openVars.length) return element ? 'Pick variables in the bar above.' : 'Choose an element at the top right.'
  const counts = { significant: 0, not_significant: 0, not_assessed: 0 }
  for (const v of openVars) {
    const st = cardState(v)
    if (st.status !== 'ready' || !st.series) continue
    counts[readCard(v, st.series, trendFor(v, st)).verdict] += 1
  }
  const parts = [
    counts.significant ? `${counts.significant} significant` : null,
    counts.not_significant ? `${counts.not_significant} not significant` : null,
    counts.not_assessed ? `${counts.not_assessed} not assessed` : null,
  ].filter(Boolean)
  const tail = openVars.length > 1 ? ' With several cards open, one may look significant by chance alone.' : ''
  return `${placeLabel(place ?? '')}: ${parts.join(', ') || 'loading'}.${tail}`
}
