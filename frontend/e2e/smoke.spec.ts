import { expect, test, type Page } from '@playwright/test'

// Basemap tiles come from a third party; keep the suite hermetic.
test.beforeEach(async ({ page }) => {
  await page.route(/basemaps\.cartocdn\.com/, (route) => route.fulfill({ status: 204 }))
})

async function open(page: Page) {
  await page.goto('/')
  await expect(page.getByTestId('seasonal-pct')).toBeVisible()
}

/** Fetch the real study payload, let a test edit it, and serve the edited copy. */
async function serveModifiedStudy(page: Page, edit: (body: any) => void) {
  await page.route('**/api/air/kyiv', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    edit(body)
    await route.fulfill({ response, json: body })
  })
}

test('connects to the real backend and shows the primary headline (≈ −28%)', async ({ page }) => {
  const studyResponse = page.waitForResponse((r) => r.url().endsWith('/api/air/kyiv') && r.ok())
  await open(page)
  const body = await (await studyResponse).json()
  const pct: number = body.result.comparisons.primary_2015_2019_valid_day.pct_change
  expect(pct).toBeCloseTo(-28, 0)
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Was NO₂ different above Kyiv in 2022?')
  await expect(page.getByTestId('study-map')).toBeVisible()
  await expect(page.getByText('© OpenStreetMap contributors')).toBeVisible().catch(async () => {
    await expect(page.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap')
  })
  await expect(page.getByText(/not a pollution heatmap/i)).toBeVisible()
})

test('switching baseline changes the headline (≈ −20%) and the chart, keeping warnings visible', async ({ page }) => {
  await open(page)
  await page.getByRole('radio', { name: /2019–2021/ }).check({ force: true })
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−20.3%')
  await expect(page.getByRole('heading', { name: /2022 against 2019–2021/ })).toBeVisible()
  await expect(page.getByTestId('coverage-2022-04')).toContainText('8 of 30 days')
  await expect(page.getByText('Before/after significance not assessed', { exact: false })).toBeVisible()
  await expect(page.getByText('Causal attribution to the war: not_established')).toBeVisible()
  await page.getByRole('radio', { name: /2015–2019/ }).check({ force: true })
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
})

test('April inspector shows 8 of 30 days and does not change the headline', async ({ page }) => {
  await open(page)
  await page.getByTestId('month-4').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('inspector-title')).toHaveText('April 2022')
  await expect(page.getByTestId('inspector-days')).toContainText('8 of 30 days')
  await expect(page.getByTestId('inspector-low-coverage')).toBeVisible()
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
})

test('missing measurements stay missing: labelled, never zero, line not bridged', async ({ page }) => {
  await serveModifiedStudy(page, (body) => {
    const may = body.result.matched_months.find((m: any) => m.calendar_month === 5)
    may.target_2022.mean_molec_cm2 = null
    may.target_2022.valid_days = 0
    may.target_2022.coverage_fraction = 0
  })
  await open(page)
  await page.getByTestId('month-5').click()
  await expect(page.getByTestId('inspector-2022')).toContainText('No valid measurement')
  await expect(page.getByTestId('inspector-2022')).not.toContainText(/^\s*0/)
  // Before/after significance is a different absence: "not assessed", not "no measurement".
  await page.getByRole('button', { name: /Statistical status/ }).click()
  await expect(page.getByTestId('stat-before-after')).toContainText('Not assessed')
  // Three plotted 2022 points on each side of the gap, none for May.
  await page.getByRole('button', { name: 'Chart' }).click()
  const circles = page.getByTestId('comparison-chart').locator('circle[r="6"]')
  await expect(circles).toHaveCount(5)
})

test('request failure shows a clear error and retry recovers', async ({ page }) => {
  let failures = 0
  await page.route('**/api/cases', async (route) => {
    if (failures++ < 1) return route.abort('connectionrefused')
    return route.continue()
  })
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('could not be reached')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
})

test('a backend error body is shown to the reader', async ({ page }) => {
  await page.route('**/api/air/kyiv', (route) =>
    route.fulfill({ status: 503, json: { error: { code: 'result_unavailable', message: 'Air results are not loaded.', details: null } } }),
  )
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Air results are not loaded.')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

test('supplementary figures: only returned charts, graceful when none or when an image fails', async ({ page }) => {
  await open(page)
  await expect(page.getByTestId('figures').getByRole('listitem')).toHaveCount(3)

  const empty = await page.context().newPage()
  await empty.route(/basemaps\.cartocdn\.com/, (route) => route.fulfill({ status: 204 }))
  await serveModifiedStudy(empty, (body) => { body.charts = [] })
  await empty.goto('/')
  await expect(empty.getByTestId('figures-empty')).toBeVisible()

  const broken = await page.context().newPage()
  await broken.route(/basemaps\.cartocdn\.com/, (route) => route.fulfill({ status: 204 }))
  await broken.route('**/api/air/kyiv/charts/matched_months', (route) => route.fulfill({ status: 404, json: { error: { code: 'chart_unavailable', message: 'gone' } } }))
  await broken.goto('/')
  await broken.getByTestId('figures').scrollIntoViewIfNeeded()
  await expect(broken.getByTestId('figure-matched_months')).toContainText('The preview did not load')
  await expect(broken.getByTestId('figure-monthly_timeline').locator('img')).toBeVisible()
})

test('desktop: map and summary sit side by side, nothing overflows', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  const summary = await page.getByTestId('seasonal-summary').boundingBox()
  const map = await page.getByTestId('study-map').boundingBox()
  expect(map!.x).toBeGreaterThan(summary!.x + summary!.width - 4)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})

test('mobile: layout stacks, month buttons are touch-sized, nothing overflows', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)
  const summary = await page.getByTestId('seasonal-summary').boundingBox()
  const map = await page.getByTestId('study-map').boundingBox()
  expect(map!.y).toBeGreaterThan(summary!.y + summary!.height - 4)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  const box = await page.getByTestId('month-4').boundingBox()
  expect(box!.height).toBeGreaterThanOrEqual(44)
  await page.getByTestId('month-4').tap().catch(() => page.getByTestId('month-4').click())
  await expect(page.getByTestId('inspector-days')).toContainText('8 of 30 days')
})
