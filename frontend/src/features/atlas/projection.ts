import { geoConicConformal } from 'd3-geo'

/**
 * The atlas's single coordinate mapping. Every layer, for every element, turns
 * longitude/latitude into atlas units through `projectLonLat` and nothing else,
 * so a real place lands on the same spot whichever element is selected.
 *
 * Projection: Lambert conformal conic (d3-geo `geoConicConformal`), standard
 * parallels 46°N and 51°N, central meridian 31.5°E. It is fitted once to a fixed
 * geographic box around Ukraine, not to any dataset, so the mapping never moves.
 *
 * Atlas units are the SVG viewBox (1600 × 1000). The base map and all overlays
 * share that viewBox, so they scale together when the screen resizes.
 */
export const ATLAS_WIDTH = 1600
export const ATLAS_HEIGHT = 1000

/** Geographic box the frame is fitted to: Ukraine including Crimea, with a small margin. */
export const FIT_BOX = { west: 22.0, south: 44.2, east: 40.35, north: 52.5 } as const
/** Where that box sits inside the viewBox, leaving room for the decorative border. */
const FRAME: [[number, number], [number, number]] = [[190, 70], [1520, 860]]

export const PROJECTION_PARAMS = { parallels: [46, 51] as [number, number], centralMeridian: 31.5 } as const

function boxOutline(steps = 40): [number, number][] {
  const { west, south, east, north } = FIT_BOX
  const points: [number, number][] = []
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps
    points.push([west + (east - west) * t, south], [west + (east - west) * t, north])
    points.push([west, south + (north - south) * t], [east, south + (north - south) * t])
  }
  return points
}

const projection = geoConicConformal()
  .parallels(PROJECTION_PARAMS.parallels)
  .rotate([-PROJECTION_PARAMS.centralMeridian, 0])
  .fitExtent(FRAME, { type: 'MultiPoint', coordinates: boxOutline() })

export type AtlasPoint = [number, number]

/** Longitude/latitude (degrees) → atlas units. */
export function projectLonLat(lon: number, lat: number): AtlasPoint {
  const point = projection([lon, lat])
  if (!point) throw new Error(`Cannot project ${lon}, ${lat}`)
  return point
}

/** Atlas units → longitude/latitude (degrees). */
export function unprojectAtlasPoint(x: number, y: number): [number, number] {
  const lonLat = projection.invert?.([x, y])
  if (!lonLat) throw new Error(`Cannot invert ${x}, ${y}`)
  return lonLat
}

const round = (n: number) => Math.round(n * 10) / 10

/** A line of [lon, lat] positions as SVG path data. Vertices are projected one by one. */
export function linePath(positions: number[][], close = false): string {
  let d = ''
  for (const [lon, lat] of positions) {
    if (lon === undefined || lat === undefined) continue
    const [x, y] = projectLonLat(lon, lat)
    d += `${d ? 'L' : 'M'}${round(x)} ${round(y)}`
  }
  return close ? `${d}Z` : d
}

/**
 * A GeoJSON polygon ring as SVG path data. Long edges are subdivided first so a
 * straight edge in degrees follows the projection's curve instead of cutting across it.
 */
export function ringPath(ring: number[][], maxStepDeg = 0.05): string {
  const dense: number[][] = []
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i] as [number, number]
    const [x2, y2] = ring[i + 1] as [number, number]
    const steps = Math.max(1, Math.ceil(Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1)) / maxStepDeg))
    for (let s = 0; s < steps; s += 1) dense.push([x1 + ((x2 - x1) * s) / steps, y1 + ((y2 - y1) * s) / steps])
  }
  return linePath(dense, true)
}

/** Bounding box, in atlas units, of a GeoJSON polygon ring. */
export function ringBounds(ring: number[][]): { minX: number; minY: number; maxX: number; maxY: number } {
  const pts = ring.map(([lon, lat]) => projectLonLat(lon as number, lat as number))
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) }
}

/** Atlas units → percentage of the frame, for HTML positioned over the map. */
export function atlasPercent(x: number, y: number): { left: string; top: string } {
  return { left: `${(x / ATLAS_WIDTH) * 100}%`, top: `${(y / ATLAS_HEIGHT) * 100}%` }
}
