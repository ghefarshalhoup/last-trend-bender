import { useEffect, useMemo, useState } from 'react'
import { dateToDecimalYear, monthToDecimalYear, type TimelinePoint } from '../atlas/TrendChart'
import definitions from '../atlas/variableDefinitions.json'
import type { ElementId } from '../explorer/elements'
import { hasDataFor, placeLabel, type ExtraSupport, type PlaceFeature, type VariableCatalog, type VariableEntry } from '../investigate/catalog'
import { endpointFor, readSeries, spanText, trendKey, type TrendResult, type VariableSeries } from '../investigate/series'
import { usePayloads, type PayloadState } from '../investigate/usePayloads'
import { rateLineFor, withGaps } from '../investigate/VariableCard'
import { displayUnit, fmt, pickTrend, readCard, type CardReading } from '../investigate/verdict'
import { GlassChart, type ChartSeries } from './GlassChart'
import styles from './GlassCards.module.css'

export const MAX_CARDS = 4
/** Main place first, then up to two comparisons. Validated for the dark surface (dataviz palette check). */
export const PLACE_COLORS = ['#2a93d4', '#bb8c22', '#9b73e8'] as const

const DEFS = new Map((definitions as { metric_id: string; definition: string }[]).map((d) => [d.metric_id, d.definition]))
const ELEMENT_NAMES: Record<ElementId, string> = { air: 'Air', fire: 'Fire', land: 'Earth', water: 'Water' }
const ICON = { significant: '●', not_significant: '○', not_assessed: '–' } as const

interface Props {
  place: PlaceFeature
  compare: string[]
  catalog: VariableCatalog
  trendIndex: Map<string, TrendResult>
  extra: ExtraSupport
  metrics: string[]
  onMetrics: (ids: string[]) => void
  /** Evidence takes most of the screen as a 2 × 2 grid; the map keeps the rest. */
  expanded: boolean
  onExpanded: (expanded: boolean) => void
}

interface PlaceRead {
  placeId: string
  color: string
  state: 'loading' | 'error' | 'none' | 'ready'
  series: VariableSeries | null
  reading: CardReading | null
  trend: TrendResult | undefined
}

function readPlace(variable: VariableEntry, placeId: string, color: string, extra: ExtraSupport, trendIndex: Map<string, TrendResult>, states: Record<string, PayloadState>): PlaceRead {
  if (!hasDataFor(variable, placeId, extra)) return { placeId, color, state: 'none', series: null, reading: null, trend: undefined }
  const payload = states[endpointFor(variable, placeId, extra)]
  if (!payload || payload.status === 'loading') return { placeId, color, state: 'loading', series: null, reading: null, trend: undefined }
  if (payload.status === 'error') return { placeId, color, state: 'error', series: null, reading: null, trend: undefined }
  const series = readSeries(variable, placeId, payload.data)
  if (!series) return { placeId, color, state: 'none', series: null, reading: null, trend: undefined }
  // Always the full record: the period is not a choice in this view.
  const trend = pickTrend(trendIndex.get(trendKey(placeId, variable.metric_id, 'full_record')), series, 'full_record')
  return { placeId, color, state: 'ready', series, reading: readCard(variable, series, trend), trend }
}

