import { useCallback, useEffect, useMemo, useState } from 'react'
import { useApiResource } from '../../api/useApiResource'
import { extraSupport, fetchComparisonWeather, fetchNo2Regional, fetchVariableCatalog, hasDataFor, NO2_METRIC, NO_COMPARISON_WEATHER, NO_REGIONAL_NO2, placeLabel, type PlaceFeature } from '../investigate/catalog'
import { fetchTrends, indexTrends, type TrendsPayload } from '../investigate/series'
import { EarthMap, type Insets } from './EarthMap'
import styles from './EarthPage.module.css'
import { GlassCards, PLACE_COLORS } from './GlassCards'
import { Starfield } from './Starfield'

type View = 'earth' | 'case'

const NO_TRENDS: TrendsPayload = { status: 'not_available', results: [] }
const NARROW = 860
/** Places that can be drawn beside the chosen one. */
const COMPARABLE = ['kyiv_no2_box', 'poland_krakow', 'czechia_prague']
const MAX_COMPARE = 2

async function loadEarth(signal: AbortSignal) {
  const [catalog, trends, no2Regional, comparisonWeather] = await Promise.all([
    fetchVariableCatalog(signal),
    fetchTrends(signal).catch(() => NO_TRENDS),
    fetchNo2Regional(signal).catch(() => NO_REGIONAL_NO2),
    fetchComparisonWeather(signal).catch(() => NO_COMPARISON_WEATHER),
  ])
  return { catalog, trends, no2Regional, comparisonWeather }
}

/** Screen space the glass cards take, in the same sizes the stylesheet uses, so the camera can slide the place clear of them. */
function measure(investigating: boolean, expanded: boolean): Insets {
  if (typeof window === 'undefined' || !investigating) return { left: 0, bottom: 0 }
  const w = window.innerWidth
  // On a phone the expanded sheet covers the map; the camera keeps its last framing.
  if (w <= NARROW) return { left: 0, bottom: Math.round(window.innerHeight * 0.52) }
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  const compact = Math.min(Math.max(20 * rem, w * 0.32), 28 * rem)
  return { left: Math.round((expanded ? Math.max(compact, w * 0.6 - 32) : compact) + 32), bottom: 0 }
}

/**
 * `#/earth`: Earth → Ukraine → a place → Investigate.
 * One map stays behind everything; investigating slides the place to the right and lays glass cards on the left.
 */
