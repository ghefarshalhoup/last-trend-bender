import { useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { AbsenceMark } from '../../components/Absence/Absence'
import { formatDays, formatFraction, formatScientific, yearsRangeLabel } from '../../adapters/format'
import { buildChartPoints, type ChartPoint, type MonthRow } from '../../adapters/months'
import styles from './ComparisonChart.module.css'

interface Props {
  rows: MonthRow[]
  baselineYears: number[]
  selectedMonth: number | null
  onSelectMonth: (calendarMonth: number) => void
}

const C_2022 = '#eb6834'
const C_BASE = '#2a78d6'
const SCALE_LABEL = '×10¹⁵ molecules/cm²'

interface DotProps {
  cx?: number
  cy?: number
  index?: number
  payload?: ChartPoint
}

export function ComparisonChart({ rows, baselineYears, selectedMonth, onSelectMonth }: Props) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const data = buildChartPoints(rows)
  const baselineLabel = yearsRangeLabel(baselineYears)
  const last = data.length - 1
  const ceilings = data.flatMap((d) => [d.baseline, d.y2022, d.band ? d.band[1] : null]).filter((v): v is number => v !== null)
  const yMax = ceilings.length > 0 ? Math.ceil(Math.max(...ceilings) * 1.1 * 2) / 2 : 1

  const dot2022 = ({ cx, cy, index, payload }: DotProps) => {
    if (cx === undefined || cy === undefined || !payload || payload.y2022 === null) return <g key={`d22-${index}`} />
    const selected = payload.calendarMonth === selectedMonth
    return (
      <g key={`d22-${index}`}>
        {selected ? <circle cx={cx} cy={cy} r={11} fill="none" stroke="#14212f" strokeWidth={2} /> : null}
        <circle
          cx={cx}
          cy={cy}
          r={6}
          fill={payload.lowCoverage2022 ? '#fcfcfb' : C_2022}
          stroke={C_2022}
          strokeWidth={payload.lowCoverage2022 ? 2.5 : 2}
          strokeDasharray={payload.lowCoverage2022 ? '2.5 2' : undefined}
        />
        {index === last ? (
          <text x={cx + 12} y={cy + 4} fontSize={13} fontWeight={600} fill="#b94a1c">2022</text>
        ) : null}
      </g>
    )
  }

  const dotBase = ({ cx, cy, index, payload }: DotProps) => {
    if (cx === undefined || cy === undefined || !payload || payload.baseline === null) return <g key={`db-${index}`} />
    return (
      <g key={`db-${index}`}>
        <circle cx={cx} cy={cy} r={4.5} fill={C_BASE} stroke="#fcfcfb" strokeWidth={2} />
        {index === last ? (
          <text x={cx + 12} y={cy + 4} fontSize={13} fontWeight={600} fill="#1d5aa6">{baselineLabel}</text>
        ) : null}
      </g>
    )
  }

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null
    const point = payload[0]?.payload as ChartPoint | undefined
    const row = rows.find((r) => r.calendarMonth === point?.calendarMonth)
    if (!row) return null
    return (
      <div className={styles.tooltip}>
        <p className={styles.tipTitle}>{row.long}</p>
        <p>
          <span className={styles.key} style={{ background: C_2022 }} /> 2022:{' '}
          {row.target.mean === null ? <AbsenceMark kind="missing_measurement" /> : formatScientific(row.target.mean)}
        </p>
        <p>
          <span className={styles.key} style={{ background: C_BASE }} /> {baselineLabel}:{' '}
          {row.baseline.mean === null ? <AbsenceMark kind="missing_measurement" /> : formatScientific(row.baseline.mean)}
        </p>
        <p className={styles.tipMeta}>
          {formatDays(row.target.validDays, row.target.calendarDays)} observed in 2022
          {row.target.lowCoverage ? ' (low coverage)' : ''}
        </p>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <ul className={styles.legend} aria-label="Chart legend">
          <li>
            <svg width="26" height="12" aria-hidden="true"><line x1="0" x2="26" y1="6" y2="6" stroke={C_2022} strokeWidth="2.5" /><circle cx="13" cy="6" r="4.5" fill={C_2022} /></svg>
            2022 monthly mean
          </li>
          <li>
            <svg width="26" height="12" aria-hidden="true"><line x1="0" x2="26" y1="6" y2="6" stroke={C_BASE} strokeWidth="2.5" /><circle cx="13" cy="6" r="3.5" fill={C_BASE} /></svg>
            {baselineLabel} monthly mean
          </li>
          <li>
            <svg width="26" height="12" aria-hidden="true"><rect x="0" y="1" width="26" height="10" fill="rgba(42,120,214,0.16)" /></svg>
            Lowest to highest year in {baselineLabel}
          </li>
          <li>
            <svg width="26" height="14" aria-hidden="true"><circle cx="13" cy="7" r="5.5" fill="#fcfcfb" stroke={C_2022} strokeWidth="2.5" strokeDasharray="2.5 2" /></svg>
            Hollow: under half the days observed
          </li>
        </ul>
        <div className={styles.toggle} role="group" aria-label="Chart view">
          <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>Chart</button>
          <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>Table</button>
        </div>
      </div>

      {view === 'chart' ? (
        <div className={styles.plot} data-testid="comparison-chart" role="img" aria-label={`Monthly NO₂, March to August: 2022 against the ${baselineLabel} average. The month buttons below give the same data.`}>
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart
              data={data}
              margin={{ top: 16, right: 84, bottom: 28, left: 8 }}
              onClick={(state) => {
                const i = Number(state?.activeIndex)
                const point = Number.isInteger(i) ? data[i] : undefined
                if (point) onSelectMonth(point.calendarMonth)
              }}
            >
              <CartesianGrid stroke="#e3e9ef" vertical={false} />
              <XAxis dataKey="short" tickLine={false} axisLine={{ stroke: '#b4c0cd' }} tick={{ fill: '#4a5a6c', fontSize: 13 }} label={{ value: 'Month (March–August)', position: 'insideBottom', offset: -18, fill: '#4a5a6c', fontSize: 12 }} />
              <YAxis
                domain={[0, yMax]}
                tickLine={false}
                axisLine={false}
                width={52}
                tick={{ fill: '#4a5a6c', fontSize: 12 }}
                tickFormatter={(v: number) => v.toFixed(1)}
                label={{ value: `NO₂ column (${SCALE_LABEL})`, angle: -90, position: 'insideLeft', offset: 8, style: { textAnchor: 'middle', fill: '#4a5a6c', fontSize: 12 } }}
              />
              <Tooltip content={tooltip} cursor={{ stroke: '#14212f', strokeOpacity: 0.25 }} />
              <Area dataKey="band" type="linear" stroke="none" fill={C_BASE} fillOpacity={0.14} isAnimationActive={false} connectNulls={false} activeDot={false} legendType="none" />
              <Line dataKey="baseline" type="linear" stroke={C_BASE} strokeWidth={2} connectNulls={false} dot={dotBase} activeDot={false} isAnimationActive={false} />
              <Line dataKey="y2022" type="linear" stroke={C_2022} strokeWidth={2.5} connectNulls={false} dot={dot2022} activeDot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table} data-testid="chart-table">
            <caption className="sr-only">Monthly NO₂ column, 2022 against the {baselineLabel} average, {SCALE_LABEL}</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">2022</th>
                <th scope="col">{baselineLabel} mean</th>
                <th scope="col">Baseline range</th>
                <th scope="col">Days observed 2022</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.calendarMonth}>
                  <th scope="row">{r.long}</th>
                  <td>{r.target.mean === null ? <AbsenceMark kind="missing_measurement" /> : formatScientific(r.target.mean)}</td>
                  <td>{r.baseline.mean === null ? <AbsenceMark kind="missing_measurement" /> : formatScientific(r.baseline.mean)}</td>
                  <td>
                    {r.baseline.min === null || r.baseline.max === null ? (
                      <AbsenceMark kind="missing_measurement" />
                    ) : (
                      `${formatScientific(r.baseline.min)} to ${formatScientific(r.baseline.max)}`
                    )}
                  </td>
                  <td>
                    {r.target.validDays}/{r.target.calendarDays} ({formatFraction(r.target.coverage)}){r.target.lowCoverage ? ' ▲ low' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className={styles.footnote}>
        Gaps in a line are months with no valid measurement; the line is never joined across them. The shaded band shows
        year-to-year variability in the baseline, not a confidence interval.
      </p>
    </div>
  )
}
