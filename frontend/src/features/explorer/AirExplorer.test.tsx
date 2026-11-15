import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, clone, studyFixture } from '../../test/fixtures'
import { ExplorerPage } from './AirExplorer'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const fetchMock = vi.fn()
const urls = () => fetchMock.mock.calls.map((c) => String(c[0]))

function serve(opts: { studyFails?: number } = {}) {
  let failures = opts.studyFails ?? 0
  fetchMock.mockImplementation(async (url: string) => {
    if (url.endsWith('/api/cases')) return json(casesFixture)
    if (url.endsWith('/api/air/kyiv')) {
      if (failures-- > 0) return json({ error: { code: 'result_unavailable', message: 'Air results are not loaded.', details: null } }, 503)
      return json(studyFixture)
    }
    return json({ error: { code: 'not_found', message: 'nope' } }, 404)
  })
}

beforeEach(() => vi.stubGlobal('fetch', fetchMock))
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals() })

async function openNeutral() {
  render(<ExplorerPage />)
  await screen.findByTestId('ukraine-map')
}
async function selectAir(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTestId('element-air'))
  await screen.findByTestId('explore-kyiv')
}

describe('neutral opening state', () => {
  it('shows the title, four elements with true availability, and no scientific content', async () => {
    serve()
    await openNeutral()
    expect(screen.getByRole('heading', { level: 1, name: 'Environmental Fingerprints of War' })).toBeInTheDocument()
    expect(screen.getByTestId('choose-prompt')).toHaveTextContent('Choose an element to explore')
    for (const id of ['air', 'fire', 'land', 'water']) expect(screen.getByTestId(`element-${id}`)).toBeInTheDocument()
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-disabled', 'false')
    for (const id of ['fire', 'land', 'water']) {
      const b = screen.getByTestId(`element-${id}`)
      expect(b).toHaveAttribute('aria-disabled', 'true')
      expect(b).toHaveTextContent('Coming later')
    }
    expect(screen.getByTestId('element-land')).toHaveTextContent('Earth')
    expect(screen.getByTestId('reset-ukraine')).toHaveTextContent('Reset Ukraine view')
    expect(screen.getByTestId('guide-bubble')).toHaveTextContent(/Choose an element/)
    expect(screen.queryByTestId('study-panel')).not.toBeInTheDocument()
    expect(screen.queryByTestId('seasonal-pct')).not.toBeInTheDocument()
    expect(screen.queryByText(/NO₂ study/)).not.toBeInTheDocument()
    expect(urls()).toEqual(['/api/cases']) // the study is not requested yet
  })

  it('legend explains the interface in the neutral state', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await user.click(screen.getByTestId('legend-toggle'))
    expect(screen.getByTestId('legend')).toHaveTextContent(/Coming later/)
    expect(screen.getByTestId('legend-toggle')).toHaveTextContent('L')
    expect(screen.getByTestId('legend-toggle')).toHaveTextContent('Legend')
  })

  it('unavailable elements do nothing when clicked', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await user.click(screen.getByTestId('element-fire'))
    expect(screen.getByTestId('element-fire')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('choose-prompt')).toBeInTheDocument()
  })

  it('reports a catalog failure and recovers on retry', async () => {
    const user = userEvent.setup()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    serve()
    render(<ExplorerPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be reached/)
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByTestId('ukraine-map')).toBeInTheDocument()
  })
})

