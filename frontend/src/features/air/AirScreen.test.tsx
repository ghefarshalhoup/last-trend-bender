import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeBundle } from '../../test/fixtures'
import { AirScreen } from './AirScreen'

describe('AirScreen', () => {
  it('shows the question, breadcrumb, map note and default primary headline', () => {
    const bundle = makeBundle()
    render(<AirScreen bundle={bundle} />)
    expect(screen.getByRole('heading', { level: 1, name: /Was NO₂ different above Kyiv in 2022\?/ })).toBeInTheDocument()
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(crumbs).getByText('Ukraine')).toBeInTheDocument()
    expect(within(crumbs).getByText('Air — NO₂')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
    expect(screen.getByText(bundle.study.map.note)).toBeInTheDocument()
  })

  it('lists other elements as not yet available, from the catalog', () => {
    render(<AirScreen bundle={makeBundle()} />)
    const list = screen.getByRole('list', { name: /Environmental elements/ })
    expect(within(list).getAllByText('not yet available')).toHaveLength(3)
  })

  it('switching baseline updates the seasonal comparison and the chart series label', async () => {
    const user = userEvent.setup()
    render(<AirScreen bundle={makeBundle()} />)
    await user.click(screen.getByRole('radio', { name: /2019–2021/ }))
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−20.3%')
    expect(screen.getByTestId('seasonal-pct')).toHaveAttribute('data-baseline', 'sensitivity_2019_2021_valid_day')
    expect(screen.getByRole('heading', { name: /2022 against 2019–2021/ })).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /2015–2019/ }))
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
  })

  it('month selection opens details without changing the seasonal headline', async () => {
    const user = userEvent.setup()
    render(<AirScreen bundle={makeBundle()} />)
    await user.click(screen.getByTestId('month-4'))
    expect(await screen.findByTestId('inspector-title')).toHaveTextContent('April 2022')
    expect(screen.getByTestId('inspector-days')).toHaveTextContent('8 of 30 days')
    expect(screen.getByTestId('inspector-low-coverage')).toBeInTheDocument()
    expect(screen.getByTestId('inspector-change')).toHaveTextContent('−37.0%')
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
  })

  it('month picker works from the keyboard', async () => {
    const user = userEvent.setup()
    render(<AirScreen bundle={makeBundle()} />)
    const april = screen.getByTestId('month-4')
    april.focus()
    await user.keyboard('{Enter}')
    expect(april).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByTestId('inspector-title')).toHaveTextContent('April 2022')
  })

  it('keeps April coverage warning and scientific notices visible without any interaction', () => {
    render(<AirScreen bundle={makeBundle()} />)
    const warnings = screen.getByTestId('warnings')
    expect(within(warnings).getByTestId('coverage-2022-04')).toHaveTextContent(/8 of 30 days/)
    expect(within(warnings).getByText(/Before\/after significance not assessed/)).toBeInTheDocument()
    expect(within(warnings).getByText(/Causal attribution to the war: not_established/)).toBeInTheDocument()
  })

  it('never renders a missing measurement as zero and names it', async () => {
    const user = userEvent.setup()
    const bundle = makeBundle((s) => {
      const may = s.result.matched_months.find((m) => m.calendar_month === 5)!
      may.target_2022.mean_molec_cm2 = null
      may.target_2022.valid_days = 0
      may.vs_primary_2015_2019 = { absolute_change_molec_cm2: null, pct_change: null, pct_change_status: 'withheld_missing_data' }
    })
    render(<AirScreen bundle={bundle} />)
    await user.click(screen.getByTestId('month-5'))
    const value = await screen.findByTestId('inspector-2022')
    expect(value).toHaveTextContent('No valid measurement')
    expect(value).not.toHaveTextContent(/^0/)
    expect(screen.getByTestId('inspector-change')).toHaveTextContent('Unavailable')
    // Same field, different meaning: the table shows the gap too.
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(within(screen.getByTestId('chart-table')).getAllByText('No valid measurement').length).toBeGreaterThan(0)
  })

  it('separates seasonal before/after status from the multi-year trend', async () => {
    const user = userEvent.setup()
    render(<AirScreen bundle={makeBundle()} />)
    await user.click(screen.getByRole('button', { name: /Statistical status/ }))
    const ba = screen.getByTestId('stat-before-after')
    expect(within(ba).getAllByText(/Not assessed/).length).toBeGreaterThan(0)
    expect(within(ba).queryByText(/0\.555/)).not.toBeInTheDocument()
    const trend = screen.getByTestId('stat-trend')
    expect(within(trend).getByTestId('trend-pre_invasion')).toHaveTextContent('0.555')
    expect(screen.getByTestId('stat-claims')).toHaveTextContent(/not established/)
  })

  it('describes the band as variability, not a confidence interval', () => {
    render(<AirScreen bundle={makeBundle()} />)
    expect(screen.getByText(/not a confidence interval/i)).toBeInTheDocument()
  })

  it('shows supplementary figures only from the returned charts array', () => {
    render(<AirScreen bundle={makeBundle((s) => { s.charts = s.charts.filter((c) => c.chart_id === 'matched_months') })} />)
    const figures = screen.getByTestId('figures')
    expect(within(figures).getAllByRole('listitem')).toHaveLength(1)
    expect(screen.queryByTestId('figure-monthly_timeline')).not.toBeInTheDocument()
  })

  it('handles an empty charts array with a clear message', () => {
    render(<AirScreen bundle={makeBundle((s) => { s.charts = [] })} />)
    expect(screen.getByTestId('figures-empty')).toBeInTheDocument()
  })

  it('guide narration follows baseline and month, from API values', async () => {
    const user = userEvent.setup()
    render(<AirScreen bundle={makeBundle()} />)
    const guide = screen.getByTestId('avatar-intro')
    expect(guide).toHaveTextContent('−28.0%')
    expect(guide).toHaveTextContent(/character art pending/)
    expect(screen.queryByTestId('guide-month')).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: /2019–2021/ }))
    expect(screen.getByTestId('guide-element')).toHaveTextContent('−20.3%')

    await user.click(screen.getByTestId('month-4'))
    expect(screen.getByTestId('guide-month')).toHaveTextContent(/April 2022/)
    expect(screen.getByTestId('guide-month')).toHaveTextContent(/8 of 30 days/)
    expect(screen.getByTestId('guide-month')).toHaveTextContent(/fewer than half/)
    // The headline narration is not replaced by the month.
    expect(screen.getByTestId('guide-element')).toHaveTextContent('−20.3%')
  })

  it('guide is honest about causes, significance and unavailable elements', () => {
    render(<AirScreen bundle={makeBundle()} />)
    const guide = screen.getByTestId('avatar-intro')
    expect(guide).toHaveTextContent(/significance is not assessed/)
    expect(guide).toHaveTextContent(/cause is not established/)
    expect(screen.getByTestId('guide-waiting')).toHaveTextContent(/Fire/)
    expect(screen.getByTestId('guide-waiting')).not.toHaveTextContent(/Air/)
  })
})
