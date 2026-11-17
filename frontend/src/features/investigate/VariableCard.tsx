import { useState } from 'react'
import { dateToDecimalYear, monthToDecimalYear, TrendChart, type RateLine, type TimelinePoint } from '../atlas/TrendChart'
import type { ElementView } from '../explorer/elements'
import { noDataReason, placeLabel, type VariableEntry } from './catalog'
import { spanText, type SeriesState, type TrendResult, type VariableSeries, type WindowId } from './series'
import { displayUnit, fmt, readCard, type CardReading } from './verdict'
import definitions from '../atlas/variableDefinitions.json'
import styles from './VariableCard.module.css'

export type { SeriesState }

interface Props {
  variable: VariableEntry
  element: ElementView
  placeId: string
  window: WindowId
  invasionDate: string
  state: SeriesState
  trend: TrendResult | undefined
  onRemove: () => void
  onRetry: () => void
  /** The card the guide is reading. */
  focused?: boolean
  onFocus?: () => void
}

const ICON = { significant: '●', not_significant: '○', not_assessed: '–' } as const
const DEFS = new Map((definitions as { metric_id: string; definition: string; reading_hint: string }[]).map((d) => [d.metric_id, d]))

/** One variable for one place: timeline, verdict, rate with uncertainty; the back explains it. */
export function VariableCard({ variable, element, placeId, window, invasionDate, state, trend, onRemove, onRetry, focused = false, onFocus }: Props) {
  const [flipped, setFlipped] = useState(false)
  const title = variable.short_label
  return (
    <article
      className={styles.card}
      style={{ '--accent': element.accent, '--soft': element.soft } as React.CSSProperties}
      aria-label={`${title}, ${placeLabel(placeId)}`}
      data-testid={`card-${variable.metric_id}`}
      data-focused={focused}
      aria-current={focused ? 'true' : undefined}
      onClick={onFocus}
    >
      <header className={styles.head}>
        <div className={styles.titles}>
          <h3 className={styles.title}>{title}</h3>
          <p className={styles.sub}>{element.label} · {displayUnit(variable).unit}</p>
        </div>
        <button type="button" className={styles.icon} aria-pressed={flipped} onClick={() => setFlipped((f) => !f)} data-testid={`card-flip-${variable.metric_id}`}>
          <span aria-hidden="true">{flipped ? '↺' : 'i'}</span>
          <span className="sr-only">{flipped ? 'Back to the chart' : 'About this variable and its test'}</span>
        </button>
        <button type="button" className={styles.icon} onClick={onRemove} aria-label={`Remove ${title}`} data-testid={`card-remove-${variable.metric_id}`}>
          <span aria-hidden="true">×</span>
        </button>
      </header>
      {state.status === 'loading' ? <p className={styles.muted}>Loading the record…</p> : null}
      {state.status === 'error' ? (
        <div className={styles.muted} role="alert" data-testid="card-failed">
          <p>Failed to load: the record did not arrive from the server. {state.message}</p>
          <button type="button" className={styles.retry} onClick={onRetry}>Try again</button>
        </div>
      ) : null}
      {state.status === 'ready' && state.series === null ? (
        <p className={styles.muted} data-testid="card-no-data">{noDataReason(variable, placeId)}</p>
      ) : null}
      {state.status === 'ready' && state.series ? (
        <CardBody variable={variable} series={state.series} trend={trend} window={window} invasionDate={invasionDate} flipped={flipped} placeId={placeId} />
      ) : null}
    </article>
  )
}

