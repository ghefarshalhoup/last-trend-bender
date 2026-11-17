import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, makeStudy } from '../../test/fixtures'
import variablesJson from '../../test/fixtures/variables.json'
import EarthPage from './EarthPage'

// The map needs WebGL, which the test browser does not have. It is replaced by buttons that call the same handlers.
vi.mock('./EarthMap', () => ({
  EarthMap: ({ view, placeId, insets, onOpenCase, onSelectPlace }: { view: string; placeId: string | null; insets: { left: number }; onOpenCase: () => void; onSelectPlace: (id: string) => void }) => (
    <div data-testid="map" data-view={view} data-place={placeId ?? ''} data-left={insets.left}>
      <button type="button" onClick={onOpenCase}>pin</button>
      <button type="button" onClick={() => onSelectPlace('kyiv_no2_box')}>box kyiv</button>
      <button type="button" onClick={() => onSelectPlace('poland_krakow')}>box krakow</button>
    </div>
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

  it('opens on the Earth with no story and Investigate unavailable', () => {
    render(<EarthPage />)
    expect(screen.getByTestId('map')).toHaveAttribute('data-view', 'earth')
    expect(screen.getByTestId('investigate')).toBeDisabled()
    expect(screen.queryByTestId('cards')).not.toBeInTheDocument()
    expect(screen.queryByText(/Before the invasion/)).not.toBeInTheDocument()
  })

  it('goes Earth, Ukraine, Kyiv, Investigate: the cards open and the camera is told to make room', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByText('pin'))
    expect(screen.getByTestId('map')).toHaveAttribute('data-view', 'case')
    await user.click(screen.getByText('box kyiv'))
    expect(screen.getByTestId('map')).toHaveAttribute('data-place', 'kyiv_no2_box')

    const investigate = await screen.findByTestId('investigate')
    await vi.waitFor(() => expect(investigate).toBeEnabled())
    await user.click(investigate)

    const cards = await screen.findByTestId('cards')
    // NO₂ is the first card, tested on the full record only.
    const card = within(cards).getByTestId('card-no2_mean_molec_cm2')
    expect(await within(card).findByTestId('card-verdict')).toBeInTheDocument()
    expect(within(card).getByTestId('card-back')).toHaveTextContent('Tested on the full record')
    expect(Number(screen.getByTestId('map').getAttribute('data-left'))).toBeGreaterThan(0)

    await user.click(screen.getByTestId('investigate'))
    expect(screen.queryByTestId('cards')).not.toBeInTheDocument()
    expect(screen.getByTestId('map')).toHaveAttribute('data-left', '0')
  })

  it('adds and removes variables, four at most', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByText('pin'))
    await user.click(screen.getByText('box kyiv'))
    await vi.waitFor(() => expect(screen.getByTestId('investigate')).toBeEnabled())
    await user.click(screen.getByTestId('investigate'))
    await user.click(await screen.findByTestId('add-variable'))
    const picker = screen.getByTestId('variable-picker')
    const boxes = within(picker).getAllByRole('checkbox')
    expect(boxes.length).toBeGreaterThan(4)
    for (const box of boxes.filter((b) => !(b as HTMLInputElement).checked).slice(0, 3)) await user.click(box)
    expect(screen.getByTestId('add-variable')).toHaveTextContent('4/4')
    expect(within(picker).getAllByRole('checkbox').filter((b) => (b as HTMLInputElement).disabled).length).toBeGreaterThan(0)
  })

  it('offers comparison places beside the chosen one', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByText('pin'))
    await user.click(screen.getByText('box kyiv'))
    const krakow = await screen.findByTestId('compare-poland_krakow')
    expect(screen.queryByTestId('compare-kyiv_no2_box')).not.toBeInTheDocument()
    await user.click(krakow)
    expect(krakow).toHaveAttribute('aria-pressed', 'true')
  })

  it('expands the evidence into a wider grid with units, tested dates and a verdict per place', async () => {
    const user = userEvent.setup()
    render(<EarthPage />)
    await user.click(screen.getByText('pin'))
    await user.click(screen.getByText('box kyiv'))
    await user.click(await screen.findByTestId('compare-poland_krakow'))
    await vi.waitFor(() => expect(screen.getByTestId('investigate')).toBeEnabled())
    await user.click(screen.getByTestId('investigate'))
    const compactLeft = Number(screen.getByTestId('map').getAttribute('data-left'))

    await user.click(await screen.findByTestId('expand-evidence'))
    expect(screen.getByTestId('cards')).toHaveAttribute('data-expanded', 'true')
    expect(Number(screen.getByTestId('map').getAttribute('data-left'))).toBeGreaterThan(compactLeft)
    const card = screen.getByTestId('card-no2_mean_molec_cm2')
    expect(await within(card).findByTestId('card-meta')).toHaveTextContent(/tested/)
    const verdicts = within(card).getByTestId('card-verdicts')
    expect(verdicts).toHaveTextContent('Kyiv')
    expect(verdicts).toHaveTextContent('Kraków')

    await user.click(screen.getByTestId('expand-evidence'))
    expect(screen.getByTestId('expand-evidence')).toHaveTextContent('Expand evidence')
    expect(Number(screen.getByTestId('map').getAttribute('data-left'))).toBe(compactLeft)
  })
})
