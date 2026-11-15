import { useCallback, useEffect, useMemo, useState } from 'react'
import { useApiResource } from '../../api/useApiResource'
import { extraSupport, fetchComparisonWeather, fetchNo2Regional, fetchVariableCatalog, NO_COMPARISON_WEATHER, NO_REGIONAL_NO2, placeLabel, type PlaceFeature } from '../investigate/catalog'
import { fetchTrends, indexTrends, type TrendsPayload } from '../investigate/series'
import { EarthMap, type Insets } from './EarthMap'
import styles from './EarthPage.module.css'
import { Starfield } from './Starfield'
import { Workspace } from './Workspace'

type View = 'earth' | 'case'

const NO_TRENDS: TrendsPayload = { status: 'not_available', results: [] }
const NARROW = 860
const FEATURED_PLACE = 'kyiv_no2_box'

async function loadEarth(signal: AbortSignal) {
  const [catalog, trends, no2Regional, comparisonWeather] = await Promise.all([
    fetchVariableCatalog(signal),
    fetchTrends(signal).catch(() => NO_TRENDS),
    fetchNo2Regional(signal).catch(() => NO_REGIONAL_NO2),
    fetchComparisonWeather(signal).catch(() => NO_COMPARISON_WEATHER),
  ])
  return { catalog, trends, no2Regional, comparisonWeather }
}

/** The same sizes the stylesheets use, so the camera knows which part of the screen is still free. */
function measure(view: View, workspace: boolean): Insets {
  if (typeof window === 'undefined' || view === 'earth') return { left: 0, bottom: 0 }
  const w = window.innerWidth
  const h = window.innerHeight
  if (w <= NARROW) return { left: 0, bottom: Math.round(h * (workspace ? 0.56 : 0.42)) }
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  return workspace ? { left: Math.round(Math.min(Math.max(26 * rem, w * 0.42), 40 * rem)), bottom: 0 } : { left: Math.round(23 * rem), bottom: 0 }
}

/**
 * `#/earth`: a freely explorable Earth that becomes an investigation workspace.
 * Three resting states: the Earth, the Ukraine case with its study places, and one place with its evidence open.
 */
export default function EarthPage() {
  const { state, retry } = useApiResource(loadEarth)
  const [view, setView] = useState<View>('earth')
  const [placeId, setPlaceId] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState(false)
  const [explored, setExplored] = useState(false)
  const [insets, setInsets] = useState<Insets>({ left: 0, bottom: 0 })

  useEffect(() => {
    const update = () =>
      setInsets((old) => {
        const next = measure(view, workspace)
        return old.left === next.left && old.bottom === next.bottom ? old : next
      })
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [view, workspace])

  const data = state.status === 'success' ? state.data : null
  const places = useMemo<PlaceFeature[]>(() => {
    if (!data) return []
    const known = new Set(data.catalog.study_regions.features.map((f) => f.properties.region_id))
    const all = [...data.catalog.study_regions.features, ...data.no2Regional.extra_places.filter((f) => !known.has(f.properties.region_id))]
    // Kyiv first, then the rest of Ukraine, then the comparison cities outside it.
    const rank = (p: PlaceFeature) => (p.properties.region_id === FEATURED_PLACE ? 0 : p.properties.is_ukraine_study_area ? 1 : 2)
    return [...all].sort((a, b) => rank(a) - rank(b))
  }, [data])
  const trendIndex = useMemo(() => indexTrends(data?.trends ?? NO_TRENDS), [data])
  const extra = useMemo(() => extraSupport(data?.no2Regional ?? NO_REGIONAL_NO2, data?.comparisonWeather ?? NO_COMPARISON_WEATHER), [data])
  const place = places.find((p) => p.properties.region_id === placeId) ?? null

  const openCase = useCallback(() => setView('case'), [])
  const selectPlace = useCallback((id: string) => {
    setView('case')
    setPlaceId(id)
  }, [])
  const backToEarth = useCallback(() => {
    setWorkspace(false)
    setPlaceId(null)
    setView('earth')
  }, [])
  const onExplore = useCallback(() => setExplored(true), [])

  // Escape steps back one state: workspace, then place, then the Earth.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (workspace) setWorkspace(false)
      else if (placeId) setPlaceId(null)
      else if (view === 'case') setView('earth')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [workspace, placeId, view])

  return (
    <main className={styles.page} data-view={view} data-workspace={workspace} data-testid="earth-page">
      <Starfield className={styles.stars} />
      <EarthMap view={view} places={places} placeId={placeId} insets={insets} onOpenCase={openCase} onSelectPlace={selectPlace} onExplore={onExplore} />

      {view === 'earth' ? (
        <>
          <header className={styles.title}>
            <h1>The Last Trend Bender</h1>
            <p>Environmental fingerprints of war, read from NASA’s record of the Earth.</p>
          </header>
          <div className={styles.launch}>
            <p>One case is open on this Earth.</p>
            <button type="button" className={styles.primaryOnNight} onClick={openCase} data-testid="open-case">Fly to Ukraine, 2022</button>
          </div>
          {explored ? null : <p className={styles.hint}>Drag to turn the Earth. Scroll to zoom.</p>}
        </>
      ) : null}

      {view === 'case' && !workspace ? (
        <>
          <button type="button" className={styles.back} onClick={backToEarth} data-testid="back-to-earth">Back to Earth</button>
          <aside className={styles.card} aria-label="Ukraine case" data-testid="case-card">
            <h2>Ukraine, 2022</h2>
            {state.status === 'loading' || state.status === 'idle' ? <p className={styles.cardNote} role="status">Loading the study places…</p> : null}
            {state.status === 'error' ? (
              <div className={styles.cardNote} role="alert">
                <p>The study places did not load. {state.error.message}</p>
                <button type="button" className={styles.primary} onClick={retry}>Try again</button>
              </div>
            ) : null}
            {data && !place ? <p className={styles.cardNote}>Each dashed box is a place whose satellite record was tested. Choose one here or on the map.</p> : null}
            {data ? (
              <ul className={styles.places}>
                {places.map((p) => {
                  const id = p.properties.region_id
                  return (
                    <li key={id}>
                      <button type="button" aria-pressed={id === placeId} onClick={() => selectPlace(id)} data-testid={`list-place-${id}`}>
                        <span>{placeLabel(id)}</span>
                        {p.properties.is_ukraine_study_area ? null : <span className={styles.tag}>comparison</span>}
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : null}
            {place ? (
              <div className={styles.chosen}>
                <p>
                  {placeLabel(place.properties.region_id)}: a study box of about {Math.round(place.properties.area_km2).toLocaleString('en-GB')} km²
                  {place.properties.is_ukraine_study_area ? '.' : ', outside Ukraine, kept for comparison.'}
                </p>
                <button type="button" className={styles.primary} onClick={() => setWorkspace(true)} data-testid="start-investigation">Start investigation</button>
              </div>
            ) : null}
          </aside>
        </>
      ) : null}

      {workspace && place && data ? (
        <Workspace place={place} catalog={data.catalog} trendIndex={trendIndex} extra={extra} onClose={() => setWorkspace(false)} onBackToEarth={backToEarth} />
      ) : null}

      <a className={styles.atlasLink} href="#/atlas">Illustrated atlas</a>
    </main>
  )
}
