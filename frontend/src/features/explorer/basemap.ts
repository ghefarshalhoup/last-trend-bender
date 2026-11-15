/**
 * Basemap tiles, no API key.
 * Primary: Esri World Street Map (place names in English).
 * Fallback: OpenStreetMap standard tiles (names in the local language), used
 * automatically if the primary tiles fail to load.
 * Both are for light use. For a public deployment, set VITE_TILE_URL and
 * VITE_TILE_ATTRIBUTION to a keyed provider. Attribution is always shown.
 */
const env = import.meta.env as Record<string, string | undefined>

export interface TileSource {
  id: string
  url: string
  attribution: string
  maxZoom: number
}

export const PRIMARY_BASEMAP: TileSource = {
  id: 'primary',
  url: env.VITE_TILE_URL || 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  attribution:
    env.VITE_TILE_ATTRIBUTION ||
    'Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, FAO, NOAA, USGS, &copy; OpenStreetMap contributors, and the GIS User Community',
  maxZoom: 18,
}

export const FALLBACK_BASEMAP: TileSource = {
  id: 'fallback',
  url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 18,
}

/** Switch to the fallback after this many failed tiles with none loaded. */
export const TILE_FAILURES_BEFORE_FALLBACK = 6