function CardBody({ variable, series, trend, window, invasionDate, flipped, placeId }: { placeId: string; variable: VariableEntry; series: VariableSeries; trend: TrendResult | undefined; window: WindowId; invasionDate: string; flipped: boolean }) {
  const reading = readCard(variable, series, trend)
  if (flipped) return <CardBack variable={variable} reading={reading} series={series} placeId={placeId} />
  const { scale, unit } = displayUnit(variable)
  const points = withGaps(series.points.map((p) => ({ month: p.month, t: monthToDecimalYear(p.month), value: p.value === null ? null : p.value / scale, low: p.low, note: p.note })))
  const invasionT = dateToDecimalYear(invasionDate)
  const span = spanText(series, window)
  // Monthly data: the pre-invasion test runs to the end of February 2022, so the untested shading starts on 1 March.
  const analysisEndT = window === 'pre_invasion' ? monthToDecimalYear('2022-03') - 0.5 / 12 : undefined
  const rateLine = rateLineFor(points, trend, reading, scale, analysisEndT)
  return (
    <>
      <p className={styles.badge} data-verdict={reading.verdict} data-testid="card-verdict">
        <span aria-hidden="true">{ICON[reading.verdict]}</span> {reading.badge}
      </p>
      <TrendChart
        compact
        points={points}
        unitLabel={unit}
        seriesLabel="Monthly value"
        lowLabel="Under half the days observed"
        eventT={invasionT}
        eventLabel="Invasion, 24 Feb 2022"
        analysisEndT={analysisEndT}
        rateLine={rateLine}
        rateDashed={reading.verdict !== 'significant'}
        formatValue={(v) => `${fmt(v)} ${unit}`}
        ariaLabel={`Monthly ${variable.short_label}. ${reading.sentence}`}
      />
      <p className={styles.sentence}>{reading.sentence}</p>
      {span ? (
        <p className={styles.span} data-testid="card-span">
          {reading.verdict === 'not_assessed' ? 'Record' : 'Tested'}: {span}
          {window === 'pre_invasion' && span.endsWith('Feb 2022') ? ' (includes 24–28 Feb)' : ''}
        </p>
      ) : null}
      {reading.rateText ? (
        <p className={styles.rate} data-testid="card-rate">
          {reading.rateText}
          {reading.intervalText ? <span className={styles.ci}> · 95% range {reading.intervalText}</span> : null}
        </p>
      ) : null}
      {reading.seasonalText ? (
        <p className={styles.seasonal} data-testid="card-seasonal">
          Mar–Aug 2022: <strong>{reading.seasonalText}</strong> <span className={styles.ci}>(a description, not a test)</span>
        </p>
      ) : null}
    </>
  )
}

/** Months missing from the record (e.g. fire's September–February) become breaks, so the line never bridges them. */
export function withGaps(points: TimelinePoint[]): TimelinePoint[] {
  const out: TimelinePoint[] = []
  for (const p of points) {
    const prev = out[out.length - 1]
    if (prev && p.t - prev.t > 1.5 / 12) out.push({ month: '', t: (prev.t + p.t) / 2, value: null, low: false })
    out.push(p)
  }
  return out
}

/** The rate is drawn through the period's average; the slope itself comes from the API. */
export function rateLineFor(points: TimelinePoint[], trend: TrendResult | undefined, reading: CardReading, scale: number, endT?: number): RateLine | null {
  if (reading.verdict === 'not_assessed' || !trend || trend.slope_per_year === null) return null
  const t0 = trend.start_month ? monthToDecimalYear(trend.start_month) : (points[0]?.t ?? 0)
  const t1 = trend.end_month ? monthToDecimalYear(trend.end_month) : (endT ?? points[points.length - 1]?.t ?? 0)
  const inside = points.filter((p) => p.value !== null && p.t >= t0 - 1e-9 && p.t <= t1 + 1e-9)
  if (inside.length < 2) return null
  const meanT = inside.reduce((s, p) => s + p.t, 0) / inside.length
  const meanY = inside.reduce((s, p) => s + (p.value as number), 0) / inside.length
  const perYear = trend.slope_per_year / scale
  return { t0, t1, y0: meanY + perYear * (t0 - meanT), y1: meanY + perYear * (t1 - meanT) }
}

function CardBack({ variable, reading, series, placeId }: { variable: VariableEntry; reading: CardReading; series: VariableSeries; placeId: string }) {
  const def = DEFS.get(variable.metric_id)
  const first = series.points[0]?.month
  const last = series.points[series.points.length - 1]?.month
  return (
    <div className={styles.back} data-testid="card-back">
      {def ? (
        <>
          <p>{def.definition}</p>
          <p className={styles.mutedText}>{def.reading_hint}</p>
        </>
      ) : null}
      <dl className={styles.facts}>
        <div><dt>Source</dt><dd>{variable.sources.join('; ')}</dd></div>
        <div><dt>Record</dt><dd>{first} to {last}, monthly</dd></div>
        <div><dt>Test</dt><dd>{reading.method ?? 'Not run'}</dd></div>
        {reading.pText ? <div><dt>p-value</dt><dd>{reading.pText}{reading.pFdrText ? ` (after correcting for many tests: ${reading.pFdrText})` : ''}</dd></div> : null}
        {reading.nMonths ? <div><dt>Months tested</dt><dd>{reading.nMonths}</dd></div> : null}
      </dl>
      <p className={styles.mutedText}>Significant means p is below 0.05: a trend this strong would rarely appear by chance alone. It does not say what caused it.</p>
      {reading.seasonalNote ? <p className={styles.mutedText}>{reading.seasonalNote}</p> : null}
      <ul className={styles.limits}>
        {/* The result's own caveats come first: they are about this place and period. The catalog's NO₂ notes describe Kyiv only. */}
        {[...reading.caveats, ...(variable.metric_id === 'no2_mean_molec_cm2' && placeId !== 'kyiv_no2_box' ? [] : variable.limitations)].slice(0, 5).map((l) => <li key={l}>{l}</li>)}
      </ul>
    </div>
  )
}
