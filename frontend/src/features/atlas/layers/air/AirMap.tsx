import type { GeoJsonFeature } from '../../../../api/types'
import { atlasPercent, ringBounds, ringPath } from '../../projection'
import type { AirReading } from './airReading'
import type { AirTrendReading } from './airTrend'
import { colourFor } from './colourScale'
import styles from './AirLayer.module.css'

interface Props {
  boundary: GeoJsonFeature
  /** Which question is asked: the map's fill and label follow it. The polygon itself never moves. */
  view: 'trend' | 'comparison'
  reading: AirReading
  trend: AirTrendReading
  onToggle: () => void
}

const ring = (boundary: GeoJsonFeature) => boundary.geometry.coordinates[0] as number[][]
/** Where the label's leader starts, in atlas units up and to the left of the box. */
const LEADER = { dx: -46, dy: -40 }

/** The Kyiv study polygon at its true geographic size, filled by the selected comparison. */
export function AirMapSvg({ boundary, view, reading, onToggle }: Props) {
  const b = ringBounds(ring(boundary))
  const d = ringPath(ring(boundary))
  // The trend view is about change over eight years, not one season's change, so the box stays one neutral colour.
  const fill = view === 'trend' ? 'neutral' : colourFor(reading.pct)
  const cx = (b.minX + b.maxX) / 2
  const cy = (b.minY + b.maxY) / 2
  return (
    <g data-testid="air-layer">
      <defs>
        <pattern id="air-no-value" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#e9e4d6" />
          <path d="M0 0L6 6M6 0L0 6" stroke="#7a6a55" strokeWidth="0.8" />
        </pattern>
        <pattern id="air-low-coverage" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="5" stroke="#2b2117" strokeWidth="1.4" />
        </pattern>
      </defs>
      <line x1={b.minX + LEADER.dx} y1={b.minY + LEADER.dy} x2={b.minX} y2={b.minY} className={styles.leader} />
      {reading.featureSelected ? <circle cx={cx} cy={cy} r={(b.maxY - b.minY) * 0.95} className={styles.halo} /> : null}
      <path
        d={d}
        fill={fill === 'neutral' ? undefined : (fill ?? 'url(#air-no-value)')}
        className={`${styles.polygon} ${fill === 'neutral' ? styles.polygonNeutral : ''}`}
        data-testid="kyiv-polygon"
        data-atlas-focus=""
        data-fill={fill ?? 'no-value'}
        data-selected={reading.featureSelected}
      />
      {view === 'comparison' && reading.lowCoverage ? <path d={d} fill="url(#air-low-coverage)" className={styles.hatch} data-testid="kyiv-low-coverage" /> : null}
      {/* Larger pointer target than the true-size box; keyboard users use the label button. */}
      <circle cx={cx} cy={cy} r={30} className={styles.hit} onClick={onToggle} aria-hidden="true" />
    </g>
  )
}

/** Readable HTML label anchored to the box. It is also the accessible control that selects the study area. */
export function AirMapLabel({ boundary, view, reading, trend, onToggle }: Props) {
  const b = ringBounds(ring(boundary))
  const anchor = atlasPercent(b.minX + LEADER.dx, b.minY + LEADER.dy)
  return (
    <button
      type="button"
      className={styles.label}
      style={{ left: anchor.left, top: anchor.top }}
      aria-pressed={reading.featureSelected}
      onClick={onToggle}
      data-testid="kyiv-label"
    >
      {view === 'trend' ? (
        <>
          <span className={styles.labelTitle}>Kyiv · NO₂ trend</span>
          <span className={styles.labelValue} data-testid="kyiv-value">{trend.verdictShort}</span>
          <span className={styles.labelMeta}>
            <span className={styles.period}>{trend.windowLabel}</span>
            {trend.pValueText ? <span className={styles.nowrap}> · p = {trend.pValueText}</span> : null}
          </span>
        </>
      ) : (
        <>
          <span className={styles.labelTitle}>Kyiv · NO₂ study area</span>
          <span className={styles.labelValue} data-testid="kyiv-value">
            {reading.pctText}
            {reading.pct !== null ? <span className={styles.labelVs}> vs {reading.baselineYears}</span> : null}
          </span>
          <span className={styles.labelMeta}>
            <span className={styles.period}>{reading.periodLabel} · </span><span className={styles.nowrap}>{reading.validDays}/{reading.calendarDays} days</span>
            {reading.lowCoverage ? (
              <span className={styles.low} data-testid="kyiv-label-warning">
                {' '}
                <span aria-hidden="true">▲</span> low coverage
              </span>
            ) : null}
          </span>
        </>
      )}
    </button>
  )
}
