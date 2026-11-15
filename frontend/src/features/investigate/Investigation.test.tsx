import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, makeStudy } from '../../test/fixtures'
import variablesJson from '../../test/fixtures/variables.json'
import weatherJson from '../../test/fixtures/air-weather-trimmed.json'
import fireJson from '../../test/fixtures/fire-trimmed.json'
import { AtlasPage } from '../atlas/AtlasPage'
import { hasDataFor, type VariableCatalog, type VariableEntry } from './catalog'
import { endpointFor, readSeries, type TrendResult, type TrendsPayload } from './series'
import { fmt, readCard } from './verdict'

const catalog = variablesJson as unknown as VariableCatalog
const variable = (id: string) => catalog.variables.find((v) => v.metric_id === id) as VariableEntry

function trendRow(over: Partial<TrendResult> = {}): TrendResult {
  return {
    region_id: 'kyiv_no2_box', metric_id: 'ws10m', window_id: 'full_record', status: 'assessed',
    start_month: '2015-01', end_month: '2022-12', n_months: 96, slope_per_year: -0.05, ci_low: -0.08, ci_high: -0.02,
    p_value: 0.004, p_value_fdr: 0.03, significant: true, method: 'Month-fixed-effects OLS, Newey-West HAC', caveats: [],
    ...over,
  }
}

function serve(trends: TrendsPayload | 'missing' = 'missing') {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url)
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (u.includes('/api/cases')) return json(casesFixture)
    if (u.includes('/api/variables')) return json(variablesJson)
    if (u.includes('/api/trends')) return trends === 'missing' ? json({ status: 'not_available', results: [] }) : json(trends)
    if (u.includes('/api/air/kyiv')) return json(makeStudy())
    if (u.includes('/api/air/weather')) return json(weatherJson)
    return json({ error: { message: 'not found' } }, 404)
  }))
}

async function openAtlas() {
  const user = userEvent.setup()
  render(<AtlasPage />)
  await screen.findByTestId('place-kyiv_no2_box')
  return user
}

describe('phase 1: place and period', () => {
  beforeEach(() => serve())

  it('starts with place pins, the two reviewed periods, and no cards', async () => {
    await openAtlas()
    expect(screen.getByTestId('place-donbas_kharkiv_east')).toBeInTheDocument()
    expect(screen.queryByTestId('place-poland_krakow')).not.toBeInTheDocument()
    expect(screen.getByTestId('compare-poland_krakow')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('window-full_record')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByTestId('card-area')).not.toBeInTheDocument()
  })

  it('Investigate asks for a place first, then opens phase 2 with the box drawn', async () => {
    const user = await openAtlas()
    await user.click(screen.getByTestId('investigate'))
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('Choose a place on the map first')
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    expect(screen.getByTestId('place-box')).toBeInTheDocument()
    await user.click(screen.getByTestId('investigate'))
    expect(screen.getByTestId('card-area')).toBeInTheDocument()
    expect(screen.getByTestId('chosen-place')).toHaveTextContent('Kyiv city')
  })
})