describe('selecting Air', () => {
  it('marks Air selected, loads the study from the catalog endpoint and reveals Kyiv without opening the panel', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'true')
    expect(urls()).toEqual(['/api/cases', '/api/air/kyiv'])
    expect(screen.getByText('Kyiv · NO₂ study')).toBeInTheDocument()
    expect(screen.queryByTestId('study-panel')).not.toBeInTheDocument()
    expect(screen.getByTestId('clear-element')).toBeInTheDocument()
  })

  it('Explore Kyiv opens the evidence panel; Close hides it and keeps Air, baseline and month', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    await user.click(screen.getByTestId('explore-kyiv'))
    const panel = await screen.findByTestId('study-panel')
    expect(within(panel).getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')

    await user.click(within(panel).getByRole('radio', { name: /2019–2021/ }))
    await user.click(within(panel).getByTestId('month-4'))
    await user.click(screen.getByTestId('close-panel'))

    expect(screen.queryByTestId('study-panel')).not.toBeInTheDocument()
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Kyiv · NO₂ study')).toBeInTheDocument()

    await user.click(screen.getByTestId('explore-kyiv'))
    expect(await screen.findByTestId('seasonal-pct')).toHaveTextContent('−20.3%')
    expect(screen.getByTestId('inspector-title')).toHaveTextContent('April 2022')
  })

  it('clicking the Kyiv marker is equivalent to Explore Kyiv (keyboard is covered in the browser suite)', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    const marker = await screen.findByTitle('Explore Kyiv NO₂ study')
    await user.click(marker)
    expect(await screen.findByTestId('study-panel')).toBeInTheDocument()
  })

  it('the label on the Kyiv box follows the month and never relabels the seasonal result', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    await user.click(screen.getByTestId('explore-kyiv'))
    await screen.findByTestId('study-panel')
    expect(screen.getByText(/March–August 2022: −28\.0%/)).toBeInTheDocument()
    await user.click(screen.getByTestId('month-4'))
    expect(await screen.findByText(/April 2022: −37\.0% · 8\/30 days ▲/)).toBeInTheDocument()
    expect(screen.getByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
  })

  it('legend explains the study boundary and marker when Air is active', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    await user.click(screen.getByTestId('legend-toggle'))
    expect(screen.getByTestId('legend')).toHaveTextContent(/Study boundary/)
    expect(screen.getByTestId('legend')).toHaveTextContent(/Selected-area marker/)
  })
})

describe('clearing, resetting and failure', () => {
  it('Clear element returns to the neutral state; Reset Ukraine view changes only the camera', async () => {
    serve()
    const user = userEvent.setup()
    await openNeutral()
    await selectAir(user)
    await user.click(screen.getByTestId('explore-kyiv'))
    await screen.findByTestId('study-panel')

    await user.click(screen.getByTestId('reset-ukraine'))
    expect(screen.getByTestId('study-panel')).toBeInTheDocument()
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByTestId('clear-element'))
    expect(screen.queryByTestId('study-panel')).not.toBeInTheDocument()
    expect(screen.queryByText('Kyiv · NO₂ study')).not.toBeInTheDocument()
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('choose-prompt')).toBeInTheDocument()
  })

  it('a failed study request shows an error with retry and never shows results', async () => {
    serve({ studyFails: 1 })
    const user = userEvent.setup()
    await openNeutral()
    await user.click(screen.getByTestId('element-air'))
    const alert = await screen.findByTestId('study-error')
    expect(alert).toHaveTextContent('Air results are not loaded.')
    expect(screen.queryByTestId('explore-kyiv')).not.toBeInTheDocument()
    expect(screen.queryByTestId('seasonal-pct')).not.toBeInTheDocument()
    expect(screen.queryByText(/NO₂ study/)).not.toBeInTheDocument()

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getByTestId('explore-kyiv')).toBeInTheDocument())
    expect(screen.queryByTestId('study-error')).not.toBeInTheDocument()
  })

  it('reports contract drift as an error instead of crashing', async () => {
    const broken = clone(studyFixture) as unknown as Record<string, unknown>
    delete broken.result
    fetchMock.mockImplementation(async (url: string) => (url.endsWith('/api/cases') ? json(casesFixture) : json(broken)))
    const user = userEvent.setup()
    await openNeutral()
    await user.click(screen.getByTestId('element-air'))
    expect(await screen.findByTestId('study-error')).toHaveTextContent(/malformed at "result"/)
  })

  it('treats Air as unavailable when the catalog says its data is not ready', async () => {
    const cases = clone(casesFixture)
    cases.cases[0]!.elements[0]!.status = 'unavailable'
    cases.cases[0]!.elements[0]!.reason = 'data_not_ready'
    fetchMock.mockResolvedValue(json(cases))
    await openNeutral()
    expect(screen.getByTestId('element-air')).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByTestId('element-air')).toHaveTextContent('Data not ready')
  })
})
