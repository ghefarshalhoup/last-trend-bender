import { expect, test, type Page } from '@playwright/test'

/** Tile requests are recorded (so we can check what the map framed) and answered empty to stay hermetic. */
const tiles: string[] = []
test.beforeEach(async ({ page }) => {
  tiles.length = 0
  await page.route(/basemaps\.cartocdn\.com/, (route) => {
    tiles.push(route.request().url())
    return route.fulfill({ status: 204 })
  })
})

async function open(page: Page) {
  await page.goto('/')
  await expect(page.getByTestId('ukraine-map')).toBeVisible()
}
async function selectAirAndExplore(page: Page) {
  await page.getByTestId('element-air').click()
  await page.getByTestId('explore-kyiv').click()
  await expect(page.getByTestId('study-panel')).toBeVisible()
}
async function serveModifiedStudy(page: Page, edit: (body: any) => void) {
  await page.route('**/api/air/kyiv', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    edit(body)
    await route.fulfill({ response, json: body })
  })
}
const kyivLabel = (page: Page) => page.locator('.leaflet-tooltip', { hasText: 'Kyiv · NO₂ study' })
const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)

// Slippy-map tile → lon/lat of its north-west corner.
function tileBounds(urls: string[]) {
  const zs = urls.map((u) => u.match(/\/(\d+)\/(\d+)\/(\d+)(?:@2x)?\.png/)!.slice(1).map(Number) as [number, number, number])
  const lon = (x: number, z: number) => (x / 2 ** z) * 360 - 180
  const lat = (y: number, z: number) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / 2 ** z))) * 180) / Math.PI
  return {
    west: Math.min(...zs.map(([z, x]) => lon(x, z))),
    east: Math.max(...zs.map(([z, x]) => lon(x + 1, z))),
    north: Math.max(...zs.map(([z, , y]) => lat(y, z))),
    south: Math.min(...zs.map(([z, , y]) => lat(y + 1, z))),
  }
}

test('neutral opening: Ukraine (with Crimea) framed, four elements, no scientific content, study not requested', async ({ page }) => {
  const requests: string[] = []
  page.on('request', (r) => r.url().includes('/api/') && requests.push(new URL(r.url()).pathname))
  await open(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Environmental Fingerprints of War')
  await expect(page.getByTestId('choose-prompt')).toHaveText('Choose an element to explore')
  await expect(page.getByTestId('element-air')).toHaveAttribute('aria-disabled', 'false')
  for (const id of ['fire', 'land', 'water']) await expect(page.getByTestId(`element-${id}`)).toContainText('Coming later')
  await expect(page.getByTestId('element-land')).toContainText('Earth')
  await expect(page.getByTestId('guide-bubble')).toBeVisible()
  await expect(page.getByTestId('reset-ukraine')).toBeVisible()
  await expect(page.getByTestId('study-panel')).toHaveCount(0)
  await expect(kyivLabel(page)).toHaveCount(0)
  await expect(page.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap')
  expect(requests).toContain('/api/cases')
  expect(requests).not.toContain('/api/air/kyiv') // the study is requested only when Air is selected

  // The framing really covers the country: Crimea's south, Ukraine's west and east.
  await expect.poll(() => tiles.length).toBeGreaterThan(0)
  const b = tileBounds(tiles)
  expect(b.south).toBeLessThanOrEqual(44.4)
  expect(b.north).toBeGreaterThanOrEqual(52.3)
  expect(b.west).toBeLessThanOrEqual(22.2)
  expect(b.east).toBeGreaterThanOrEqual(40.2)
})

test('selecting Air reveals Kyiv from the backend and keeps the Ukraine view until Kyiv is chosen', async ({ page }) => {
  await open(page)
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'true')
  await expect(kyivLabel(page)).toBeVisible()
  await expect(page.getByTestId('explore-kyiv')).toBeVisible()
  await expect(page.getByTestId('study-panel')).toHaveCount(0)
  // The boundary polygon comes from the API payload and is drawn on the map.
  await expect(page.locator('.leaflet-overlay-pane path')).toHaveCount(1)
  const box = await page.locator('.leaflet-overlay-pane path').boundingBox()
  expect(box!.width).toBeLessThan(80) // small at country scale: the marker and label make it discoverable
})

test('Explore Kyiv focuses the study area and opens the panel with the real ≈ −28% headline', async ({ page }) => {
  await open(page)
  const before = await page.locator('.leaflet-overlay-pane path').count()
  const studyResponse = page.waitForResponse((r) => r.url().endsWith('/api/air/kyiv') && r.ok())
  await page.getByTestId('element-air').click()
  const body = await (await studyResponse).json()
  expect(body.result.comparisons.primary_2015_2019_valid_day.pct_change).toBeCloseTo(-28, 0)
  await page.getByTestId('explore-kyiv').click()
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
  await expect(page.getByTestId('seasonal-summary')).toContainText('March–August 2022')
  await expect(page.getByTestId('study-panel').getByText(/not a pollution heatmap/i)).toBeVisible()
  await expect.poll(async () => (await page.locator('.leaflet-overlay-pane path').boundingBox())!.width).toBeGreaterThan(150)
  expect(before).toBe(0)
})

test('keyboard equivalent: Tab to the Kyiv marker and press Enter', async ({ page }) => {
  await open(page)
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('explore-kyiv')).toBeVisible()
  await page.getByTitle('Explore Kyiv NO₂ study').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('study-panel')).toBeVisible()
})

