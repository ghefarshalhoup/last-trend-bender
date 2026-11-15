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
import { extraSupport, hasDataFor, NO_COMPARISON_WEATHER, NO_REGIONAL_NO2, noDataReason, OUTSIDE_DISTANCE_KM, placeLabel, variablesOf, type ComparisonWeather, type ExtraSupport, type No2Regional, type PlaceFeature, type VariableCatalog, type VariableEntry } from './catalog'
import styles from './InvestigationAtlas.module.css'
import { endpointFor, indexTrends, readSeries, trendKey, WINDOWS, type SeriesState, type TrendsPayload, type WindowId } from './series'
import { usePayloads } from './usePayloads'
import { observe } from './observation'
import { VariableCard } from './VariableCard'
import { pickTrend } from './verdict'

export const MAX_CARDS = 3
/** Places outside the war that can be shown beside a Ukrainian place. */
export const COMPARE_PLACES = ['poland_krakow', 'czechia_prague'] as const
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
  /** Monthly NO₂ beyond Kyiv. Optional: without it NO₂ is offered for Kyiv only. */
  no2Regional?: No2Regional
  /** Temperature, sunlight and evaporation demand for the comparison cities. */
  comparisonWeather?: ComparisonWeather
}

type Phase = 'choose' | 'investigate'

/**
 * Two phases. 1: choose a place on the map and an analysis period. 2: the map becomes the
 * background and each chosen variable opens as a card with its timeline and verdict.
 */
