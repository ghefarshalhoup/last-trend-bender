import type { FeatureCollection, MultiLineString, MultiPolygon, Polygon, Position } from 'geojson'
import type { StyleSpecification } from 'maplibre-gl'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import landTopology from 'world-atlas/land-110m.json'
import atlasGeo from '../atlas/geo/atlas-geo.json'

/**
 * NASA Blue Marble (shaded relief and bathymetry) from the Global Imagery Browse Services.
 * Web Mercator endpoint, tile matrix set GoogleMapsCompatible_Level8: about 500 m per pixel at
 * its deepest level, so it is an orbital and regional picture, not a street-level one.
 */
export const NASA_BLUE_MARBLE_TILES =
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg'

/** The imagery stops adding detail here; beyond it the picture only gets softer. */
export const IMAGERY_MAX_ZOOM = 8
export const MAP_MAX_ZOOM = 9.2
export const MAP_MIN_ZOOM = 1

type Land = FeatureCollection<Polygon | MultiPolygon>

/**
 * A ring that crosses the antimeridian jumps from +180° to −180°, which draws a sliver right around the world
 * (Chukotka and Fiji do this). Carrying the longitude past 180° keeps the ring in one piece.
 * Antarctica reaches the pole along both edges on purpose and is left as it is.
 */
function unwrapRing(ring: Position[]): Position[] {
  if (ring.some((p) => (p[1] as number) < -85)) return ring
  let offset = 0
  return ring.map((point, i) => {
    const prev = ring[i - 1]
    if (prev) {
      const step = (point[0] as number) - (prev[0] as number)
      if (step > 180) offset -= 360
      else if (step < -180) offset += 360
    }
    return [(point[0] as number) + offset, point[1] as number]
  })
}

/** Coarse continents (Natural Earth 1:110m). Drawn under the imagery, so the Earth is never blank while tiles load or fail. */
const rawLand = feature(landTopology as unknown as Topology, (landTopology as unknown as Topology).objects.land as GeometryCollection) as unknown as Land
const land: Land = {
  type: 'FeatureCollection',
  features: rawLand.features.map((f) => ({
    ...f,
    geometry:
      f.geometry.type === 'Polygon'
        ? { type: 'Polygon', coordinates: f.geometry.coordinates.map(unwrapRing) }
        : { type: 'MultiPolygon', coordinates: f.geometry.coordinates.map((polygon) => polygon.map(unwrapRing)) },
  })),
}

interface AtlasFeature {
  type: 'Feature'
  properties: { kind: string; name: string }
  geometry: MultiPolygon | Polygon | MultiLineString
}
const atlasFeatures = (atlasGeo as unknown as { features: AtlasFeature[] }).features
const ofKind = (kind: string): FeatureCollection => ({
  type: 'FeatureCollection',
  features: atlasFeatures.filter((f) => f.properties.kind === kind).map((f) => ({ type: 'Feature', properties: { name: f.properties.name }, geometry: f.geometry })),
})

/** Ukraine's outline, from the same Natural Earth file the illustrated atlas is fitted to. */
export const UKRAINE_OUTLINE = ofKind('ukraine')
/**
 * The main rivers: quiet local bearings once the camera is down at the case (the Dnieper runs through the Kyiv box).
 * The file's neighbour countries are not drawn: they are cut to the painted atlas's frame, so their straight cut edges would read as borders.
 */
const RIVERS = ofKind('river')

/** West, south, east, north. */
export const UKRAINE_BOUNDS: [number, number, number, number] = [22.1, 44.3, 40.3, 52.4]
/** Where the case pin sits on the globe. */
export const UKRAINE_PIN: [number, number] = [31.4, 49.0]
/** The opening view: Europe and Africa facing the reader, Ukraine in the upper half. */
export const EARTH_HOME: { center: [number, number]; zoom: number } = { center: [22, 28], zoom: 1.75 }

export const EMPTY_COLLECTION: FeatureCollection = { type: 'FeatureCollection', features: [] }

export const earthStyle: StyleSpecification = {
  version: 8,
  projection: { type: 'globe' },
  // The thin blue limb seen from orbit; it fades as the camera comes down to a region.
  sky: { 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 0.5, 2.5, 0.5, 4.2, 0] },
  light: { anchor: 'map', position: [1.5, 90, 80] },
  sources: {
    land: { type: 'geojson', data: land },
    nasa: {
      type: 'raster',
      tiles: [NASA_BLUE_MARBLE_TILES],
      tileSize: 256,
      minzoom: 1,
      maxzoom: IMAGERY_MAX_ZOOM,
      attribution: 'Imagery: NASA GIBS, Blue Marble',
    },
    ukraine: { type: 'geojson', data: UKRAINE_OUTLINE },
    rivers: { type: 'geojson', data: RIVERS },
    boxes: { type: 'geojson', data: EMPTY_COLLECTION, promoteId: 'region_id' },
  },
  layers: [
    { id: 'ocean', type: 'background', paint: { 'background-color': '#0a2342' } },
    { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#3c5a45', 'fill-antialias': false } },
    { id: 'nasa', type: 'raster', source: 'nasa', paint: { 'raster-fade-duration': 400, 'raster-saturation': -0.08 } },
    {
      id: 'river-line',
      type: 'line',
      source: 'rivers',
      layout: { 'line-join': 'round', 'line-cap': 'round', visibility: 'none' },
      paint: { 'line-color': '#a9d3f5', 'line-opacity': 0.75, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 8.5, 2.6] },
    },
    {
      id: 'ukraine-glow',
      type: 'line',
      source: 'ukraine',
      layout: { 'line-join': 'round', visibility: 'none' },
      paint: { 'line-color': '#f2cf7a', 'line-width': 7, 'line-blur': 7, 'line-opacity': 0.45 },
    },
    {
      id: 'ukraine-line',
      type: 'line',
      source: 'ukraine',
      layout: { 'line-join': 'round', visibility: 'none' },
      paint: { 'line-color': '#f7e3a6', 'line-width': 1.4 },
    },
    {
      id: 'boxes-fill',
      type: 'fill',
      source: 'boxes',
      layout: { visibility: 'none' },
      paint: { 'fill-color': '#f7e3a6', 'fill-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.16, 0] },
    },
    {
      id: 'boxes-line',
      type: 'line',
      source: 'boxes',
      layout: { visibility: 'none' },
      paint: {
        'line-color': ['case', ['boolean', ['feature-state', 'selected'], false], '#fff6d6', '#f7e3a6'],
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2.4, 1],
        'line-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0.55],
        'line-dasharray': [3, 2],
      },
    },
  ],
}