export default function EarthPage() {
  const { state, retry } = useApiResource(loadEarth)
  const [view, setView] = useState<View>('earth')
  const [placeId, setPlaceId] = useState<string | null>(null)
  const [investigating, setInvestigatingRaw] = useState(false)
  const [expanded, setExpanded] = useState(false)
  // Closing the cards always returns to the compact layout next time.
  const setInvestigating = useCallback((on: boolean) => {
    setInvestigatingRaw(on)
    if (!on) setExpanded(false)
  }, [])
  const [compare, setCompare] = useState<string[]>([])
  const [metrics, setMetrics] = useState<string[]>([])
  const [explored, setExplored] = useState(false)
  const [insets, setInsets] = useState<Insets>({ left: 0, bottom: 0 })

  useEffect(() => {
    const update = () =>
      setInsets((old) => {
        const next = measure(investigating, expanded)
        return old.left === next.left && old.bottom === next.bottom ? old : next
      })
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [investigating, expanded])

  const data = state.status === 'success' ? state.data : null
  const places = useMemo<PlaceFeature[]>(() => {
    if (!data) return []
    const known = new Set(data.catalog.study_regions.features.map((f) => f.properties.region_id))
    return [...data.catalog.study_regions.features, ...data.no2Regional.extra_places.filter((f) => !known.has(f.properties.region_id))]
  }, [data])
  const trendIndex = useMemo(() => indexTrends(data?.trends ?? NO_TRENDS), [data])
  const extra = useMemo(() => extraSupport(data?.no2Regional ?? NO_REGIONAL_NO2, data?.comparisonWeather ?? NO_COMPARISON_WEATHER), [data])
  const place = places.find((p) => p.properties.region_id === placeId) ?? null
  const compareOptions = COMPARABLE.filter((id) => id !== placeId && places.some((p) => p.properties.region_id === id))
  const activeCompare = compare.filter((id) => compareOptions.includes(id))

  const openCase = useCallback(() => setView('case'), [])
  const selectPlace = useCallback((id: string) => {
    setView('case')
    setPlaceId(id)
  }, [])
  const toUkraine = useCallback(() => {
    setInvestigating(false)
    setPlaceId(null)
    setView('case')
  }, [setInvestigating])
  const backToEarth = useCallback(() => {
    setInvestigating(false)
    setPlaceId(null)
    setView('earth')
  }, [setInvestigating])
  const onExplore = useCallback(() => setExplored(true), [])

  const investigate = () => {
    if (!place || !data) return
    if (investigating) {
      setInvestigating(false)
      return
    }
    // NO₂ first when this place has it; otherwise the first variable it does have.
    const id = place.properties.region_id
    const usable = metrics.filter((m) => data.catalog.variables.some((v) => v.metric_id === m && hasDataFor(v, id, extra)))
    if (!usable.length) {
      const no2 = data.catalog.variables.find((v) => v.metric_id === NO2_METRIC)
      const first = no2 && hasDataFor(no2, id, extra) ? no2 : [...data.catalog.variables].sort((a, b) => a.display_order - b.display_order).find((v) => hasDataFor(v, id, extra))
      setMetrics(first ? [first.metric_id] : [])
    } else setMetrics(usable)
    setInvestigating(true)
  }

  const toggleCompare = (id: string) => setCompare((old) => (old.includes(id) ? old.filter((c) => c !== id) : old.length >= MAX_COMPARE ? old : [...old, id]))

  // Escape steps back one state: cards, then place, then the Earth.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (expanded) setExpanded(false)
      else if (investigating) setInvestigating(false)
      else if (placeId) setPlaceId(null)
      else if (view === 'case') setView('earth')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded, investigating, placeId, view, setInvestigating])

  const hint =
    view === 'earth'
      ? explored
        ? 'Choose the pin on Ukraine.'
        : 'Drag to turn the Earth. Scroll to zoom. Choose the pin on Ukraine.'
      : !placeId && state.status !== 'error'
        ? 'Choose a study box.'
        : null

  return (
    <main className={styles.page} data-view={view} data-investigating={investigating} data-expanded={expanded} data-testid="earth-page">
      <Starfield className={styles.stars} />
      <EarthMap view={view} places={places} placeId={placeId} insets={insets} onOpenCase={openCase} onSelectPlace={selectPlace} onExplore={onExplore} />

      <nav className={styles.nav} aria-label="Investigation">
        <div className={styles.left}>
          <h1 className={styles.brand}>The Last Trend Bender</h1>
          <ol className={styles.path} aria-label="Where you are">
            <li>
              <button type="button" onClick={backToEarth} aria-current={view === 'earth' ? 'page' : undefined} data-testid="nav-earth">Earth</button>
            </li>
            {view === 'case' ? (
              <li>
                <button type="button" onClick={toUkraine} aria-current={!placeId ? 'page' : undefined} data-testid="nav-ukraine">Ukraine</button>
              </li>
            ) : null}
            {place ? (
              <li>
                <span aria-current="page">{placeLabel(place.properties.region_id)}</span>
              </li>
            ) : null}
          </ol>
          {place && compareOptions.length ? (
            <div className={styles.compare} role="group" aria-label="Compare with">
              <span className={styles.label}>Compare</span>
              {compareOptions.map((id) => {
                const slot = activeCompare.indexOf(id)
                return (
                  <button key={id} type="button" className={styles.chip} aria-pressed={slot >= 0} onClick={() => toggleCompare(id)} data-testid={`compare-${id}`}>
                    <span className={styles.chipKey} style={{ background: slot >= 0 ? PLACE_COLORS[slot + 1] : 'transparent' }} aria-hidden="true" />
                    {placeLabel(id)}
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>
        <div className={styles.right}>
          <a className={styles.atlas} href="#/atlas">Atlas</a>
          <button type="button" className={styles.investigate} disabled={!place || !data} aria-pressed={investigating} onClick={investigate} data-testid="investigate">
            {investigating ? 'Close cards' : 'Investigate'}
          </button>
        </div>
      </nav>

      {hint ? <p className={styles.hint} data-testid="hint">{hint}</p> : null}
      {view === 'case' && state.status === 'error' ? (
        <div className={styles.error} role="alert">
          <p>The study places did not load. {state.error.message}</p>
          <button type="button" onClick={retry}>Try again</button>
        </div>
      ) : null}

      {investigating && place && data ? (
        <GlassCards place={place} compare={activeCompare} catalog={data.catalog} trendIndex={trendIndex} extra={extra} metrics={metrics} onMetrics={setMetrics} expanded={expanded} onExpanded={setExpanded} />
      ) : null}
    </main>
  )
}
