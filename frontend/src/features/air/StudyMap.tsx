import type { LatLngBoundsExpression } from 'leaflet'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import type { MapPayload } from '../../api/types'
import styles from './StudyMap.module.css'

function ResetView({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap()
  return (
    <button
      type="button"
      className={styles.reset}
      onClick={() => map.fitBounds(bounds, { padding: [28, 28] })}
    >
      Reset view
    </button>
  )
}

interface Props {
  map: MapPayload
}

/**
 * Study-area outline on a basemap. It is deliberately NOT a pollution heatmap:
 * panning and zooming change the view only, never the analysed region.
 */
export function StudyMap({ map }: Props) {
  const bounds = map.bounds as LatLngBoundsExpression
  return (
    <figure className={styles.figure}>
      <div className={styles.frame} data-testid="study-map">
        <MapContainer
          bounds={bounds}
          boundsOptions={{ padding: [28, 28] }}
          center={[map.center.lat, map.center.lon]}
          className={styles.map}
          scrollWheelZoom={false}
          attributionControl
          aria-label="Map of the Kyiv study area outline"
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            subdomains="abcd"
            maxZoom={18}
          />
          <GeoJSON
            data={map.sampled_grid_center_extent as never}
            style={{ color: '#4a5a6c', weight: 1.5, dashArray: '4 5', fill: false }}
          />
          <GeoJSON
            data={map.study_boundary as never}
            style={{ color: '#eb6834', weight: 3, fillColor: '#eb6834', fillOpacity: 0.08 }}
          />
          <ResetView bounds={bounds} />
        </MapContainer>
      </div>
      <figcaption className={styles.caption}>
        <span className={styles.legend}>
          <span className={styles.swatchSolid} aria-hidden="true" /> Study boundary
        </span>
        <span className={styles.legend}>
          <span className={styles.swatchDashed} aria-hidden="true" /> Sampled grid-cell centres
        </span>
        <p className={styles.note}>{map.note}</p>
      </figcaption>
    </figure>
  )
}
