import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, makeStudy } from '../../test/fixtures'
import { AtlasPage } from './AtlasPage'
import { readAir } from './layers/air/airReading'
import { colourFor, SCALE_COLOURS } from './layers/air/colourScale'

function serve(study = makeStudy()) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const body = String(url).includes('/api/cases') ? casesFixture : study
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
}
async function openAir() {
  const user = userEvent.setup()
  render(<AtlasPage />)
  await user.click(await screen.findByTestId('element-air'))
  await screen.findByTestId('kyiv-polygon')
  return user
}

describe('illustrated atlas: Air through the layer structure', () => {
  beforeEach(() => serve())

  it('starts neutral: base map, no layer, no controls, no evidence widget', async () => {
    render(<AtlasPage />)
    expect(await screen.findByTestId('atlas-base')).toBeInTheDocument()
    expect(screen.queryByTestId('kyiv-polygon')).not.toBeInTheDocument()
    expect(screen.queryByTestId('layer-controls')).not.toBeInTheDocument()
    expect(screen.queryByTestId('evidence-widget')).not.toBeInTheDocument()
  })

  it('reveals the Kyiv polygon with the seasonal comparison and a fixed key', async () => {
    await openAir()
    expect(screen.getByTestId('kyiv-value')).toHaveTextContent('−28.0% vs 2015–2019')
    expect(screen.getByTestId('air-key')).toBeInTheDocument()
    expect(screen.getByTestId('kyiv-polygon')).toHaveAttribute('data-fill', colourFor(-27.96) as string)
  })

  it('April updates map, evidence and guide together and keeps the coverage warning', async () => {
    const user = await openAir()
    const shape = screen.getByTestId('kyiv-polygon').getAttribute('d')
    await user.click(screen.getByTestId('period-4'))
    expect(screen.getByTestId('kyiv-value')).toHaveTextContent('−37.0% vs 2015–2019')
    expect(screen.getByTestId('kyiv-label')).toHaveTextContent('8/30 days')
    expect(screen.getByTestId('kyiv-label-warning')).toHaveTextContent('low coverage')
    expect(screen.getByTestId('kyiv-low-coverage')).toBeInTheDocument()
    expect(screen.getByTestId('evidence-value')).toHaveTextContent('−37.0%')
    expect(screen.getByTestId('evidence-low-coverage')).toHaveTextContent('8 of 30 days')
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('only 8 of 30 days')
    // position and shape never change with the selection
    expect(screen.getByTestId('kyiv-polygon').getAttribute('d')).toBe(shape)
  })

  it('switching baseline changes the comparison everywhere', async () => {
    const user = await openAir()
    await user.click(screen.getByTestId('period-4'))
    await user.click(within(screen.getByTestId('comparison-sensitivity_2019_2021_valid_day')).getByRole('radio'))
    expect(screen.getByTestId('kyiv-value')).toHaveTextContent('−33.2% vs 2019–2021')
    expect(screen.getByTestId('evidence-value')).toHaveTextContent('−33.2%')
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('2019–2021')
  })

  it('selecting the study area is reflected in the map, evidence and guide', async () => {
    const user = await openAir()
    await user.click(screen.getByTestId('kyiv-label'))
    expect(screen.getByTestId('kyiv-label')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('evidence-area')).toBeInTheDocument()
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('whole Kyiv study area')
  })

  it('clearing the element returns to the neutral atlas', async () => {
    const user = await openAir()
    await user.click(screen.getByTestId('clear-element'))
    expect(screen.queryByTestId('kyiv-polygon')).not.toBeInTheDocument()
    expect(screen.queryByTestId('evidence-widget')).not.toBeInTheDocument()
    expect(screen.getByTestId('atlas-base')).toBeInTheDocument()
  })
})

describe('Air adapter', () => {
  it('keeps a missing comparison missing instead of drawing zero', async () => {
    serve(makeStudy((s) => {
      const april = s.result.matched_months.find((m) => m.calendar_month === 4)!
      april.vs_primary_2015_2019 = { absolute_change_molec_cm2: null, pct_change: null, pct_change_status: 'withheld_missing_data' }
    }))
    const user = await openAir()
    await user.click(screen.getByTestId('period-4'))
    expect(screen.getByTestId('kyiv-value')).toHaveTextContent('No comparison available')
    expect(screen.getByTestId('kyiv-polygon')).toHaveAttribute('data-fill', 'no-value')
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent('not a zero')
  })

  it('reads numbers straight from the API result', () => {
    const study = makeStudy()
    const april = readAir(study, { period: '4', comparison: 'primary_2015_2019_valid_day', feature: null })
    expect(april.pct).toBe(study.result.matched_months.find((m) => m.calendar_month === 4)!.vs_primary_2015_2019.pct_change)
    expect([april.validDays, april.calendarDays, april.lowCoverage]).toEqual([8, 30, true])
  })

  it('uses a fixed scale that clamps beyond ±50%', () => {
    expect(colourFor(-80)).toBe(SCALE_COLOURS[0])
    expect(colourFor(-5)).toBe(SCALE_COLOURS[4])
    expect(colourFor(5)).toBe(SCALE_COLOURS[5])
    expect(colourFor(80)).toBe(SCALE_COLOURS[9])
    expect(colourFor(null)).toBeNull()
  })
})
