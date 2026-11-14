import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { casesFixture, clone, studyFixture } from '../../test/fixtures'
import { AirPage } from './AirPage'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('AirPage loading, failure and retry', () => {
  const fetchMock = vi.fn()
  beforeEach(() => vi.stubGlobal('fetch', fetchMock))
  afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals() })

  it('loads from /api/cases then the endpoint the catalog names', async () => {
    fetchMock.mockImplementation(async (url: string) => (url.endsWith('/api/cases') ? json(casesFixture) : json(studyFixture)))
    render(<AirPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByTestId('seasonal-pct')).toHaveTextContent('−28.0%')
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(['/api/cases', '/api/air/kyiv'])
  })

  it('shows an error with the backend message and recovers on retry', async () => {
    const user = userEvent.setup()
    fetchMock.mockResolvedValueOnce(
      json({ error: { code: 'result_unavailable', message: 'Air results are not loaded.', details: null } }, 503),
    )
    fetchMock.mockImplementation(async (url: string) => (url.endsWith('/api/cases') ? json(casesFixture) : json(studyFixture)))
    render(<AirPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Air results are not loaded.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByTestId('seasonal-pct')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reports a network failure', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    render(<AirPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be reached/)
  })

  it('reports contract drift instead of crashing', async () => {
    const broken = clone(studyFixture) as unknown as Record<string, unknown>
    delete broken.result
    fetchMock.mockImplementation(async (url: string) => (url.endsWith('/api/cases') ? json(casesFixture) : json(broken)))
    render(<AirPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/malformed at "result"/)
  })

  it('explains when the catalog says air is not ready', async () => {
    const cases = clone(casesFixture)
    cases.cases[0]!.elements[0]!.status = 'unavailable'
    cases.cases[0]!.elements[0]!.reason = 'data_not_ready'
    fetchMock.mockResolvedValue(json(cases))
    render(<AirPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/not ready yet/)
  })
})