/** The left column of glass cards: one card per variable, every chosen place drawn in the same card. */
export function GlassCards({ place, compare, catalog, trendIndex, extra, metrics, onMetrics, expanded, onExpanded }: Props) {
  const placeId = place.properties.region_id
  const placeIds = useMemo(() => [placeId, ...compare.filter((c) => c !== placeId)], [placeId, compare])
  const chosen = useMemo(() => metrics.map((m) => catalog.variables.find((v) => v.metric_id === m)).filter((v): v is VariableEntry => Boolean(v)), [metrics, catalog.variables])
  const endpoints = useMemo(() => {
    const set = new Set<string>()
    for (const v of chosen) for (const p of placeIds) if (hasDataFor(v, p, extra)) set.add(endpointFor(v, p, extra))
    return [...set]
  }, [chosen, placeIds, extra])
  const { states, retry } = usePayloads(endpoints)
  const [picking, setPicking] = useState(false)
  // Expanded charts share the screen height: two rows of cards, each with about 200 px of title, units and verdicts.
  const [viewH, setViewH] = useState(() => (typeof window === 'undefined' ? 900 : window.innerHeight))
  useEffect(() => {
    const onResize = () => setViewH(window.innerHeight)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  const expandedChartH = Math.round(Math.min(240, Math.max(140, (viewH - 170) / 2 - 205)))

  const available = useMemo(
    () => [...catalog.variables].filter((v) => hasDataFor(v, placeId, extra)).sort((a, b) => a.display_order - b.display_order),
    [catalog.variables, placeId, extra],
  )
  const full = metrics.length >= MAX_CARDS
  const toggle = (id: string) => {
    if (metrics.includes(id)) onMetrics(metrics.filter((m) => m !== id))
    else if (!full) onMetrics([...metrics, id])
  }

  return (
    <section className={styles.column} data-expanded={expanded} aria-label={`Evidence for ${placeLabel(placeId)}`} data-testid="cards">
      <header className={styles.head}>
        <p className={styles.place}>
          {placeIds.map((id, i) => (
            <span key={id} className={styles.placeKey}>
              <span className={styles.swatch} style={{ background: PLACE_COLORS[i] }} aria-hidden="true" />
              {placeLabel(id)}
            </span>
          ))}
        </p>
        <div className={styles.headActions}>
          <button type="button" className={styles.add} aria-expanded={picking} onClick={() => setPicking((p) => !p)} data-testid="add-variable">
            Variables {metrics.length}/{MAX_CARDS}
          </button>
          <button type="button" className={styles.expand} aria-pressed={expanded} onClick={() => onExpanded(!expanded)} data-testid="expand-evidence">
            {expanded ? 'Return to map' : 'Expand evidence'}
          </button>
        </div>
      </header>

      {picking ? (
        <div className={styles.picker} data-testid="variable-picker">
          {(['air', 'fire', 'land', 'water'] as ElementId[]).map((el) => {
            const list = available.filter((v) => v.element_id === el)
            if (!list.length) return null
            return (
              <fieldset key={el} className={styles.group}>
                <legend>{ELEMENT_NAMES[el]}</legend>
                {list.map((v) => {
                  const on = metrics.includes(v.metric_id)
                  return (
                    <label key={v.metric_id} className={styles.option} data-disabled={!on && full}>
                      <input type="checkbox" checked={on} disabled={!on && full} onChange={() => toggle(v.metric_id)} data-testid={`pick-${v.metric_id}`} />
                      <span>{v.short_label}</span>
                    </label>
                  )
                })}
              </fieldset>
            )
          })}
          <p className={styles.pickerNote}>{full ? `Four at a time. Remove one to add another.` : `Variables with a record for ${placeLabel(placeId)}.`}</p>
          <button type="button" className={styles.done} onClick={() => setPicking(false)}>Done</button>
        </div>
      ) : null}

      {chosen.length === 0 ? <p className={styles.empty}>Choose up to four variables to compare.</p> : null}
      <div className={styles.stack}>
        {chosen.map((v, i) => (
          <GlassCard
            key={v.metric_id}
            index={i}
            variable={v}
            reads={placeIds.map((p, j) => readPlace(v, p, PLACE_COLORS[j] ?? '#888', extra, trendIndex, states))}
            invasionDate={catalog.conflict_start}
            expanded={expanded}
            chartHeight={expanded ? expandedChartH : 150}
            onRemove={() => toggle(v.metric_id)}
            onRetry={() => endpoints.forEach((e) => states[e]?.status === 'error' && retry(e))}
          />
        ))}
      </div>
    </section>
  )
}

interface CardProps {
  index: number
  variable: VariableEntry
  reads: PlaceRead[]
  invasionDate: string
  expanded: boolean
  chartHeight: number
  onRemove: () => void
  onRetry: () => void
}

function GlassCard({ index, variable, reads, invasionDate, expanded, chartHeight, onRemove, onRetry }: CardProps) {
  const [flipped, setFlipped] = useState(false)
  const main = reads[0] as PlaceRead
  const { scale, unit } = displayUnit(variable)
  const toPoints = (s: VariableSeries): TimelinePoint[] =>
    withGaps(s.points.map((p) => ({ month: p.month, t: monthToDecimalYear(p.month), value: p.value === null ? null : p.value / scale, low: p.low, note: p.note })))
  const chartSeries: ChartSeries[] = reads.filter((r) => r.series).map((r) => ({ id: r.placeId, label: placeLabel(r.placeId), color: r.color, points: toPoints(r.series as VariableSeries) }))
  const mainPoints = chartSeries[0]?.id === main.placeId ? chartSeries[0].points : []
  const rateLine = main.reading && mainPoints.length ? rateLineFor(mainPoints, main.trend, main.reading, scale) : null
  const span = main.series ? spanText(main.series, 'full_record') : null

  return (
    <article className={styles.card} data-flipped={flipped} style={{ animationDelay: `${index * 90}ms` }} data-testid={`card-${variable.metric_id}`}>
      <div className={styles.inner}>
        <div className={styles.front} aria-hidden={flipped}>
          <div className={styles.cardHead}>
            <h3 className={styles.title}>{variable.short_label}</h3>
            <div className={styles.actions}>
              <button type="button" className={styles.icon} onClick={() => setFlipped(true)} aria-label={`Details for ${variable.short_label}`} tabIndex={flipped ? -1 : 0} data-testid="flip">
                <span aria-hidden="true">↻</span>
              </button>
              <button type="button" className={styles.icon} onClick={onRemove} aria-label={`Remove ${variable.short_label}`} tabIndex={flipped ? -1 : 0}>
                <span aria-hidden="true">×</span>
              </button>
            </div>
          </div>
          {expanded ? (
            <>
              <p className={styles.meta} data-testid="card-meta">
                {unit}
                {span ? `, ${reads.length > 1 ? `${placeLabel(main.placeId)} ` : ''}tested ${span}` : ''}
              </p>
              <ul className={styles.verdicts} data-testid="card-verdicts">
                {reads.map((r) => (
                  <li key={r.placeId} data-verdict={r.reading?.verdict ?? 'none'}>
                    <span className={styles.swatch} style={{ background: r.color }} aria-hidden="true" />
                    <span className={styles.vPlace}>{placeLabel(r.placeId)}</span>
                    <span className={styles.vText}>
                      {r.reading ? (
                        <>
                          <span aria-hidden="true">{ICON[r.reading.verdict]}</span> {r.reading.badge}
                        </>
                      ) : r.state === 'none' ? (
                        'No record'
                      ) : r.state === 'error' ? (
                        'Did not load'
                      ) : (
                        'Loading…'
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : main.reading ? (
            <p className={styles.verdict} data-verdict={main.reading.verdict} data-testid="card-verdict">
              <span aria-hidden="true">{ICON[main.reading.verdict]}</span> {main.reading.badge}
            </p>
          ) : null}
          {main.state === 'loading' ? <p className={styles.note} role="status">Loading…</p> : null}
          {main.state === 'error' ? (
            <p className={styles.note} role="alert">
              The record did not load. <button type="button" className={styles.inline} onClick={onRetry}>Try again</button>
            </p>
          ) : null}
          {main.state === 'none' ? <p className={styles.note}>No record for {placeLabel(main.placeId)}.</p> : null}
          {chartSeries.length ? (
            <GlassChart
              series={chartSeries}
              rateLine={rateLine}
              rateDashed={main.reading?.verdict !== 'significant'}
              eventT={dateToDecimalYear(invasionDate)}
              formatValue={(v) => `${fmt(v)} ${unit}`}
              ariaLabel={`${variable.label}, monthly. ${main.reading?.sentence ?? ''}`}
              height={chartHeight}
              large={expanded}
            />
          ) : null}
        </div>

        <div className={styles.back} aria-hidden={!flipped} data-testid="card-back">
          <div className={styles.cardHead}>
            <h3 className={styles.title}>{variable.label}</h3>
            <button type="button" className={styles.icon} onClick={() => setFlipped(false)} aria-label="Back to the chart" tabIndex={flipped ? 0 : -1}>
              <span aria-hidden="true">↺</span>
            </button>
          </div>
          {DEFS.get(variable.metric_id) ? <p className={styles.def}>{DEFS.get(variable.metric_id)}</p> : null}
          <dl className={styles.facts}>
            {main.reading?.rateText ? <div><dt>Rate</dt><dd>{main.reading.rateText}</dd></div> : null}
            {main.reading?.intervalText ? <div><dt>95% range</dt><dd>{main.reading.intervalText}</dd></div> : null}
            {main.reading?.pText ? <div><dt>p-value</dt><dd>{main.reading.pText}</dd></div> : null}
            {main.reading?.pFdrText ? <div><dt>p, corrected for many tests</dt><dd>{main.reading.pFdrText}</dd></div> : null}
            {span ? <div><dt>Tested</dt><dd>{span}</dd></div> : null}
          </dl>
          {main.reading && main.reading.verdict === 'not_assessed' ? <p className={styles.def}>{main.reading.sentence}</p> : null}
          {reads.length > 1 ? (
            <ul className={styles.others}>
              {reads.slice(1).map((r) => (
                <li key={r.placeId}>
                  <span className={styles.swatch} style={{ background: r.color }} aria-hidden="true" />
                  {placeLabel(r.placeId)}: {r.reading ? r.reading.badge.toLowerCase() : r.state === 'none' ? 'no record' : 'loading'}
                  {r.reading?.pText ? `, p ${r.reading.pText}` : ''}
                  {r.reading?.pFdrText ? ` (${r.reading.pFdrText} corrected)` : ''}
                </li>
              ))}
            </ul>
          ) : null}
          <p className={styles.source}>{variable.sources.join('; ')}. Monthly means over the study box. Tested on the full record.</p>
        </div>
      </div>
    </article>
  )
}
