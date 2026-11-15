import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, type Marker } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef, useState } from 'react'
import { placeLabel, type PlaceFeature } from '../investigate/catalog'
import { EARTH_HOME, earthStyle, MAP_MAX_ZOOM, MAP_MIN_ZOOM, UKRAINE_BOUNDS, UKRAINE_PIN } from './earthStyle'
import styles from './EarthMap.module.css'

/** Screen space covered by the evidence workspace, so the camera can keep the place in the free area. */
export interface Insets {
  left: number
  bottom: number
}

interface Props {
  view: 'earth' | 'case'
  places: PlaceFeature[]
  placeId: string | null
  insets: Insets
  onOpenCase: () => void
  onSelectPlace: (id: string) => void
  /** The reader moved the Earth by hand at least once. */
  onExplore: () => void
}

type Bounds = [number, number, number, number]

/** Degrees of longitude per second while the Earth idles: one turn in four minutes. */
const SPIN_DEG_PER_S = 1.5
const IDLE_BEFORE_SPIN_MS = 5000
const LAYERS_FOR_CASE = ['river-line', 'ukraine-glow', 'ukraine-line', 'boxes-fill', 'boxes-line']

const prefersReducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function boundsOf(place: PlaceFeature): Bounds {
  const ring = place.geometry.coordinates[0] ?? []
  const lons = ring.map((c) => c[0] as number)
  const lats = ring.map((c) => c[1] as number)
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]
}

/**
 * One map for the whole experience: the turning Earth, the flight to Ukraine and the close view of a study box.
 * The map never unmounts; the page's state only changes where the camera rests and which marks are shown.
 */