test('clicking the Kyiv marker opens the panel; Explore Kyiv button is hidden while it is open', async ({ page }) => {
  await open(page)
  await page.getByTestId('element-air').click()
  await page.getByTitle('Explore Kyiv NO₂ study').click()
  await expect(page.getByTestId('study-panel')).toBeVisible()
  await expect(page.getByTestId('explore-kyiv')).toHaveCount(0)
})

test('baselines update headline, chart and monthly comparison together; warnings stay visible', async ({ page }) => {
  await open(page)
  await selectAirAndExplore(page)
  await page.getByTestId('month-4').click()
  await expect(page.getByTestId('inspector-change')).toContainText('−37.0%')
  await page.getByRole('radio', { name: /2019–2021/ }).check({ force: true })
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−20.3%')
  await expect(page.getByRole('heading', { name: /2022 against 2019–2021/ })).toBeVisible()
  await expect(page.getByTestId('inspector-change')).not.toContainText('−37.0%')
  await expect(page.getByTestId('coverage-2022-04')).toContainText('8 of 30 days')
  await expect(page.getByText('Before/after significance not assessed', { exact: false })).toBeVisible()
  await expect(page.getByText('Causal attribution to the war: not_established')).toBeVisible()
  await page.getByRole('radio', { name: /2015–2019/ }).check({ force: true })
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
})

test('April inspector: 8 of 30 days, label on the Kyiv box follows the month, seasonal headline unchanged', async ({ page }) => {
  await open(page)
  await selectAirAndExplore(page)
  await expect(page.locator('.leaflet-tooltip')).toContainText('March–August 2022: −28.0%')
  const pathBefore = await page.locator('.leaflet-overlay-pane path').boundingBox()
  await page.getByTestId('month-4').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('inspector-title')).toHaveText('April 2022')
  await expect(page.getByTestId('inspector-days')).toContainText('8 of 30 days')
  await expect(page.getByTestId('inspector-low-coverage')).toBeVisible()
  await expect(page.locator('.leaflet-tooltip')).toContainText('April 2022: −37.0% · 8/30 days')
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−28.0%')
  // Time does not move the boundary.
  const pathAfter = await page.locator('.leaflet-overlay-pane path').boundingBox()
  expect(Math.round(pathAfter!.x)).toBe(Math.round(pathBefore!.x))
  expect(Math.round(pathAfter!.y)).toBe(Math.round(pathBefore!.y))
})

test('close panel keeps Air, month and baseline; clear returns to neutral; reset view keeps data', async ({ page }) => {
  await open(page)
  await selectAirAndExplore(page)
  await page.getByRole('radio', { name: /2019–2021/ }).check({ force: true })
  await page.getByTestId('month-4').click()

  await page.getByTestId('close-panel').click()
  await expect(page.getByTestId('study-panel')).toHaveCount(0)
  await expect(page.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'true')
  await expect(kyivLabel(page)).toBeVisible()

  await page.getByTestId('explore-kyiv').click()
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−20.3%')
  await expect(page.getByTestId('inspector-title')).toHaveText('April 2022')

  await page.getByTestId('reset-ukraine').click()
  await expect(page.getByTestId('study-panel')).toBeVisible()
  await expect(page.getByTestId('seasonal-pct')).toHaveText('−20.3%')

  await page.getByTestId('clear-element').click()
  await expect(page.getByTestId('study-panel')).toHaveCount(0)
  await expect(kyivLabel(page)).toHaveCount(0)
  await expect(page.getByTestId('choose-prompt')).toBeVisible()
  await expect(page.getByTestId('element-air')).toHaveAttribute('aria-pressed', 'false')
})

