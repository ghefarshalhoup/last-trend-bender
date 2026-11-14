/**
 * Fixed diverging scale for "percent change against the baseline".
 * Blue = lower than baseline, red = higher, palest steps next to zero.
 * The domain never changes with month or baseline, so colours are comparable
 * across every selection.
 */
export const SCALE_EDGES = [-50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50] as const
export const SCALE_COLOURS = [
  '#1d4f91', '#2f6fb3', '#5a93cc', '#93b8de', '#c9d9ea',
  '#f0d3c8', '#e6ab98', '#d98068', '#c7563f', '#a8321f',
] as const

/** Bin index for a percent change; values beyond ±50% use the end bins. */
export function binIndex(pct: number): number {
  const index = Math.floor((pct - SCALE_EDGES[0]) / 10)
  return Math.min(SCALE_COLOURS.length - 1, Math.max(0, index))
}

/** Fill for a percent change, or null when there is no value (drawn as a "no value" pattern, never as zero). */
export function colourFor(pct: number | null): string | null {
  return pct === null ? null : (SCALE_COLOURS[binIndex(pct)] as string)
}
