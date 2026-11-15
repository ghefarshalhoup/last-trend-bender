import { memo } from 'react'
import geoJson from './geo/atlas-geo.json'
import { ATLAS_VIEW, linePath, projectLonLat } from './projection'
import styles from './AtlasBase.module.css'
import paintedBase from './assets/painted-base.webp'

/**
 * The fixed base map. A painted illustration (AI-generated, marked on the map) is warped onto the
 * atlas projection: its six city dots and its border were fitted to the real ones (median border
 * offset about 5 units of 1600; see docs/base-map.md). The vector geography (Natural Earth 1:10m)
 * stays underneath for the edges the painting does not cover. Place boxes and pins are drawn
 * from true coordinates on top, so evidence never depends on the painting. It never pans or zooms.
 */
interface GeoFeature {
  properties: { kind: 'ukraine' | 'neighbour' | 'river'; name: string }
  geometry: { type: string; coordinates: unknown }
}
const features = (geoJson as unknown as { features: GeoFeature[] }).features

const polygonPath = (f: GeoFeature) =>
  (f.geometry.coordinates as number[][][][]).map((poly) => poly.map((ring) => linePath(ring, true)).join('')).join('')

const UKRAINE = features.filter((f) => f.properties.kind === 'ukraine').map(polygonPath).join('')
const NEIGHBOURS = features.filter((f) => f.properties.kind === 'neighbour').map(polygonPath)

/** Orientation labels at their real coordinates. */
export const CITIES = [
  { name: 'Kyiv', lon: 30.5234, lat: 50.4501, capital: true },
  { name: 'Lviv', lon: 24.0297, lat: 49.8397 },
  { name: 'Kharkiv', lon: 36.2304, lat: 49.9935 },
  { name: 'Dnipro', lon: 35.0462, lat: 48.4647 },
  { name: 'Donetsk', lon: 37.8028, lat: 48.0159 },
  { name: 'Odesa', lon: 30.7233, lat: 46.4825 },
] as const

function AtlasBaseImpl() {
  const V = ATLAS_VIEW
  const ukraineLabel = projectLonLat(31.2, 49.0)
  const sea = projectLonLat(32.0, 44.0)
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
        <clipPath id="atlas-clip"><rect x={V.x} y={V.y} width={V.w} height={V.h} /></clipPath>
      </defs>
      <g clipPath="url(#atlas-clip)">
        <rect x={V.x} y={V.y} width={V.w} height={V.h} className={styles.sea} />
        <rect x={V.x} y={V.y} width={V.w} height={V.h} fill="url(#atlas-waves)" />
        {NEIGHBOURS.map((d, i) => <path key={i} d={d} className={styles.shore} />)}
        <path d={UKRAINE} className={styles.shore} />
        {NEIGHBOURS.map((d, i) => <path key={i} d={d} className={styles.neighbour} />)}
        <path d={UKRAINE} className={styles.ukraine} />
        <image href={paintedBase} x={V.x} y={V.y} width={V.w} height={V.h} preserveAspectRatio="none" data-testid="painted-base" />
        {/* The painting carries the border and rivers; the true outline stays for alignment, invisible. Labels are ours, at true coordinates. */}
        <path d={UKRAINE} className={styles.trueOutline} data-testid="ukraine-outline" />
        <text x={ukraineLabel[0]} y={ukraineLabel[1]} className={styles.country}>UKRAINE</text>
        <text x={sea[0]} y={sea[1]} className={styles.seaLabel}>BLACK SEA</text>
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
        <text x={V.x + V.w / 2} y={V.y + V.h - 22} className={styles.aiMark} data-testid="ai-mark">AI-generated illustration · aligned to true coordinates</text>
        <rect x={V.x + 6} y={V.y + 6} width={V.w - 12} height={V.h - 12} className={styles.frameOuter} />
      </g>
    </g>
  )
}

export const AtlasBase = memo(AtlasBaseImpl)
