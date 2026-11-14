import { useState } from 'react'
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from 'recharts'
import styles from './TrendChart.module.css'

/** One monthly value on the timeline. `value` null = no measurement; the line breaks there. */
export interface TimelinePoint {
  /** "YYYY-MM" */
  month: string
  /** Decimal year at mid-month, used as the x position. */
  t: number
  value: number | null
  /** Quality flag, e.g. under half the days observed. Drawn hollow. */
  low: boolean
  /** Second tooltip line, e.g. "8 of 30 days observed". */
  note?: string
}

/** A straight line showing an estimated rate of change. */
export interface RateLine {
  t0: number
  t1: number
  y0: number
  y1: number
}

interface Props {
  points: TimelinePoint[]
  /** Axis label, e.g. "NO₂ column (×10¹⁵ molecules/cm²)". */
  unitLabel: string
  /** What one value is, for the legend, e.g. "Monthly mean". */
  seriesLabel: string
  /** Decimal year of the marked event. */
  eventT: number
  eventLabel: string
  /** Values after this decimal year are outside the analysis period and drawn faded. */
  analysisEndT?: number
  rateLine?: RateLine | null
  lowLabel?: string
  formatValue: (value: number) => string
  ariaLabel: string
}

const C_SERIES = '#2a78d6'
const C_RATE = '#2b2117'
const C_EVENT = '#a8321f'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const monthLabel = (ym: string) => `${MONTHS[Number(ym.slice(5, 7)) - 1] ?? ''} ${ym.slice(0, 4)}`

interface DotProps {
  cx?: number
  cy?: number
  index?: number
  payload?: TimelinePoint
}