test('missing values stay missing: labelled, never zero, line not bridged', async ({ page }) => {
  await serveModifiedStudy(page, (body) => {
    const may = body.result.matched_months.find((m: any) => m.calendar_month === 5)
    may.target_2022.mean_molec_cm2 = null
    may.target_2022.valid_days = 0
    may.target_2022.coverage_fraction = 0
  })
  await open(page)
  await selectAirAndExplore(page)
  await page.getByTestId('month-5').click()
  await expect(page.getByTestId('inspector-2022')).toContainText('No valid measurement')
  await expect(page.getByTestId('inspector-2022')).not.toContainText(/^\s*0/)
  await page.getByRole('button', { name: /Statistical status/ }).click()
  await expect(page.getByTestId('stat-before-after')).toContainText('Not assessed')
  await expect(page.getByTestId('comparison-chart').locator('circle[r="6"]')).toHaveCount(5)
})

test('study request failure: error and retry, never invented results; catalog failure too', async ({ page }) => {
  let failures = 0
  await page.route('**/api/air/kyiv', (route) =>
    failures++ < 1
      ? route.fulfill({ status: 503, json: { error: { code: 'result_unavailable', message: 'Air results are not loaded.', details: null } } })
      : route.continue(),
  )
  await open(page)
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('study-error')).toContainText('Air results are not loaded.')
  await expect(kyivLabel(page)).toHaveCount(0)
  await expect(page.getByTestId('seasonal-pct')).toHaveCount(0)
  await page.getByTestId('study-error').getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByTestId('explore-kyiv')).toBeVisible()
})

test('catalog failure shows a retryable error', async ({ page }) => {
  let failures = 0
  await page.route('**/api/cases', (route) => (failures++ < 1 ? route.abort('connectionrefused') : route.continue()))
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('could not be reached')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByTestId('ukraine-map')).toBeVisible()
})

test('supplementary figures: only returned charts; graceful when none or when an image fails', async ({ page, context }) => {
  await open(page)
  await selectAirAndExplore(page)
  await page.getByRole('button', { name: /^Supplementary figures/ }).click()
  await expect(page.getByTestId('figures').getByRole('listitem')).toHaveCount(3)

  const empty = await context.newPage()
  await empty.route(/basemaps\.cartocdn\.com/, (r) => r.fulfill({ status: 204 }))
  await serveModifiedStudy(empty, (body) => { body.charts = [] })
  await empty.goto('/')
  await selectAirAndExplore(empty)
  await empty.getByRole('button', { name: /^Supplementary figures/ }).click()
  await expect(empty.getByTestId('figures-empty')).toBeVisible()

  const broken = await context.newPage()
  await broken.route(/basemaps\.cartocdn\.com/, (r) => r.fulfill({ status: 204 }))
  await broken.route('**/api/air/kyiv/charts/matched_months', (r) => r.fulfill({ status: 404, json: { error: { code: 'chart_unavailable', message: 'gone' } } }))
  await broken.goto('/')
  await selectAirAndExplore(broken)
  await broken.getByRole('button', { name: /^Supplementary figures/ }).click()
  await broken.getByTestId('figures').scrollIntoViewIfNeeded()
  await expect(broken.getByTestId('figure-matched_months')).toContainText('The preview did not load')
})

test('desktop: map stays visible beside the panel; nothing overflows', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  expect(await noHorizontalOverflow(page)).toBeLessThanOrEqual(0)
  await selectAirAndExplore(page)
  const map = await page.getByTestId('ukraine-map').boundingBox()
  const panel = await page.getByTestId('study-panel').boundingBox()
  expect(panel!.x).toBeGreaterThanOrEqual(map!.x + map!.width - 4)
  expect(map!.width).toBeGreaterThan(600)
  expect(await noHorizontalOverflow(page)).toBeLessThanOrEqual(0)
  await expect(page.locator('.leaflet-control-attribution')).toBeVisible()
})

test('mobile: stacked layout, touch-sized controls, panel readable, no sideways scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)
  expect(await noHorizontalOverflow(page)).toBeLessThanOrEqual(0)
  const airBox = await page.getByTestId('element-air').boundingBox()
  expect(airBox!.height).toBeGreaterThanOrEqual(44)
  await selectAirAndExplore(page)
  const map = await page.getByTestId('ukraine-map').boundingBox()
  const panel = await page.getByTestId('study-panel').boundingBox()
  expect(panel!.y).toBeGreaterThan(map!.y + map!.height - 4)
  expect(await noHorizontalOverflow(page)).toBeLessThanOrEqual(0)
  const april = page.getByTestId('month-4')
  expect((await april.boundingBox())!.height).toBeGreaterThanOrEqual(44)
  await april.click()
  await expect(page.getByTestId('inspector-days')).toContainText('8 of 30 days')
  await expect(page.locator('.leaflet-control-attribution')).toBeAttached()
  await page.getByTestId('close-panel').click()
  await expect(page.getByTestId('study-panel')).toHaveCount(0)
})
