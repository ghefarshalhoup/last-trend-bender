import { useMemo, useState } from 'react'
import { MINUS } from '../../adapters/format'
import { dateToDecimalYear, monthToDecimalYear, TrendChart } from '../atlas/TrendChart'
import definitions from '../atlas/variableDefinitions.json'
import { hasDataFor, NO2_METRIC, noDataReason, placeLabel, type ExtraSupport, type PlaceFeature, type VariableCatalog, type VariableEntry } from '../investigate/catalog'
import { endpointFor, readSeries, spanText, trendKey, WINDOWS, type TrendResult, type VariableSeries, type WindowId } from '../investigate/series'
import { usePayloads } from '../investigate/usePayloads'
import { rateLineFor, withGaps } from '../investigate/VariableCard'
import { displayUnit, fmt, pickTrend, readCard, type CardReading } from '../investigate/verdict'
import styles from './Workspace.module.css'

interface Props {
  place: PlaceFeature
  catalog: VariableCatalog
  trendIndex: Map<string, TrendResult>
  extra: ExtraSupport
  onClose: () => void
  onBackToEarth: () => void
}

const NO2_DEFINITION = (definitions as { metric_id: string; definition: string }[]).find((d) => d.metric_id === NO2_METRIC)?.definition
const ICON = { significant: '●', not_significant: '○', not_assessed: '–' } as const

const signedPercent = (pct: number) => `${pct < 0 ? MINUS : pct > 0 ? '+' : ''}${Math.abs(pct).toFixed(1)}%`

/** One sentence that puts the season and the record side by side. Every part of it comes from the results. */
function takeaway(reading: CardReading, seasonalPct: number | null, window: WindowId): string {
  const period = window === 'pre_invasion' ? 'the record before the invasion' : 'the full record'
  if (reading.verdict === 'not_assessed') return `${reading.sentence} The monthly values are shown as they are.`
  const move = reading.direction === 'down' ? 'fall' : 'rise'
  if (reading.verdict === 'significant') {
    return window === 'pre_invasion' ? `A statistically significant ${move} was already under way before the invasion.` : `The ${move} is statistically significant across the full record.`
  }
  if (seasonalPct !== null && seasonalPct !== 0) {
    return `Spring and summer 2022 were ${seasonalPct < 0 ? 'lower' : 'higher'} than the earlier average, but across ${period} the trend is not statistically significant. One season does not make a lasting change.`
  }
  return reading.sentence
}

/** The evidence workspace: one place, its NO₂ record, the season everyone quotes and the test of the whole record. */
export function Workspace({ place, catalog, trendIndex, extra, onClose, onBackToEarth }: Props) {
  const placeId = place.properties.region_id
  const label = placeLabel(placeId)
  const [window, setWindow] = useState<WindowId>('full_record')
  const variable = useMemo(() => catalog.variables.find((v) => v.metric_id === NO2_METRIC), [catalog.variables])
  const supported = variable ? hasDataFor(variable, placeId, extra) : false
  const endpoint = variable && supported ? endpointFor(variable, placeId, extra) : null
  const { states, retry } = usePayloads(endpoint ? [endpoint] : [])
  const payload = endpoint ? states[endpoint] : undefined
  const series: VariableSeries | null = variable && payload?.status === 'success' ? readSeries(variable, placeId, payload.data) : null

  return (
    <section className={styles.sheet} aria-label={`Evidence for ${label}`} data-testid="workspace">
      <header className={styles.bar}>
        <nav aria-label="Where you are" className={styles.path}>
          <button type="button" className={styles.link} onClick={onBackToEarth} data-testid="back-to-earth">Earth</button>
          <span aria-hidden="true">/</span>
          <span>Ukraine case</span>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{label}</span>
        </nav>
        <button type="button" className={styles.close} onClick={onClose} data-testid="close-workspace">Close</button>
      </header>

      <h2 className={styles.question}>
        {placeId === 'kyiv_no2_box' ? 'Did lower NO₂ over Kyiv in 2022 mean a lasting change?' : `What does the NO₂ record over ${label} show?`}
      </h2>

      {!variable || !supported ? (
        <p className={styles.note} data-testid="workspace-no-data">{variable ? noDataReason(variable, placeId) : 'The variable list did not include NO₂.'}</p>
      ) : !payload || payload.status === 'loading' ? (
        <p className={styles.note} role="status">Loading the record…</p>
      ) : payload.status === 'error' ? (
        <div className={styles.note} role="alert">
          <p>The record did not arrive. {payload.error.message}</p>
          <button type="button" className={styles.retry} onClick={() => endpoint && retry(endpoint)}>Try again</button>
        </div>
      ) : !series ? (
        <p className={styles.note} data-testid="workspace-no-data">{noDataReason(variable, placeId)}</p>
      ) : (
        <Evidence
          key={placeId}
          label={label}
          series={series}
          trend={pickTrend(trendIndex.get(trendKey(placeId, NO2_METRIC, window)), series, window)}
          window={window}
          onWindow={setWindow}
          invasionDate={catalog.conflict_start}
          variable={variable}
        />
      )}

      <footer className={styles.foot}>
        {NO2_DEFINITION ? <p><strong>NO₂.</strong> {NO2_DEFINITION}</p> : null}
        {variable ? <p>Source: {variable.sources.join('; ')}. Monthly means over the dashed study box on the map.</p> : null}
        <p><a href="#/atlas">Open the illustrated atlas</a> for all 25 variables.</p>
      </footer>
    </section>
  )
}