describe('phase 2: variables as cards', () => {
  it('a variable opens a card; without a trend result it says "not assessed" and shows no rate', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    await user.click(screen.getByTestId('variable-ws10m'))
    const card = screen.getByTestId('card-ws10m')
    expect(await within(card).findByTestId('card-verdict')).toHaveTextContent('Not assessed')
    expect(within(card).queryByTestId('card-rate')).not.toBeInTheDocument()
    expect(within(card).getByTestId('card-seasonal')).toHaveTextContent('vs 2015–2019')
  })

  it('a trend result from /api/trends sets the badge, rate and range', async () => {
    serve({ status: 'available', results: [trendRow()] })
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    await user.click(screen.getByTestId('variable-ws10m'))
    const card = screen.getByTestId('card-ws10m')
    expect(await within(card).findByTestId('card-verdict')).toHaveTextContent('Significant fall')
    expect(within(card).getByTestId('card-rate')).toHaveTextContent('−0.0500 m/s per year')
    await user.click(screen.getByTestId('card-flip-ws10m'))
    expect(within(card).getByTestId('card-back')).toHaveTextContent('after correcting for many tests: 0.030')
  })

  it('the period switch reads the matching result', async () => {
    serve({ status: 'available', results: [trendRow(), trendRow({ window_id: 'pre_invasion', significant: false, p_value: 0.4 })] })
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    await user.click(screen.getByTestId('variable-ws10m'))
    await within(screen.getByTestId('card-ws10m')).findByText(/Significant fall/)
    await user.click(screen.getByTestId('window-pre_invasion'))
    expect(within(screen.getByTestId('card-ws10m')).getByTestId('card-verdict')).toHaveTextContent('No significant trend')
  })

  it('variables without data for the place say so and do not open', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-donbas_kharkiv_east'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    expect(screen.getByTestId('variable-no2_mean_molec_cm2')).toHaveAttribute('aria-disabled', 'true')
    await user.click(screen.getByTestId('variable-no2_mean_molec_cm2'))
    expect(screen.queryByTestId('card-no2_mean_molec_cm2')).not.toBeInTheDocument()
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('Not collected: NO₂ was not requested')
  })

  it('compare: the same variable opens in both halves, each with its own place', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('compare-poland_krakow'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    await user.click(screen.getByTestId('variable-ws10m'))
    const main = screen.getByTestId('half-main')
    const other = screen.getByTestId('half-compare')
    expect(main).toHaveTextContent('Kyiv city')
    expect(other).toHaveTextContent('Kraków, Poland')
    expect(within(main).getByTestId('card-ws10m')).toBeInTheDocument()
    expect(within(other).getByTestId('card-ws10m')).toBeInTheDocument()
    await user.click(screen.getByTestId('compare-poland_krakow'))
    expect(screen.queryByTestId('half-compare')).not.toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(1)
  })

  it('at most three cards', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    for (const id of ['no2_mean_molec_cm2', 'ws10m', 'cloud_amt', 'ps', 'clrsky_sfc_sw_dwn']) await user.click(screen.getByTestId(`variable-${id}`))
    expect(screen.getAllByRole('article')).toHaveLength(3)
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('Up to 3 cards')
    await user.click(screen.getByTestId('card-remove-cloud_amt'))
    expect(screen.getAllByRole('article')).toHaveLength(2)
  })

  it('Kyiv NO₂ with wind and cloud: the portrait quotes each card', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByTestId('place-kyiv_no2_box'))
    await user.click(screen.getByTestId('investigate'))
    await user.click(screen.getByTestId('element-air'))
    for (const id of ['no2_mean_molec_cm2', 'ws10m', 'cloud_amt']) await user.click(screen.getByTestId(`variable-${id}`))
    const no2 = screen.getByTestId('card-no2_mean_molec_cm2')
    expect(await within(no2).findByTestId('card-verdict')).toHaveTextContent('No significant trend')
    expect(within(no2).getByTestId('card-seasonal')).toHaveTextContent('−28.0% vs 2015–2019')
    expect(screen.getByTestId('card-ws10m')).toBeInTheDocument()
    expect(screen.getByTestId('card-cloud_amt')).toBeInTheDocument()
    // the portrait opens the guide's insights: one per card, read from the card's own fields
    await user.click(screen.getByTestId('avatar-button'))
    const panel = await screen.findByTestId('avatar-panel')
    expect(await within(panel).findByTestId('insight-no2_mean_molec_cm2-kyiv_no2_box')).toHaveTextContent('did not detect a clear trend over Mar 2015 – Aug 2022')
    expect(within(panel).getByTestId('insight-no2_mean_molec_cm2-kyiv_no2_box')).toHaveTextContent('Separately, March–August 2022 averaged 28% below')
    expect(screen.getByTestId('avatar-badge')).toHaveTextContent('3')
    await user.click(screen.getByTestId('avatar-close'))
    expect(screen.queryByTestId('avatar-panel')).not.toBeInTheDocument()
  })

  it('the field guide lists the chosen element’s variables with definitions and follows the element', async () => {
    serve()
    const user = await openAtlas()
    await user.click(screen.getByRole('button', { name: /field guide/i }))
    expect(screen.getByTestId('variable-guide-empty')).toBeInTheDocument()
    await user.click(screen.getByTestId('element-air'))
    expect(screen.getByTestId('variable-guide')).toHaveAttribute('data-element', 'air')
    expect(screen.getByTestId('define-no2_mean_molec_cm2')).toHaveTextContent('nitrogen dioxide')
    expect(screen.getByTestId('define-ws10m')).toHaveTextContent('wind')
    // switching the element off empties the letter again (the browser test covers switching to another element)
    await user.click(screen.getByTestId('element-air'))
    expect(screen.getByTestId('variable-guide-empty')).toBeInTheDocument()
  })
})

