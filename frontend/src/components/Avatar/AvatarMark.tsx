import { useState } from 'react'
interface Props {
  size?: number
  /** Accent used for the headband; follows the active element. */
  accent?: string
}

/**
 * The guide's portrait. If `public/guide-portrait.png` exists (an original character, square, at least
 * 256 px), it is shown in a round frame; otherwise this drawn placeholder is used.
 */
export function AvatarMark({ size = 48, accent = 'var(--element-air)' }: Props) {
  const [missing, setMissing] = useState(false)
  if (!missing)
    return (
      <img
        src={`${import.meta.env.BASE_URL}guide-portrait.png`}
        width={size}
        height={size}
        alt="The guide"
        onError={() => setMissing(true)}
        style={{ flex: 'none', borderRadius: '50%', objectFit: 'cover', display: 'block' }}
        data-testid="guide-portrait"
      />
    )
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Guide placeholder (final character art pending)" style={{ flex: 'none' }}>
      <circle cx="32" cy="32" r="30" fill="#f7f0df" stroke="#8a6a2f" strokeWidth="2" />
      <circle cx="32" cy="27" r="8.5" fill="none" stroke="#2b2117" strokeWidth="2.5" />
      <path d="M15 52c2-10 9-15 17-15s15 5 17 15" fill="none" stroke="#2b2117" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M21 17c6-5 16-5 22 0" fill="none" stroke={accent} strokeWidth="3.5" strokeLinecap="round" />
      <path d="M32 11v4" fill="none" stroke={accent} strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