interface EvidenceProps {
  label: string
  series: VariableSeries
  trend: TrendResult | undefined
  window: WindowId
  onWindow: (w: WindowId) => void
  invasionDate: string
  variable: VariableEntry
}

function Evidence({ label, series, trend, window, onWindow, invasionDate, variable }: EvidenceProps) {
  const reading = readCard(variable, series, trend)
  const { scale, unit } = displayUnit(variable)
  const points = withGaps(series.points.map((p) => ({ month: p.month, t: monthToDecimalYear(p.month), value: p.value === null ? null : p.value / scale, low: p.low, note: p.note })))
  // Monthly data: the pre-invasion test runs to the end of February 2022, so the untested shading starts on 1 March.
  const analysisEndT = window === 'pre_invasion' ? monthToDecimalYear('2022-03') - 0.5 / 12 : undefined
  const pct = series.seasonal?.pct ?? null
  const span = spanText(series, window)

  return (
    <>
      {pct !== null && series.seasonal ? (
        <div className={styles.season} data-testid="workspace-season">
          <p className={styles.number}>{signedPercent(pct)}</p>
          <p className={styles.numberLabel}>
            NO₂ over {label}, March to August 2022, against the {series.seasonal.baselineLabel} average of the same months.
            <span className={styles.quiet}> This describes one season. It is not a test.</span>
          </p>
        </div>
      ) : null}

      <div className={styles.record}>
        <div className={styles.recordHead}>
          <h3 className={styles.h3}>The record, month by month</h3>
          <div className={styles.periods} role="group" aria-label="Period tested">
            {WINDOWS.map((w) => (
              <button key={w.id} type="button" aria-pressed={window === w.id} onClick={() => onWindow(w.id)} data-testid={`workspace-window-${w.id}`}>
                {w.label}
              </button>
            ))}
          </div>
        </div>
        <TrendChart
          drawOn
          compact
          height={236}
          points={points}
          unitLabel={`NO₂ (${unit})`}
          seriesLabel="Monthly mean"
          lowLabel="Under half the days observed"
          eventT={dateToDecimalYear(invasionDate)}
          eventLabel="Invasion, 24 Feb 2022"
          analysisEndT={analysisEndT}
          rateLine={rateLineFor(points, trend, reading, scale, analysisEndT)}
          rateDashed={reading.verdict !== 'significant'}
          formatValue={(v) => `${fmt(v)} ${unit}`}
          ariaLabel={`Monthly NO₂ over ${label}. ${reading.sentence}`}
        />
        <ul className={styles.legend} aria-label="How to read the chart">
          <li><span className={styles.keyDot} aria-hidden="true" /> Monthly mean, {unit}</li>
          <li><span className={styles.keyHollow} aria-hidden="true" /> Under half the days observed</li>
          <li><span className={styles.keyRate} aria-hidden="true" /> Estimated rate of change</li>
          <li><span className={styles.keyEvent} aria-hidden="true" /> Invasion, 24 Feb 2022</li>
        </ul>
      </div>

      <div className={styles.verdict} data-verdict={reading.verdict} data-testid="workspace-verdict">
        <p className={styles.badge}><span aria-hidden="true">{ICON[reading.verdict]}</span> {reading.badge}</p>
        <p className={styles.takeaway}>{takeaway(reading, pct, window)}</p>
        <dl className={styles.facts}>
          {reading.rateText ? <div><dt>Rate of change</dt><dd>{reading.rateText}</dd></div> : null}
          {reading.intervalText ? <div><dt>95% range</dt><dd>{reading.intervalText}</dd></div> : null}
          {reading.pText ? <div><dt>p-value</dt><dd>{reading.pText}</dd></div> : null}
          {span ? <div><dt>{reading.verdict === 'not_assessed' ? 'Record' : 'Tested'}</dt><dd>{span}</dd></div> : null}
        </dl>
      </div>
    </>
  )
}