/** Full-record timeline with a marked event, an optional rate line and a table view of the same data. */
export function TrendChart({ points, unitLabel, seriesLabel, eventT, eventLabel, analysisEndT, rateLine, lowLabel, formatValue, ariaLabel }: Props) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const values = points.map((p) => p.value).filter((v): v is number => v !== null)
  const yMax = values.length ? Math.ceil(Math.max(...values) * 1.08 * 2) / 2 : 1
  const yMin = values.length ? Math.min(0, Math.floor(Math.min(...values))) : 0
  const firstYear = Math.floor(points[0]?.t ?? 2015)
  const lastYear = Math.ceil(points[points.length - 1]?.t ?? 2023)
  const years = Array.from({ length: lastYear - firstYear + 1 }, (_, i) => firstYear + i)
  const faded = (p: TimelinePoint) => analysisEndT !== undefined && p.t > analysisEndT

  const dot = ({ cx, cy, index, payload }: DotProps) => {
    if (cx === undefined || cy === undefined || !payload || payload.value === null) return <g key={`t-${index}`} />
    return (
      <circle
        key={`t-${index}`}
        cx={cx}
        cy={cy}
        r={payload.low ? 3.4 : 3}
        fill={payload.low ? '#fcfcfb' : C_SERIES}
        stroke={C_SERIES}
        strokeWidth={payload.low ? 1.6 : 1}
        opacity={faded(payload) ? 0.35 : 1}
      />
    )
  }

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    const point = active ? (payload?.find((p) => (p.payload as TimelinePoint | undefined)?.month)?.payload as TimelinePoint | undefined) : undefined
    if (!point) return null
    return (
      <div className={styles.tooltip}>
        <p className={styles.tipTitle}>{monthLabel(point.month)}</p>
        <p>{point.value === null ? 'No measurement' : formatValue(point.value)}</p>
        {point.note ? <p className={styles.tipMeta}>{point.note}{point.low && lowLabel ? ` (${lowLabel.toLowerCase()})` : ''}</p> : null}
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <ul className={styles.legend} aria-label="Chart legend">
          <li>
            <svg width="26" height="12" aria-hidden="true"><line x1="0" x2="26" y1="6" y2="6" stroke={C_SERIES} strokeWidth="2" /><circle cx="13" cy="6" r="3.5" fill={C_SERIES} /></svg>
            {seriesLabel}
          </li>
          {lowLabel ? (
            <li>
              <svg width="26" height="12" aria-hidden="true"><circle cx="13" cy="6" r="4" fill="#fcfcfb" stroke={C_SERIES} strokeWidth="1.8" /></svg>
              Hollow: {lowLabel.toLowerCase()}
            </li>
          ) : null}
          {rateLine ? (
            <li>
              <svg width="26" height="12" aria-hidden="true"><line x1="0" x2="26" y1="6" y2="6" stroke={C_RATE} strokeWidth="2" strokeDasharray="6 4" /></svg>
              Estimated rate of change
            </li>
          ) : null}
          <li>
            <svg width="26" height="12" aria-hidden="true"><line x1="13" x2="13" y1="0" y2="12" stroke={C_EVENT} strokeWidth="2" /></svg>
            {eventLabel}
          </li>
        </ul>
        <div className={styles.toggle} role="group" aria-label="Timeline view">
          <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>Chart</button>
          <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>Table</button>
        </div>
      </div>

      {view === 'chart' ? (
        <div className={styles.plot} role="img" aria-label={ariaLabel} data-testid="trend-chart">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={points} margin={{ top: 22, right: 14, bottom: 8, left: 4 }}>
              <CartesianGrid stroke="#e7dfc9" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={[firstYear, lastYear]}
                ticks={years}
                tickFormatter={(y: number) => String(y)}
                tick={{ fontSize: 12, fill: '#5a4a38' }}
                tickLine={false}
                axisLine={{ stroke: '#b9a678' }}
              />
              <YAxis
                domain={[yMin, yMax]}
                tick={{ fontSize: 12, fill: '#5a4a38' }}
                tickLine={false}
                axisLine={false}
                width={44}
                label={{ value: unitLabel, angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: '#5a4a38', textAnchor: 'middle' }, dx: -2 }}
              />
              {analysisEndT !== undefined ? <ReferenceArea x1={analysisEndT} x2={lastYear} fill="#2b2117" fillOpacity={0.06} /> : null}
              <ReferenceLine x={eventT} stroke={C_EVENT} strokeWidth={2} label={{ value: eventLabel, position: 'top', fontSize: 11, fill: C_EVENT }} />
              <Tooltip content={tooltip} isAnimationActive={false} />
              <Line dataKey="value" stroke={C_SERIES} strokeWidth={1.6} dot={dot} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls={false} />
              {rateLine ? (
                <ReferenceLine
                  segment={[{ x: rateLine.t0, y: rateLine.y0 }, { x: rateLine.t1, y: rateLine.y1 }]}
                  stroke={C_RATE}
                  strokeWidth={2}
                  strokeDasharray="6 4"
                />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className={styles.tableWrap} data-testid="trend-table" tabIndex={0}>
          <table className={styles.table}>
            <thead>
              <tr><th scope="col">Month</th><th scope="col">{unitLabel}</th><th scope="col">Note</th></tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.month}>
                  <th scope="row">{monthLabel(p.month)}</th>
                  <td>{p.value === null ? 'No measurement' : formatValue(p.value)}</td>
                  <td>{p.note ?? ''}{p.low && lowLabel ? ` · ${lowLabel.toLowerCase()}` : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** "2022-04" → decimal year at mid-month. */
export function monthToDecimalYear(ym: string): number {
  return Number(ym.slice(0, 4)) + (Number(ym.slice(5, 7)) - 0.5) / 12
}

/** A calendar date → decimal year. */
export function dateToDecimalYear(iso: string): number {
  const date = new Date(`${iso}T00:00:00Z`)
  const year = date.getUTCFullYear()
  const start = Date.UTC(year, 0, 1)
  const end = Date.UTC(year + 1, 0, 1)
  return year + (date.getTime() - start) / (end - start)
}
