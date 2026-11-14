import { memo } from 'react'
import geoJson from './geo/atlas-geo.json'
import { ATLAS_HEIGHT, ATLAS_WIDTH, linePath, projectLonLat } from './projection'
import styles from './AtlasBase.module.css'

/**
 * The fixed base map: real geography (Natural Earth 1:10m) drawn through the
 * atlas projection, in an inked-parchment style. It never pans or zooms.
 * Everything here is decoration or orientation; evidence comes from layers.
 */
interface GeoFeature {
  properties: { kind: 'ukraine' | 'neighbour' | 'river'; name: string }
  geometry: { type: string; coordinates: unknown }
}
const features = (geoJson as unknown as { features: GeoFeature[] }).features

const polygonPath = (f: GeoFeature) =>
  (f.geometry.coordinates as number[][][][]).map((poly) => poly.map((ring) => linePath(ring, true)).join('')).join('')
const riverPath = (f: GeoFeature) => (f.geometry.coordinates as number[][][]).map((line) => linePath(line)).join('')

const UKRAINE = features.filter((f) => f.properties.kind === 'ukraine').map(polygonPath).join('')
const NEIGHBOURS = features.filter((f) => f.properties.kind === 'neighbour').map(polygonPath)
const RIVERS = features.filter((f) => f.properties.kind === 'river').map((f) => ({ name: f.properties.name, d: riverPath(f) }))

/** Orientation labels at their real coordinates. */
export const CITIES = [
  { name: 'Kyiv', lon: 30.5234, lat: 50.4501, capital: true },
  { name: 'Lviv', lon: 24.0297, lat: 49.8397 },
  { name: 'Kharkiv', lon: 36.2304, lat: 49.9935 },
  { name: 'Dnipro', lon: 35.0462, lat: 48.4647 },
  { name: 'Donetsk', lon: 37.8028, lat: 48.0159 },
  { name: 'Odesa', lon: 30.7233, lat: 46.4825 },
] as const

// Decorative glyphs, placed where the terrain really is (Carpathians, Crimean Mountains, northern forests).
const MOUNTAINS: [number, number][] = [
  [22.9, 48.75], [23.4, 48.55], [23.9, 48.4], [24.4, 48.25], [24.9, 48.05], [23.6, 48.85], [24.2, 48.65], [34.1, 44.62], [34.6, 44.75],
]
const FORESTS: [number, number][] = [
  [24.9, 51.3], [25.8, 51.45], [26.7, 51.35], [27.6, 51.3], [28.5, 51.2], [29.3, 51.05], [27.1, 50.85], [31.9, 51.75],
  [32.7, 51.9], [33.5, 51.75], [24.6, 49.0], [25.2, 48.6], [37.6, 49.15], [38.3, 49.3], [29.0, 49.0], [31.9, 49.2],
]

function AtlasBaseImpl() {
  const ukraineLabel = projectLonLat(31.7, 48.95)
  const sea = projectLonLat(31.6, 44.75)
  const azov = projectLonLat(36.6, 46.05)
  return (
    <g data-testid="atlas-base">
      <defs>
        <filter id="atlas-paper" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.012 0.018" numOctaves="4" seed="7" result="noise" />
          <feColorMatrix type="matrix" values="0 0 0 0 0.35  0 0 0 0 0.26  0 0 0 0 0.14  0 0 0 0.55 -0.12" />
        </filter>
        <pattern id="atlas-waves" width="34" height="16" patternUnits="userSpaceOnUse">
          <path d="M0 11q8.5-9 17 0t17 0" className={styles.wave} />
        </pattern>
        <clipPath id="atlas-clip"><rect width={ATLAS_WIDTH} height={ATLAS_HEIGHT} /></clipPath>
      </defs>
      <g clipPath="url(#atlas-clip)">
        <rect width={ATLAS_WIDTH} height={ATLAS_HEIGHT} className={styles.sea} />
        <rect width={ATLAS_WIDTH} height={ATLAS_HEIGHT} fill="url(#atlas-waves)" />
        {NEIGHBOURS.map((d, i) => <path key={i} d={d} className={styles.shore} />)}
        <path d={UKRAINE} className={styles.shore} />
        {NEIGHBOURS.map((d, i) => <path key={i} d={d} className={styles.neighbour} />)}
        <path d={UKRAINE} className={styles.ukraine} />
        {RIVERS.map((r, i) => <path key={i} d={r.d} className={styles.river} data-major={r.name === 'Dnieper'} />)}
        {FORESTS.map(([lon, lat], i) => {
          const [x, y] = projectLonLat(lon, lat)
          return <path key={i} transform={`translate(${x} ${y})`} d="M-9 6l5-13 4 9 4-11 6 15z" className={styles.forest} />
        })}
        {MOUNTAINS.map(([lon, lat], i) => {
          const [x, y] = projectLonLat(lon, lat)
          return (
            <g key={i} transform={`translate(${x} ${y})`}>
              <path d="M-15 8L-3-11 2-3 6-9 16 8z" className={styles.mountain} />
              <path d="M-3-11l3 9-4 5" className={styles.ridge} />
            </g>
          )
        })}
        <path d={UKRAINE} className={styles.borderGlow} />
        <path d={UKRAINE} className={styles.border} data-testid="ukraine-outline" />
        <text x={ukraineLabel[0]} y={ukraineLabel[1]} className={styles.country}>UKRAINE</text>
        <text x={sea[0]} y={sea[1]} className={styles.seaLabel}>BLACK SEA</text>
        <text x={azov[0]} y={azov[1]} className={styles.seaLabelSmall}>Sea of Azov</text>
        {CITIES.map((c) => {
          const [x, y] = projectLonLat(c.lon, c.lat)
          return (
            <g key={c.name} data-testid={`city-${c.name}`} data-x={x} data-y={y}>
              {'capital' in c ? <circle cx={x} cy={y} r={9} className={styles.capitalRing} /> : null}
              <circle cx={x} cy={y} r={5} className={styles.cityDot} />
              <text x={x + 14} y={y + 7} className={styles.city}>{c.name}</text>
            </g>
          )
        })}
        <rect width={ATLAS_WIDTH} height={ATLAS_HEIGHT} filter="url(#atlas-paper)" className={styles.paper} />
        <rect x="10" y="10" width={ATLAS_WIDTH - 20} height={ATLAS_HEIGHT - 20} className={styles.frameOuter} />
        <rect x="20" y="20" width={ATLAS_WIDTH - 40} height={ATLAS_HEIGHT - 40} className={styles.frameInner} />
      </g>
    </g>
  )
}

export const AtlasBase = memo(AtlasBaseImpl)
