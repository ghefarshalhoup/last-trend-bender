import type { ElementId } from '../explorer/elements'

/**
 * Generic element glyphs and the colours of each element's scroll and medallion.
 * Drawn for this project (wind, flame, mountain, waves); not taken from any franchise.
 */
export type ArtId = ElementId | 'none'

interface Art {
  /** paper / medallion light tone */
  light: string
  /** paper / medallion deep tone */
  deep: string
  /** glyph ink */
  ink: string
}

export const ELEMENT_ART: Record<ArtId, Art> = {
  air: { light: '#fff6dc', deep: '#e9c977', ink: '#8a6414' },
  fire: { light: '#fde6d8', deep: '#e98b5e', ink: '#a8361a' },
  land: { light: '#eef1d9', deep: '#aebb72', ink: '#4c6420' },
  water: { light: '#e3eef8', deep: '#93bce0', ink: '#245a8c' },
  none: { light: '#f7efda', deep: '#dccfae', ink: '#8a6a2f' },
}

/** 48 × 48 glyph, centred on (24, 24). */
export function ElementGlyph({ id, color }: { id: ArtId; color: string }) {
  const line = { fill: 'none', stroke: color, strokeWidth: 3.2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (id) {
    case 'air':
      return (
        <g>
          <path d="M5 18H27a5.5 5.5 0 1 0-5.5-5.5" {...line} />
          <path d="M4 26H34a6 6 0 1 1-6 6" {...line} />
          <path d="M11 34H21" {...line} />
        </g>
      )
    case 'fire':
      return (
        <g>
          <path d="M24 5c3 8 12 12 12 24a12 12 0 0 1-24 0c0-6 3-9 5-14 2 4 3 6 5 7-1-6-1-11 2-17z" fill={color} />
          <path d="M24 25c2 3 6 5 6 10a6 6 0 0 1-12 0c0-3 4-6 6-10z" fill="#fff4e4" opacity="0.85" />
        </g>
      )
    case 'land':
      return (
        <g>
          <path d="M3 39L18 13l7 12 5-7 15 21z" fill={color} />
          <path d="M18 13l-5 9 5-2.5 3.5 3z" fill="#fbf7ea" opacity="0.9" />
        </g>
      )
    case 'water':
      return (
        <g>
          <path d="M5 17q4.75-5.5 9.5 0t9.5 0 9.5 0 9.5 0" {...line} />
          <path d="M5 26q4.75-5.5 9.5 0t9.5 0 9.5 0 9.5 0" {...line} />
          <path d="M5 35q4.75-5.5 9.5 0t9.5 0 9.5 0 9.5 0" {...line} />
        </g>
      )
    default:
      return (
        <g>
          <circle cx="24" cy="24" r="12" {...line} strokeWidth={2.4} />
          <path d="M24 10v28M10 24h28" {...line} strokeWidth={2} />
          <path d="M24 12l3 12-3 12-3-12z" fill={color} />
        </g>
      )
  }
}

/** The element scroll. Paper colour and glyph follow the active element. */
export function ScrollArt({ id }: { id: ArtId }) {
  const art = ELEMENT_ART[id]
  const ink = '#2b2117'
  const gradient = `scroll-paper-${id}`
  return (
    <svg viewBox="0 0 120 110" width="100%" height="100%" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={gradient} cx="45%" cy="40%" r="70%">
          <stop offset="0" stopColor={art.light} />
          <stop offset="1" stopColor={art.deep} />
        </radialGradient>
      </defs>
      <ellipse cx="60" cy="100" rx="44" ry="5" fill={art.deep} opacity="0.35" />
      {/* top curl */}
      <path d="M86 15c0-8 15-10 17-2 1.5 6-5.5 9-8 5" fill={`url(#${gradient})`} stroke={ink} strokeWidth="2.6" strokeLinecap="round" />
      {/* sheet with a wavy left edge */}
      <path d="M30 14H90V82H30c4-9-4-17 0-27s-4-19 0-27c1.5-4 0-9 0-14z" fill={`url(#${gradient})`} stroke={ink} strokeWidth="2.6" strokeLinejoin="round" />
      {/* bottom roll */}
      <rect x="16" y="78" width="80" height="16" rx="8" fill={`url(#${gradient})`} stroke={ink} strokeWidth="2.6" />
      <circle cx="88" cy="86" r="5" fill="none" stroke={ink} strokeWidth="2" />
      <path d="M88 86a2.4 2.4 0 1 1 2.4-2.4" fill="none" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />
      <g transform="translate(37 25) scale(0.92)">
        <ElementGlyph id={id} color={art.ink} />
      </g>
    </svg>
  )
}
