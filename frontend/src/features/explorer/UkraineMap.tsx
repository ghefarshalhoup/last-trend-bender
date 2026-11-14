import L, { type LatLngBoundsExpression } from 'leaflet'
import { useEffect, useRef, useState } from 'react'
import { GeoJSON, MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { MapPayload } from '../../api/types'
import { FALLBACK_BASEMAP, PRIMARY_BASEMAP, TILE_FAILURES_BEFORE_FALLBACK } from './basemap'
import styles from './UkraineMap.module.css'

/** Country view including Crimea with some surrounding geography. This is a camera, not data. */
export const UKRAINE_BOUNDS: LatLngBoundsExpression = [
  [43.6, 21.5],
  [52.9, 41.0],
]

export type MapCommand = { kind: 'ukraine' | 'kyiv'; nonce: number }

function Controller({ command, kyivBounds }: { command: MapCommand; kyivBounds: LatLngBoundsExpression | null }) {
  const map = useMap()

  // The map container changes size when the panel opens or closes.
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ animate: false }))
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])

  // View commands only move the camera. They never touch data or selection.
  useEffect(() => {
    if (command.nonce === 0) return
    map.invalidateSize({ animate: false })
    if (command.kind === 'kyiv' && kyivBounds) map.fitBounds(kyivBounds, { padding: [32, 32], maxZoom: 11 })
    else map.fitBounds(UKRAINE_BOUNDS, { padding: [12, 12] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command.nonce])

  return null
}

interface Props {
  /** Present only while Air is selected and its study has loaded. */
  map: MapPayload | null
  command: MapCommand
  /** Result line shown under the study label, or null for the label alone. */
  resultLabel: string | null
  onExplore: () => void
}

const pinIcon = L.divIcon({ className: styles.pin, html: '<span></span>', iconSize: [22, 22], iconAnchor: [11, 11] })

export function UkraineMap({ map, command, resultLabel, onExplore }: Props) {
  const [source, setSource] = useState(PRIMARY_BASEMAP)
  const tiles = useRef({ loaded: 0, failed: 0 })
  const kyivBounds = map ? (map.bounds as LatLngBoundsExpression) : null
  return (
    <div className={styles.frame} data-testid="ukraine-map">
      <MapContainer
        bounds={UKRAINE_BOUNDS}
        boundsOptions={{ padding: [12, 12] }}
        minZoom={4}
        className={styles.map}
        scrollWheelZoom
        attributionControl
        aria-label="Map of Ukraine"
      >
        <TileLayer
          key={source.id}
          url={source.url}
          attribution={source.attribution}
          maxZoom={source.maxZoom}
          eventHandlers={{
            tileload: () => { tiles.current.loaded += 1 },
            tileerror: () => {
              tiles.current.failed += 1
              if (source.id === 'primary' && tiles.current.loaded === 0 && tiles.current.failed >= TILE_FAILURES_BEFORE_FALLBACK) {
                setSource(FALLBACK_BASEMAP)
              }
            },
          }}
        />
        <Controller command={command} kyivBounds={kyivBounds} />
        {map ? (
          <>
            <GeoJSON
              key="kyiv-boundary"
              data={map.study_boundary as never}
              style={{ color: '#8a6a2f', weight: 3, fillColor: '#b8891a', fillOpacity: 0.3 }}
              eventHandlers={{ click: onExplore }}
            />
            <Marker position={[map.center.lat, map.center.lon]} icon={pinIcon} title="Explore Kyiv NO₂ study" alt="Explore Kyiv NO₂ study" eventHandlers={{ click: onExplore, keydown: (e) => { const k = (e.originalEvent as KeyboardEvent).key; if (k === 'Enter' || k === ' ') onExplore() } }}>
              <Tooltip permanent direction="right" offset={[14, 0]} className={styles.label}>
                <strong>Kyiv · NO₂ study</strong>
                {resultLabel ? <span className={styles.result}>{resultLabel}</span> : null}
              </Tooltip>
            </Marker>
          </>
        ) : null}
      </MapContainer>
    </div>
  )
}