export function InvestigationAtlas({ cases, catalog, trends, no2Regional = NO_REGIONAL_NO2, comparisonWeather = NO_COMPARISON_WEATHER }: Props) {
  const [phase, setPhase] = useState<Phase>('choose')
  const [place, setPlace] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [window, setWindow] = useState<WindowId>('full_record')
  const [element, setElement] = useState<ElementId | null>(null)
  const [cards, setCards] = useState<string[]>([])
  /** A comparison city shown beside the chosen place; null = single view. */
  const [compare, setCompare] = useState<string | null>(null)
  /** The card the avatar reads (metric and place); the latest opened, or the one last clicked. */
  const [focus, setFocus] = useState<{ metric: string; place: string | null } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [example, setExample] = useState(false)
  const [scrollOpen, setScrollOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const overlayId = useId()

  const elements = useMemo(() => resolveElements(cases.elements, ALL_ELEMENTS), [cases.elements])
  const places = useMemo(() => {
    const known = new Set(catalog.study_regions.features.map((f) => f.properties.region_id))
    return [...catalog.study_regions.features, ...no2Regional.extra_places.filter((f) => !known.has(f.properties.region_id))]
  }, [catalog.study_regions.features, no2Regional.extra_places])
  const no2Places = useMemo(() => extraSupport(no2Regional, comparisonWeather), [no2Regional, comparisonWeather])
  const trendIndex = useMemo(() => indexTrends(trends), [trends])
  const byId = useMemo(() => new Map(catalog.variables.map((v) => [v.metric_id, v])), [catalog.variables])
  const openVars = cards.map((id) => byId.get(id)).filter((v): v is VariableEntry => Boolean(v))
  const shownPlaces = compare ? [place, compare] : [place]
  const { states, retry } = usePayloads(
    phase === 'investigate' ? openVars.flatMap((v) => shownPlaces.map((p) => endpointFor(v, p, no2Places))) : [],
  )

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
    if (place && !hasDataFor(v, place, no2Places)) return setNotice(noDataReason(v, place))
    if (cards.length >= MAX_CARDS) return setNotice(`Up to ${MAX_CARDS} cards at once. Remove one first.`)
    setCards((c) => [...c, v.metric_id])
    setFocus({ metric: v.metric_id, place })
  }
  const startExample = () => {
    setPlace(GUIDED_EXAMPLE.place)
    setWindow(GUIDED_EXAMPLE.window)
    setElement(GUIDED_EXAMPLE.element)
    setCards(GUIDED_EXAMPLE.cards)
    setFocus({ metric: GUIDED_EXAMPLE.cards[0] ?? '', place: GUIDED_EXAMPLE.place })
    setCompare(null)
    setNotice(null)
    setPhase('investigate')
    setExample(true)
  }

  const cardState = (v: VariableEntry, at: string | null = place): SeriesState => {
    const s = states[endpointFor(v, at, no2Places)]
    if (!s || s.status === 'loading') return { status: 'loading' }
    if (s.status === 'error') return { status: 'error', message: s.error.message }
    return { status: 'ready', series: at ? readSeries(v, at, s.data) : null }
  }
  const trendFor = (v: VariableEntry, st: SeriesState, at: string | null = place) =>
    st.status === 'ready' && st.series && at ? pickTrend(trendIndex.get(trendKey(at, v.metric_id, window)), st.series, window) : undefined

  // Focus falls back to the newest open card when the focused one is closed.
  const focusVar = openVars.find((v) => v.metric_id === focus?.metric) ?? openVars[openVars.length - 1]
  const focusPlace = focus?.place && shownPlaces.includes(focus.place) ? focus.place : place
  const guide = guideText({
    phase, place: focusPlace, element, example, notice, openVars, focusVar, window,
    cardState: (v) => cardState(v, focusPlace), trendFor: (v, st) => trendFor(v, st, focusPlace),
  })
  const guideAction =
    phase === 'investigate' && focusVar && !notice ? { label: 'Explore another place', onClick: () => { edit(); setPhase('choose') } } : undefined
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
                </div>
                <CompareGroup compare={compare} onChange={(c) => { edit(); setCompare(c) }} />
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
                <CompareGroup compare={compare} onChange={(c) => { edit(); setCompare(c) }} />
                <PeriodGroup window={window} onChange={(w) => { edit(); setWindow(w) }} label="Period" />
                <VariablePicker catalog={catalog} element={element} place={place} no2Places={no2Places} cards={cards} onToggle={toggleCard} />
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
              <OutsideMarker places={places} selected={compare} />
            </div>
          </div>

          {phase === 'investigate' ? (
            <section className={`${styles.cards} ${compare ? styles.split : ''}`} aria-label="Variable cards" data-testid="card-area" data-compare={compare ?? undefined}>
              {openVars.length === 0 ? (
                <p className={styles.empty} data-testid="cards-empty">Choose an element at the top right, then pick its variables in the bar above. Each opens here as a card.</p>
              ) : (
                shownPlaces.map((at, i) => (
                  <div key={at ?? 'none'} className={compare ? styles.half : styles.single} data-testid={compare ? (i === 0 ? 'half-main' : 'half-compare') : undefined}>
                    {compare ? (
                      <h2 className={styles.halfTitle}>
                        {at ? placeLabel(at) : ''}
                        <span>{i === 0 ? 'Ukraine' : 'Comparison city, outside the war'}</span>
                      </h2>
                    ) : null}
                    <div className={styles.cardRow}>
                      {openVars.map((v) => {
                        const st = cardState(v, at)
                        const el = elements.find((e) => e.id === v.element_id) ?? elements[0]!
                        const isFocus = focusVar?.metric_id === v.metric_id && focusPlace === at
                        return (
                          <VariableCard
                            key={`${v.metric_id}-${at ?? ''}`}
                            variable={v}
                            element={el}
                            placeId={at ?? ''}
                            window={window}
                            invasionDate={catalog.conflict_start}
                            state={st}
                            trend={trendFor(v, st, at)}
                            onRemove={() => toggleCard(v)}
                            onRetry={() => retry(endpointFor(v, at, no2Places))}
                            focused={isFocus && openVars.length * shownPlaces.length > 1}
                            onFocus={() => setFocus({ metric: v.metric_id, place: at })}
                          />
                        )
                      })}
                    </div>
                  </div>
                ))
              )}
            </section>
          ) : null}

          <div className={pageStyles.topRight}>
            <ElementMedallions elements={elements} active={element} onSelect={(id) => { edit(); setElement(id) }} onClear={() => { edit(); setElement(null) }} />
          </div>
          <div className={`${pageStyles.bottomLeft} ${styles.guide}`}>
            <GuideBubble text={guide} accent={current?.accent} action={guideAction} />
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

function CompareGroup({ compare, onChange }: { compare: string | null; onChange: (c: string | null) => void }) {
  return (
    <div role="group" aria-label="Compare with a city outside the war" className={styles.group}>
      <span className={styles.step}>Compare with</span>
      {COMPARE_PLACES.map((id) => (
        <button
          key={id}
          type="button"
          className={styles.chip}
          aria-pressed={compare === id}
          onClick={() => onChange(compare === id ? null : id)}
          data-testid={`compare-${id}`}
        >
          {placeLabel(id)}
        </button>
      ))}
    </div>
  )
}

function PeriodGroup({ window, onChange, label }: { window: WindowId; onChange: (w: WindowId) => void; label: string }) {
  return (
    <div role="group" aria-label="Analysis period" className={styles.group}>
      <span className={styles.step}>{label}</span>
      {WINDOWS.map((w) => (
        <button key={w.id} type="button" className={styles.chip} aria-pressed={window === w.id} onClick={() => onChange(w.id)} title={w.note} data-testid={`window-${w.id}`}>
          {w.label} <span className={styles.dates}>· {w.dates}</span>
        </button>
      ))}
    </div>
  )
}

function VariablePicker({ catalog, element, place, no2Places, cards, onToggle }: { catalog: VariableCatalog; element: ElementId | null; place: string | null; no2Places: ExtraSupport; cards: string[]; onToggle: (v: VariableEntry) => void }) {
  if (!element) return <p className={styles.hint} data-testid="variables-hint">Choose an element at the top right to list its variables.</p>
  return (
    <div role="group" aria-label="Variables" className={`${styles.group} ${styles.variables}`} data-testid="variable-picker">
      <span className={styles.step}>Variables · {cards.length}/{MAX_CARDS} open</span>
      {variablesOf(catalog, element).map((v) => {
        const here = place ? hasDataFor(v, place, no2Places) : true
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

/** A comparison city is outside Ukraine: label its box, or point off the map when it lies beyond the edge. */
function OutsideMarker({ places, selected }: { places: PlaceFeature[]; selected: string | null }) {
  const f = places.find((p) => p.properties.region_id === selected)
  if (!f || f.properties.is_ukraine_study_area) return null
  const { center } = f.properties
  const [x, y] = projectLonLat(center.lon, center.lat)
  const offMap = x < 24
  const km = OUTSIDE_DISTANCE_KM[f.properties.region_id]
  const pos = atlasPercent(offMap ? 24 : x, Math.min(Math.max(y, 60), ATLAS_HEIGHT - 60))
  return (
    <p className={styles.outsideMarker} style={{ left: pos.left, top: pos.top }} data-off-map={offMap} data-testid="outside-marker">
      {offMap ? '← ' : ''}
      <strong>{placeLabel(f.properties.region_id)}</strong>
      <span> · comparison city outside the war{km ? `, about ${km} km west of Ukraine` : ''}{offMap ? '; it lies beyond this map' : ''}</span>
    </p>
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
        <li><strong>– Too little data / Not assessed</strong> The record is too short or too patchy for a fair test, or no test was run. No rate is shown.</li>
      </ul>
      <p><strong>Periods.</strong> Full record: 2015–2022 (NO₂ and fire end in August 2022, weather in December 2022). Before the invasion: 2015 to February 2022. The data are monthly, so February 2022 is counted whole and includes its last five days, from 24 February. Grey shading marks months a test did not use.</p>
      <p>The guide reads one card at a time: the newest, or the one you click. It reports that card’s test and, separately, how March–August 2022 compared with earlier years. It does not explain causes.</p>
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
  focusVar: VariableEntry | undefined
  window: WindowId
  cardState: (v: VariableEntry) => SeriesState
  trendFor: (v: VariableEntry, st: SeriesState) => ReturnType<typeof pickTrend>
}

function guideText({ phase, place, element, example, notice, openVars, focusVar, window, cardState, trendFor }: GuideInput): string {
  if (notice) return notice
  if (phase === 'choose') {
    if (!place) return 'Press a place on the map, or start the guided example. Each place is a study box; its true size appears when you point at it.'
    return `${placeLabel(place)} is chosen. Pick a period and press Investigate.`
  }
  if (!focusVar || !place) return element ? 'Pick variables in the bar above.' : 'Choose an element at the top right.'
  const st = cardState(focusVar)
  const text = observe({ variable: focusVar, placeId: place, window, state: st, trend: trendFor(focusVar, st), noDataReason: noDataReason(focusVar, place) })
  const more = openVars.length > 1 ? ' Click another card to read it here.' : ''
  return `${example ? 'Guided example: ' : ''}${text}${more}`
}