export function EarthMap({ view, places, placeId, insets, onOpenCase, onSelectPlace, onExplore }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markers = useRef<Marker[]>([])
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)
  // Latest props for handlers registered once on the map.
  const latest = useRef({ view, places, onOpenCase, onSelectPlace, onExplore })
  latest.current = { view, places, onOpenCase, onSelectPlace, onExplore }
  const spin = useRef({ allowed: view === 'earth', flying: false, lastTouch: 0 })

  // Create the map once.
  useEffect(() => {
    if (!container.current) return
    let map: MapLibreMap
    try {
      map = new maplibregl.Map({
        container: container.current,
        style: earthStyle,
        center: EARTH_HOME.center,
        zoom: EARTH_HOME.zoom,
        minZoom: MAP_MIN_ZOOM,
        maxZoom: MAP_MAX_ZOOM,
        maxPitch: 0,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        fadeDuration: 200,
      })
    } catch {
      setFailed(true)
      return
    }
    mapRef.current = map
    map.touchZoomRotate.disableRotation()
    map.keyboard.disableRotation()

    const touched = () => {
      spin.current.lastTouch = performance.now()
      latest.current.onExplore()
    }
    for (const event of ['mousedown', 'touchstart', 'wheel', 'dragstart'] as const) map.on(event, touched)

    const popup = new maplibregl.Popup({ closeButton: false, className: styles.popup, maxWidth: '260px', offset: 10 })
    map.on('click', (e) => {
      const hit = map.getLayer('boxes-fill') ? map.queryRenderedFeatures(e.point, { layers: ['boxes-fill'] }) : []
      if (latest.current.view === 'case' && hit.length) {
        // Boxes overlap (Kyiv city sits inside the northern belt): the smallest one under the pointer wins.
        const ids = new Set(hit.map((f) => String(f.properties?.region_id)))
        const smallest = latest.current.places.filter((p) => ids.has(p.properties.region_id)).sort((a, b) => a.properties.area_km2 - b.properties.area_km2)[0]
        if (smallest) {
          popup.remove()
          latest.current.onSelectPlace(smallest.properties.region_id)
          return
        }
      }
      const note = document.createElement('div')
      const title = document.createElement('strong')
      title.textContent = 'No study here yet'
      const body = document.createElement('p')
      body.textContent = 'You can look anywhere on Earth. Tested results exist for the Ukraine case only.'
      note.append(title, body)
      popup.setLngLat(e.lngLat).setDOMContent(note).addTo(map)
    })

    map.on('load', () => setReady(true))
    map.on('error', () => undefined) // A missing imagery tile is not a failure: the continents layer stays underneath.

    return () => {
      for (const m of markers.current) m.remove()
      markers.current = []
      popup.remove()
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Study boxes: geometry and which one is selected.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const source = map.getSource('boxes') as GeoJSONSource | undefined
    source?.setData({
      type: 'FeatureCollection',
      features: places.map((p) => ({ type: 'Feature', geometry: p.geometry, properties: { region_id: p.properties.region_id } })),
    })
  }, [ready, places])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    for (const p of places) map.setFeatureState({ source: 'boxes', id: p.properties.region_id }, { selected: p.properties.region_id === placeId })
    // Once a place is chosen, the other boxes step back so its edge is the one that reads.
    map.setPaintProperty('boxes-line', 'line-opacity', ['case', ['boolean', ['feature-state', 'selected'], false], 1, placeId ? 0.2 : 0.55])
  }, [ready, places, placeId])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    for (const id of LAYERS_FOR_CASE) map.setLayoutProperty(id, 'visibility', view === 'case' ? 'visible' : 'none')
  }, [ready, view])

  // Marks on the Earth: one case pin from orbit, the study places once the case is open.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    for (const m of markers.current) m.remove()
    markers.current = []
    const add = (el: HTMLElement, lngLat: [number, number], anchor: 'center' | 'left') => {
      markers.current.push(new maplibregl.Marker({ element: el, anchor, opacityWhenCovered: '0' }).setLngLat(lngLat).addTo(map))
    }
    if (view === 'earth') {
      const pin = document.createElement('button')
      pin.type = 'button'
      pin.className = styles.casePin ?? ''
      pin.setAttribute('data-testid', 'case-pin')
      pin.innerHTML = `<span class="${styles.casePinDot}" aria-hidden="true"></span><span class="${styles.casePinLabel}">Ukraine case</span>`
      pin.addEventListener('click', (e) => {
        e.stopPropagation()
        latest.current.onOpenCase()
      })
      add(pin, UKRAINE_PIN, 'left')
      return
    }
    for (const place of places) {
      const id = place.properties.region_id
      const el = document.createElement('button')
      el.type = 'button'
      el.className = styles.place ?? ''
      el.dataset.selected = String(id === placeId)
      el.dataset.testid = `place-${id}`
      el.setAttribute('aria-pressed', String(id === placeId))
      el.innerHTML = `<span class="${styles.placeDot}" aria-hidden="true"></span><span class="${styles.placeLabel}"></span>`
      ;(el.querySelector(`.${styles.placeLabel}`) as HTMLElement).textContent = placeLabel(id)
      el.addEventListener('click', (e) => {
        e.stopPropagation()
        latest.current.onSelectPlace(id)
      })
      add(el, [place.properties.center.lon, place.properties.center.lat], 'left')
    }
  }, [ready, view, places, placeId])

  // Camera: where it rests follows the page's state. Moving the map by hand never changes that state.
  const firstCamera = useRef(true)
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    spin.current.allowed = view === 'earth'
    if (firstCamera.current) {
      firstCamera.current = false
      if (view === 'earth') return // Already at home from the constructor.
    }
    const still = prefersReducedMotion()
    const go = (camera: { center: maplibregl.LngLatLike; zoom: number }, duration: number) => {
      spin.current.flying = true
      map.once('moveend', () => {
        spin.current.flying = false
        spin.current.lastTouch = performance.now()
      })
      if (still) map.jumpTo(camera)
      else map.flyTo({ ...camera, duration, curve: 1.25, essential: true })
    }
    if (view === 'earth') {
      go(EARTH_HOME, 2600)
      return
    }
    const place = placeId ? places.find((p) => p.properties.region_id === placeId) : undefined
    const [w, s, e, n] = place ? boundsOf(place) : UKRAINE_BOUNDS
    const edge = Math.round(Math.min(map.getContainer().clientWidth, map.getContainer().clientHeight) * (place ? 0.2 : 0.1))
    const camera = map.cameraForBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: { left: insets.left + edge, right: edge, top: edge, bottom: insets.bottom + edge }, maxZoom: 8.3 },
    )
    if (camera?.center !== undefined && camera.zoom !== undefined) go({ center: camera.center, zoom: camera.zoom }, place ? 2200 : 3200)
  }, [ready, view, placeId, places, insets.left, insets.bottom])

  // The Earth turns slowly while nobody is holding it.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || prefersReducedMotion()) return
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = Math.min(now - last, 100) / 1000
      last = now
      const s = spin.current
      if (s.allowed && !s.flying && now - s.lastTouch > IDLE_BEFORE_SPIN_MS && map.getZoom() < 3 && !map.isMoving()) {
        const c = map.getCenter()
        map.jumpTo({ center: [c.lng + SPIN_DEG_PER_S * dt, c.lat] })
      }
      frame = requestAnimationFrame(tick)
    }
    // Start turning at once on arrival; after a touch, wait for the idle time.
    spin.current.lastTouch = -IDLE_BEFORE_SPIN_MS
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [ready])

  return (
    <div className={styles.wrap}>
      <div ref={container} className={styles.map} data-testid="earth-map" data-ready={ready} aria-label="The Earth. Drag to turn it, scroll to zoom." role="application" />
      {failed ? (
        <p className={styles.failed} role="alert">
          This view needs WebGL, which this browser has switched off. <a href="#/atlas">Open the illustrated atlas instead.</a>
        </p>
      ) : null}
    </div>
  )
}
