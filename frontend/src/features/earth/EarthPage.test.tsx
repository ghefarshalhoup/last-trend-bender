import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, makeStudy } from '../../test/fixtures'
import variablesJson from '../../test/fixtures/variables.json'
import EarthPage from './EarthPage'

// The map needs WebGL, which the test browser does not have. The page's states are what is tested here.
vi.mock('./EarthMap', () => ({
  EarthMap: ({ view, placeId, insets }: { view: string; placeId: string | null; insets: { left: number; bottom: number } }) => (
    <div data-testid="map" data-view={view} data-place={placeId ?? ''} data-left={insets.left} />
  ),
}))
vi.mock('./Starfield', () => ({ Starfield: () => null }))

function serve() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url)
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (u.includes('/api/cases')) return json(casesFixture)
    if (u.includes('/api/variables')) return json(variablesJson)
    if (u.includes('/api/trends')) return json({ status: 'not_available', results: [] })
    if (u.includes('/api/air/kyiv')) return json(makeStudy())
    return json({ error: { message: 'not found' } }, 404)
  }))
}

describe('the Earth view', () => {
  beforeEach(() => serve())

  it('opens on the Earth with one case and no evidence', () => {
    render(<EarthPage />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The Last Trend Bender')
    expect(screen.getByTestId('map')).toHaveAttribute('data-view', 'earth')
    expect(screen.queryByTestId('workspace')).not.toBeInTheDocument()
  })

  it('goes from the Earth to the case, to Kyiv, to the evidence, and back', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByTestId('open-case'))
    expect(screen.getByTestId('map')).toHaveAttribute('data-view', 'case')

    // Kyiv is listed first; nothing is investigated until a place is chosen.
    const first = (await screen.findAllByRole('button', { pressed: false })).find((b) => b.dataset.testid?.startsWith('list-place-'))
    expect(first).toHaveAttribute('data-testid', 'list-place-kyiv_no2_box')
    expect(screen.queryByTestId('start-investigation')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('list-place-kyiv_no2_box'))
    expect(screen.getByTestId('map')).toHaveAttribute('data-place', 'kyiv_no2_box')
    await user.click(screen.getByTestId('start-investigation'))

    const sheet = await screen.findByTestId('workspace')
    expect(within(sheet).getByRole('heading', { level: 2 })).toHaveTextContent('Did lower NO₂ over Kyiv in 2022 mean a lasting change?')
    // The season is shown as a description, and the verdict comes from the study's own trend result.
    expect(await within(sheet).findByTestId('workspace-season')).toHaveTextContent(/%/)
    expect(within(sheet).getByTestId('workspace-season')).toHaveTextContent('It is not a test')
    expect(within(sheet).getByTestId('workspace-verdict')).toBeInTheDocument()
    // The workspace takes screen space, and the camera is told how much.
    expect(Number(screen.getByTestId('map').getAttribute('data-left'))).toBeGreaterThan(0)

    await user.click(within(sheet).getByTestId('close-workspace'))
    expect(screen.queryByTestId('workspace')).not.toBeInTheDocument()
    expect(screen.getByTestId('map')).toHaveAttribute('data-place', 'kyiv_no2_box')

    await user.click(screen.getByTestId('back-to-earth'))
    expect(screen.getByTestId('map')).toHaveAttribute('data-view', 'earth')
    expect(screen.getByTestId('map')).toHaveAttribute('data-place', '')
  })

  it('says why a place has no NO₂ record instead of showing an empty chart', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByTestId('open-case'))
    await user.click(await screen.findByTestId('list-place-poland_krakow'))
    await user.click(screen.getByTestId('start-investigation'))
    expect(await screen.findByTestId('workspace-no-data')).toHaveTextContent(/Not collected/)
  })
})
