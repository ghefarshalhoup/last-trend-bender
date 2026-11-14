/**
 * Basemap tiles. OpenStreetMap's standard tiles need no API key, which suits a
 * hackathon demo. Their usage policy forbids heavy or commercial traffic, so for
 * anything public set VITE_TILE_URL / VITE_TILE_ATTRIBUTION to a keyed provider
 * (MapTiler, Stadia, Esri, your own tile server...). Attribution is always shown.
 */
const env = import.meta.env as Record<string, string | undefined>

export const BASEMAP = {
  url: env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution:
    env.VITE_TILE_ATTRIBUTION ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 18,
} as const
