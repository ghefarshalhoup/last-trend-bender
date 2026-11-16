import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import type { RateLine, TimelinePoint } from '../atlas/TrendChart'
import styles from './GlassChart.module.css'

export interface ChartSeries {
  id: string
  label: string
  color: string
  points: TimelinePoint[]
}

interface Props {
  series: ChartSeries[]
  /** Trend line for the first series only. */
  rateLine: RateLine | null
  rateDashed: boolean
  eventT: number
  formatValue: (v: number) => string
  ariaLabel: string
  height?: number
}

const PAD = { top: 10, right: 10, bottom: 20, left: 34 }
const MIN_SPAN_YEARS = 0.5

const monthName = (m: string) => {
  const [y, mm] = m.split('-')
  return new Date(Number(y), Number(mm) - 1, 15).toLocaleString('en-GB', { month: 'short', year: 'numeric' })
}

function niceTicks(lo: number, hi: number, count: number): number[] {
  const span = hi - lo || 1
  const raw = span / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(10)))
  return out
}

/**
 * A quiet line chart for the glass cards. Drag across it to zoom into a stretch of time;
 * double-click or press "Full record" to go back. Zooming only changes the view: the trend test always uses the full record.
 */
export function GlassChart({ series, rateLine, rateDashed, eventT, formatValue, ariaLabel, height = 150 }: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(320)
  const all = useMemo(() => series.flatMap((s) => s.points.filter((p) => p.value !== null)), [series])
  const fullX: [number, number] = useMemo(() => {
    if (!all.length) return [2015, 2023]
    return [Math.min(...all.map((p) => p.t)), Math.max(...all.map((p) => p.t))]
  }, [all])
  const [domain, setDomain] = useState<[number, number] | null>(null)
  const [x0, x1] = domain ?? fullX
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null)
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    const el = wrap.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([entry]) => entry && setWidth(Math.max(200, entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const innerW = width - PAD.left - PAD.right
  const innerH = height - PAD.top - PAD.bottom
  const visible = all.filter((p) => p.t >= x0 && p.t <= x1)
  const values = visible.map((p) => p.value as number)
  const rawLo = values.length ? Math.min(...values) : 0
  const rawHi = values.length ? Math.max(...values) : 1
  const padY = (rawHi - rawLo || Math.abs(rawHi) || 1) * 0.1
  const y0 = rawLo >= 0 && rawLo - padY < 0 ? 0 : rawLo - padY
  const y1 = rawHi + padY
  const sx = (t: number) => PAD.left + ((t - x0) / (x1 - x0 || 1)) * innerW
  const sy = (v: number) => PAD.top + (1 - (v - y0) / (y1 - y0 || 1)) * innerH
  const tx = (px: number) => x0 + ((px - PAD.left) / innerW) * (x1 - x0)

  const pathOf = (pts: TimelinePoint[]) => {
    let d = ''
    let pen = false
    for (const p of pts) {
      if (p.value === null || p.t < x0 - 0.2 || p.t > x1 + 0.2) {
        pen = false
        continue
      }
      d += `${pen ? 'L' : 'M'}${sx(p.t).toFixed(1)},${sy(p.value).toFixed(1)}`
      pen = true
    }
    return d
  }

  const yTicks = niceTicks(y0, y1, 3)
  const span = x1 - x0
  const xTicks: number[] = []
  const yearStep = span > 5 ? 1 : span > 2 ? 0.5 : 0.25
  for (let t = Math.ceil(x0 / yearStep) * yearStep; t <= x1; t += yearStep) xTicks.push(t)
  const xLabel = (t: number) => {
    const y = Math.floor(t + 1e-6)
    const m = Math.round((t - y) * 12)
    return m === 0 ? (span > 5 ? `’${String(y).slice(2)}` : String(y)) : new Date(y, m, 1).toLocaleString('en-GB', { month: 'short' })
  }

  const local = (e: ReactPointerEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
    return Math.min(Math.max(e.clientX - rect.left, PAD.left), PAD.left + innerW)
  }
  const onDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return
    ;(e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId)
    const x = local(e)
    setDrag({ from: x, to: x })
  }
  const onMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    const x = local(e)
    setHover(tx(x))
    if (drag) setDrag({ ...drag, to: x })
  }
  const onUp = () => {
    if (drag && Math.abs(drag.to - drag.from) > 8) {
      const a = tx(Math.min(drag.from, drag.to))
      const b = tx(Math.max(drag.from, drag.to))
      if (b - a >= MIN_SPAN_YEARS / 4) setDomain(b - a < MIN_SPAN_YEARS ? [(a + b) / 2 - MIN_SPAN_YEARS / 2, (a + b) / 2 + MIN_SPAN_YEARS / 2] : [a, b])
    }
    setDrag(null)
  }

  // The readout lists every place at the month under the pointer.
  const readout = useMemo(() => {
    if (hover === null || drag) return null
    const first = series[0]?.points.filter((p) => p.value !== null) ?? []
    let best: TimelinePoint | undefined
    for (const p of first.length ? first : all) if (!best || Math.abs(p.t - hover) < Math.abs(best.t - hover)) best = p
    if (!best) return null
    const month = best.month
    return {
      t: best.t,
      month,
      rows: series.map((s) => ({ s, p: s.points.find((p) => p.month === month) })),
    }
  }, [hover, drag, series, all])

  const zoomed = domain !== null
  const clipId = useMemo(() => `clip-${Math.random().toString(36).slice(2)}`, [])

  return (
    <div className={styles.wrap} ref={wrap}>
      <svg
        width={width}
        height={height}
        className={styles.svg}
        role="img"
        aria-label={`${ariaLabel}${zoomed ? ` Showing ${monthName(String(Math.floor(x0)) + '-01')} onwards.` : ''}`}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={() => {
          setHover(null)
          setDrag(null)
        }}
        onDoubleClick={() => setDomain(null)}
        data-testid="glass-chart"
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={PAD.left} y={PAD.top - 4} width={innerW} height={innerH + 8} />
          </clipPath>
        </defs>
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={sy(v)} y2={sy(v)} className={styles.grid} />
            <text x={PAD.left - 6} y={sy(v)} className={styles.tick} textAnchor="end" dominantBaseline="middle">
              {Number(v.toPrecision(3))}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={sx(t)} y={height - 4} className={styles.tick} textAnchor="middle">
            {xLabel(t)}
          </text>
        ))}
        <g clipPath={`url(#${clipId})`}>
          {eventT >= x0 && eventT <= x1 ? <line x1={sx(eventT)} x2={sx(eventT)} y1={PAD.top} y2={PAD.top + innerH} className={styles.event} /> : null}
          {[...series].reverse().map((s) => (
            <path key={s.id} d={pathOf(s.points)} stroke={s.color} className={styles.line} style={{ filter: `drop-shadow(0 0 3px ${s.color})` }} />
          ))}
          {rateLine ? (
            <line x1={sx(rateLine.t0)} x2={sx(rateLine.t1)} y1={sy(rateLine.y0)} y2={sy(rateLine.y1)} className={styles.rate} strokeDasharray={rateDashed ? '4 4' : undefined} />
          ) : null}
          {readout ? (
            <>
              <line x1={sx(readout.t)} x2={sx(readout.t)} y1={PAD.top} y2={PAD.top + innerH} className={styles.cross} />
              {readout.rows.map(({ s, p }) => (p && p.value !== null ? <circle key={s.id} cx={sx(p.t)} cy={sy(p.value)} r={3.5} fill={s.color} className={styles.dot} /> : null))}
            </>
          ) : null}
          {drag ? <rect x={Math.min(drag.from, drag.to)} y={PAD.top} width={Math.abs(drag.to - drag.from)} height={innerH} className={styles.brush} /> : null}
        </g>
      </svg>
      {readout ? (
        <div className={styles.tip} style={{ left: Math.min(Math.max(sx(readout.t) - 70, 0), width - 150) }} role="status">
          <p className={styles.tipMonth}>{monthName(readout.month)}</p>
          {readout.rows.map(({ s, p }) => (
            <p key={s.id} className={styles.tipRow}>
              <span className={styles.tipKey} style={{ background: s.color }} aria-hidden="true" />
              <strong>{p && p.value !== null ? formatValue(p.value) : 'no data'}</strong>
              <span className={styles.tipLabel}>{s.label}{p?.low ? ', few days' : ''}</span>
            </p>
          ))}
        </div>
      ) : null}
      <div className={styles.zoomBar}>
        {zoomed ? (
          <button type="button" className={styles.reset} onClick={() => setDomain(null)} data-testid="zoom-reset">
            Full record
          </button>
        ) : (
          <span className={styles.hint}>Drag to zoom time</span>
        )}
      </div>
    </div>
  )
}
