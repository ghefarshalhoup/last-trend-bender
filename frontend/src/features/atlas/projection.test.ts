import { describe, expect, it } from 'vitest'
import { studyFixture } from '../../test/fixtures'
import { CITIES } from './AtlasBase'
import { ATLAS_HEIGHT, ATLAS_WIDTH, PROJECTION_PARAMS, projectLonLat, ringBounds, unprojectAtlasPoint } from './projection'

/** Textbook Lambert conformal conic (Snyder 1987, eq. 15-1 to 15-4), written independently of d3-geo. Unscaled. */
function lambert(lon: number, lat: number): [number, number] {
  const rad = Math.PI / 180
  const [p1, p2] = PROJECTION_PARAMS.parallels.map((p) => p * rad) as [number, number]
  const t = (phi: number) => Math.tan(Math.PI / 4 + phi / 2)
  const n = Math.log(Math.cos(p1) / Math.cos(p2)) / Math.log(t(p2) / t(p1))
  const F = (Math.cos(p1) * t(p1) ** n) / n
  const rho = F / t(lat * rad) ** n
  const theta = n * (lon - PROJECTION_PARAMS.centralMeridian) * rad
  return [rho * Math.sin(theta), -rho * Math.cos(theta)]
}
const dist = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1])

describe('atlas coordinate mapping', () => {
  it('round-trips every reference city through project and unproject', () => {
    for (const c of CITIES) {
      const [x, y] = projectLonLat(c.lon, c.lat)
      const [lon, lat] = unprojectAtlasPoint(x, y)
      expect(lon).toBeCloseTo(c.lon, 6)
      expect(lat).toBeCloseTo(c.lat, 6)
      expect(x).toBeGreaterThan(0)
      expect(x).toBeLessThan(ATLAS_WIDTH)
      expect(y).toBeGreaterThan(0)
      expect(y).toBeLessThan(ATLAS_HEIGHT)
    }
  })

  it('matches an independent Lambert conformal conic up to one uniform scale', () => {
    const ours = CITIES.map((c) => projectLonLat(c.lon, c.lat))
    const reference = CITIES.map((c) => lambert(c.lon, c.lat))
    const scale = dist(ours[0]!, ours[1]!) / dist(reference[0]!, reference[1]!)
    for (let i = 0; i < CITIES.length; i += 1) {
      for (let j = i + 1; j < CITIES.length; j += 1) {
        // every city-to-city distance agrees to a thousandth of an atlas unit
        expect(dist(ours[i]!, ours[j]!)).toBeCloseTo(dist(reference[i]!, reference[j]!) * scale, 3)
      }
    }
  })

  it('keeps north up along the central meridian', () => {
    const south = projectLonLat(PROJECTION_PARAMS.centralMeridian, 45)
    const north = projectLonLat(PROJECTION_PARAMS.centralMeridian, 52)
    expect(north[0]).toBeCloseTo(south[0], 6)
    expect(north[1]).toBeLessThan(south[1])
  })

  it('places the Kyiv study box from the API around Kyiv at its true proportions', () => {
    const ring = studyFixture.map.study_boundary.geometry.coordinates[0] as number[][]
    const b = ringBounds(ring)
    const kyiv = projectLonLat(studyFixture.map.center.lon, studyFixture.map.center.lat)
    expect(kyiv[0]).toBeGreaterThan(b.minX)
    expect(kyiv[0]).toBeLessThan(b.maxX)
    expect(kyiv[1]).toBeGreaterThan(b.minY)
    expect(kyiv[1]).toBeLessThan(b.maxY)
    expect(Math.abs((b.minX + b.maxX) / 2 - kyiv[0])).toBeLessThan(0.5)
    // 0.5° of longitude at 50.45°N is cos(50.45°) = 0.637 times 0.5° of latitude
    const [[south, west], [north, east]] = studyFixture.map.bounds
    const expected = ((east - west) * Math.cos((50.45 * Math.PI) / 180)) / (north - south)
    expect((b.maxX - b.minX) / (b.maxY - b.minY)).toBeCloseTo(expected, 1)
  })
})