describe('adapters', () => {
  it('Kyiv NO₂ carries its own verdict, scaled to ×10¹⁵', () => {
    const series = readSeries(variable('no2_mean_molec_cm2'), 'kyiv_no2_box', makeStudy())!
    const r = readCard(variable('no2_mean_molec_cm2'), series, series.embeddedTrends.full_record)
    expect(r.verdict).toBe('not_significant')
    expect(r.rateText).toBe('−0.0418 ×10¹⁵ molecules/cm² per year')
    expect(readSeries(variable('no2_mean_molec_cm2'), 'poland_krakow', makeStudy())).toBeNull()
  })

  it('fire: four seasons only, so not assessed with the reason; 2019–2021 is the baseline', () => {
    const v = variable('fire_type0_per_1k_km2_day')
    const series = readSeries(v, 'kyiv_no2_box', fireJson)!
    expect(series.points).toHaveLength(24)
    expect(series.seasonal?.baselineLabel).toBe('2019–2021')
    const r = readCard(v, series, undefined)
    expect(r.verdict).toBe('not_assessed')
    expect(r.sentence).toBe('Only 4 years of data: too short for a trend test.')
    expect(r.rateText).toBeNull()
  })

  it('temperatures: a difference in °C, never a percent', () => {
    const v = variable('t2m')
    const series = readSeries(v, 'kyiv_no2_box', fireJson)!
    const r = readCard(v, series, undefined)
    expect(r.seasonalText).toMatch(/°C vs 2015–2019$/)
    expect(r.seasonalNote).toBe('Shown as a difference, not a percent.')
  })

  it('an insufficient-evidence result is not a verdict', () => {
    const v = variable('ws10m')
    const series = readSeries(v, 'kyiv_no2_box', weatherJson)!
    const r = readCard(v, series, trendRow({ status: 'insufficient_evidence', slope_per_year: null, significant: null }))
    expect([r.verdict, r.rateText, r.pText]).toEqual(['not_assessed', null, null])
  })

  it('formats with a true minus and three significant digits', () => {
    expect(fmt(-0.04178, true)).toBe('−0.0418')
    expect(fmt(12.345, true)).toBe('+12.3')
    expect(fmt(0)).toBe('0')
  })
})

describe('regional NO₂', () => {
  const payload = {
    regions: {
      poland_krakow: {
        monthly_series: [
          { month: '2022-03', value: 3.1e15, valid_days: 9, calendar_days: 31, flagged_below_50_pct: true },
          { month: '2022-04', value: null, valid_days: 0, calendar_days: 30, flagged_below_50_pct: true },
        ],
        seasonal_mar_aug: { vs_2015_2019: { abs_diff: -3e14, pct_change: -11.0, pct_change_status: 'computed' } },
      },
    },
  }

  it('reads a place beyond Kyiv with coverage flags and the 2022 comparison', () => {
    const series = readSeries(variable('no2_mean_molec_cm2'), 'poland_krakow', payload)
    expect(series?.points).toEqual([
      { month: '2022-03', value: 3.1e15, low: true, note: '9/31 days observed' },
      { month: '2022-04', value: null, low: true, note: '0/30 days observed' },
    ])
    expect(series?.seasonal).toMatchObject({ baselineLabel: '2015–2019', pct: -11.0 })
    expect(readSeries(variable('no2_mean_molec_cm2'), 'west_ukraine_cand', payload)).toBeNull()
  })

  it('asks the regional file for other places and the Kyiv study for Kyiv', () => {
    expect(endpointFor(variable('no2_mean_molec_cm2'), 'poland_krakow')).toBe('/api/air/no2')
    expect(endpointFor(variable('no2_mean_molec_cm2'), 'kyiv_no2_box')).toBe('/api/air/kyiv')
    const extra = new Map([['t2m|czechia_prague', '/api/weather/comparison']])
    expect(endpointFor(variable('t2m'), 'czechia_prague', extra)).toBe('/api/weather/comparison')
    expect(endpointFor(variable('t2m'), 'kyiv_north_belt', extra)).toBe('/api/fire/ukraine')
    expect(hasDataFor(variable('t2m'), 'czechia_prague', extra)).toBe(true)
    expect(hasDataFor(variable('no2_mean_molec_cm2'), 'poland_krakow', new Map([['no2_mean_molec_cm2|poland_krakow', '/api/air/no2']]))).toBe(true)
    expect(hasDataFor(variable('ws10m'), 'kharkiv_city', new Map([['no2_mean_molec_cm2|kharkiv_city', '/api/air/no2']]))).toBe(false)
  })
})
