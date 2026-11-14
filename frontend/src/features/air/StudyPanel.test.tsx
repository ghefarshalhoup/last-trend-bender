import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useMemo, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { DEFAULT_BASELINE, getSeasonalSummary, type BaselineOption } from '../../adapters/baselines'
import { buildMonthRows } from '../../adapters/months'
import type { StudyPackage } from '../../api/types'
import { makeCatalog, makeStudy } from '../../test/fixtures'
import { StudyPanel } from './StudyPanel'

/** Same wiring the explorer uses: baseline and month are separate state. */
function Harness({ study }: { study: StudyPackage }) {
  const [baseline, setBaseline] = useState<BaselineOption>(DEFAULT_BASELINE)
  const [month, setMonth] = useState<number | null>(null)
  const summary = useMemo(() => getSeasonalSummary(study.result, baseline), [study, baseline])
  const rows = useMemo(() => buildMonthRows(study.result.matched_months, baseline), [study, baseline])
  return (
    <StudyPanel
      study={study}
      elements={makeCatalog().elements}
      baseline={baseline}
      onBaselineChange={setBaseline}
      summary={summary}
      rows={rows}
      selectedMonth={month}
      onSelectMonth={setMonth}
      onClose={() => {}}
      onClear={() => {}}
    />
  )
}
const renderPanel = (mutate?: (s: StudyPackage) => void) => render(<Harness study={makeStudy(mutate)} />)

describe('StudyPanel', () => {
  it('states location, variable, study period and the default primary headline', () => {
    renderPanel()
    expect(screen.getByRole('heading', { level: 2, name: 'Kyiv' })).toBeInTheDocument()
    expect(screen.getByText(/Tropospheric NO₂ column · March–August 2022/)).toBeInTheDocument()
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
    expect(screen.getByTestId('seasonal-summary')).toHaveTextContent('March–August 2022')
  })

  it('switching baseline updates headline, chart title and the monthly comparison together', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByTestId('month-4'))
    expect(await screen.findByTestId('inspector-change')).toHaveTextContent('−37.0%')
    await user.click(screen.getByRole('radio', { name: /2019–2021/ }))
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−20.3%')
    expect(screen.getByTestId('seasonal-pct')).toHaveAttribute('data-baseline', 'sensitivity_2019_2021_valid_day')
    expect(screen.getByRole('heading', { name: /2022 against 2019–2021/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('inspector-change')).not.toHaveTextContent('−37.0%'))
    await user.click(screen.getByRole('radio', { name: /2015–2019/ }))
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
  })

  it('month selection opens details without changing the seasonal headline', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByTestId('month-4'))
    expect(await screen.findByTestId('inspector-title')).toHaveTextContent('April 2022')
    expect(screen.getByTestId('inspector-days')).toHaveTextContent('8 of 30 days')
    expect(screen.getByTestId('inspector-low-coverage')).toBeInTheDocument()
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
    expect(screen.getByTestId('seasonal-summary')).toHaveTextContent('March–August')
  })

  it('month picker works from the keyboard', async () => {
    const user = userEvent.setup()
    renderPanel()
    const april = screen.getByTestId('month-4')
    april.focus()
    await user.keyboard('{Enter}')
    expect(april).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps the April warning and scientific notices visible without interaction', () => {
    renderPanel()
    const warnings = screen.getByTestId('warnings')
    expect(within(warnings).getByTestId('coverage-2022-04')).toHaveTextContent(/8 of 30 days/)
    expect(within(warnings).getByText(/Before\/after significance not assessed/)).toBeInTheDocument()
    expect(within(warnings).getByText(/Causal attribution to the war: not_established/)).toBeInTheDocument()
  })

  it('never renders a missing measurement as zero and names it', async () => {
    const user = userEvent.setup()
    renderPanel((s) => {
      const may = s.result.matched_months.find((m) => m.calendar_month === 5)!
      may.target_2022.mean_molec_cm2 = null
      may.target_2022.valid_days = 0
      may.vs_primary_2015_2019 = { absolute_change_molec_cm2: null, pct_change: null, pct_change_status: 'withheld_missing_data' }
    })
    await user.click(screen.getByTestId('month-5'))
    const value = await screen.findByTestId('inspector-2022')
    expect(value).toHaveTextContent('No valid measurement')
    expect(value).not.toHaveTextContent(/^0/)
    expect(screen.getByTestId('inspector-change')).toHaveTextContent('Unavailable')
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(within(screen.getByTestId('chart-table')).getAllByText('No valid measurement').length).toBeGreaterThan(0)
  })

  it('separates seasonal before/after status from the multi-year trend', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: /Statistical status/ }))
    const ba = screen.getByTestId('stat-before-after')
    expect(within(ba).getAllByText(/Not assessed/).length).toBeGreaterThan(0)
    expect(within(ba).queryByText(/0\.555/)).not.toBeInTheDocument()
    expect(within(screen.getByTestId('stat-trend')).getByTestId('trend-pre_invasion')).toHaveTextContent('0.555')
    expect(screen.getByTestId('stat-claims')).toHaveTextContent(/not established/)
  })

  it('has expandable sources, methods, limitations and figures', async () => {
    const user = userEvent.setup()
    renderPanel()
    for (const name of [/^Sources/, /^Methods/, /^Limitations/, /^Supplementary figures/]) {
      const trigger = screen.getByRole('button', { name })
      expect(trigger).toHaveAttribute('aria-expanded', 'false')
      await user.click(trigger)
      expect(trigger).toHaveAttribute('aria-expanded', 'true')
    }
  })

  it('describes the band as variability, not a confidence interval', () => {
    renderPanel()
    expect(screen.getByText(/not a confidence interval/i)).toBeInTheDocument()
  })

  it('shows figures only from the returned charts array, with a clear message when none', async () => {
    const user = userEvent.setup()
    const { unmount } = renderPanel((s) => { s.charts = s.charts.filter((c) => c.chart_id === 'matched_months') })
    await user.click(screen.getByRole('button', { name: /^Supplementary figures/ }))
    expect(within(screen.getByTestId('figures')).getAllByRole('listitem')).toHaveLength(1)
    unmount()
    renderPanel((s) => { s.charts = [] })
    await user.click(screen.getByRole('button', { name: /^Supplementary figures/ }))
    expect(screen.getByTestId('figures-empty')).toBeInTheDocument()
  })

  it('guide narration follows baseline and month, and names elements not yet readable', async () => {
    const user = userEvent.setup()
    renderPanel()
    const guide = screen.getByTestId('avatar-intro')
    expect(guide).toHaveTextContent('−28.0%')
    expect(guide).toHaveTextContent(/significance is not assessed/)
    expect(guide).toHaveTextContent(/cause is not established/)
    expect(screen.getByTestId('guide-waiting')).toHaveTextContent(/Fire/)
    await user.click(screen.getByRole('radio', { name: /2019–2021/ }))
    expect(screen.getByTestId('guide-element')).toHaveTextContent('−20.3%')
    await user.click(screen.getByTestId('month-4'))
    expect(screen.getByTestId('guide-month')).toHaveTextContent(/8 of 30 days/)
    expect(screen.getByTestId('guide-month')).toHaveTextContent(/fewer than half/)
  })
})
