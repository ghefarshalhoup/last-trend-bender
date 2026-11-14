import { expect, test, type Page } from '@playwright/test'

// Illustrated-atlas preview against the REAL FastAPI backend (see playwright.config.ts).
const SHOTS = '../docs/screenshots/atlas-poc'

async function openAir(page: Page) {
  await page.goto('/#/atlas')
  await expect(page.getByTestId('atlas-base')).toBeVisible()
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('kyiv-polygon')).toBeVisible()
}
async function openScroll(page: Page) {
  await page.getByTestId('evidence-scroll').click()
  await expect(page.getByTestId('evidence-widget')).toBeVisible()
}

/** Where things are on screen, as fractions of the atlas frame. */
async function geometry(page: Page) {
  return page.evaluate(() => {
    const rect = (id: string) => document.querySelector(`[data-testid="${id}"]`)!.getBoundingClientRect()
    const frame = rect('atlas-frame')
    const box = rect('kyiv-polygon')
    const label = rect('kyiv-label')
    const city = document.querySelector('[data-testid="city-Kyiv"]') as SVGGElement
    // where the shared projection says Kyiv is, converted from atlas units to screen pixels
    const expectedX = frame.left + (Number(city.dataset.x) / 1600) * frame.width
    const expectedY = frame.top + (Number(city.dataset.y) / 1000) * frame.height
    return {
      frameWidth: frame.width,
      frameRatio: frame.width / frame.height,
      offsetX: box.left + box.width / 2 - expectedX,
      offsetY: box.top + box.height / 2 - expectedY,
      boxWidthFraction: box.width / frame.width,
      boxCentreX: (box.left + box.width / 2 - frame.left) / frame.width,
      boxCentreY: (box.top + box.height / 2 - frame.top) / frame.height,
      labelCornerX: (label.right - frame.left) / frame.width,
      labelCornerY: (label.bottom - frame.top) / frame.height,
    }
  })
}

test('neutral atlas: fixed illustrated map, no tiles, no layer', async ({ page }) => {
  const tiles: string[] = []
  page.on('request', (r) => { if (/tile|arcgisonline/.test(r.url())) tiles.push(r.url()) })
  await page.goto('/#/atlas')
  await expect(page.getByTestId('ukraine-outline')).toBeVisible()
  await expect(page.getByTestId('kyiv-polygon')).toHaveCount(0)
  await expect(page.getByTestId('layer-controls')).toHaveCount(0)
  await expect(page.locator('.leaflet-container')).toHaveCount(0)
  expect(tiles).toHaveLength(0)
  await page.screenshot({ path: `${SHOTS}/1-neutral-desktop.png` })
})

test('Air: season, April and baseline update map, evidence and guide together', async ({ page }) => {
  await openAir(page)
  await expect(page.getByTestId('kyiv-value')).toContainText('−28.0% vs 2015–2019')
  await page.screenshot({ path: `${SHOTS}/2-air-season-desktop.png` })

  await page.getByTestId('period-4').click()
  await expect(page.getByTestId('kyiv-value')).toContainText('−37.0% vs 2015–2019')
  await expect(page.getByTestId('kyiv-label')).toContainText('8/30 days')
  await expect(page.getByTestId('kyiv-label-warning')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/3-air-april-desktop.png` })
  await openScroll(page)
  await expect(page.getByTestId('evidence-low-coverage')).toContainText('8 of 30 days')
  await expect(page.getByTestId('guide-bubble')).toContainText('only 8 of 30 days')
  // the open scroll must not hide the Kyiv box at this size
  const box = (await page.getByTestId('kyiv-polygon').boundingBox())!
  const scroll = (await page.getByTestId('evidence-widget').boundingBox())!
  expect(box.x + box.width).toBeLessThan(scroll.x)
  await page.screenshot({ path: `${SHOTS}/4-air-april-scroll-open-desktop.png` })
  await page.getByTestId('scroll-tab-legend').click()
  await expect(page.getByTestId('air-key')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/5-air-april-legend-desktop.png` })
  await page.getByTestId('scroll-tab-evidence').click()

  await page.getByTestId('comparison-sensitivity_2019_2021_valid_day').click()
  await expect(page.getByTestId('kyiv-value')).toContainText('−33.2% vs 2019–2021')
  await expect(page.getByTestId('evidence-value')).toContainText('−33.2%')

  await page.getByTestId('clear-element').click()
  await expect(page.getByTestId('kyiv-polygon')).toHaveCount(0)
  await expect(page.getByTestId('evidence-widget')).toHaveCount(0)
})

test('the map does not move when Air is selected or a month changes', async ({ page }) => {
  await page.goto('/#/atlas')
  const outline = () => page.getByTestId('ukraine-outline').boundingBox()
  await expect(page.getByTestId('ukraine-outline')).toBeVisible()
  const viewBox = () => page.locator('[data-testid="atlas-frame"] svg').getAttribute('viewBox')
  const before = await viewBox()
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('kyiv-polygon')).toBeVisible()
  const withAir = await outline()
  const polygon = await page.getByTestId('kyiv-polygon').getAttribute('d')
  await page.getByTestId('period-6').click()
  await openScroll(page)
  expect(await viewBox()).toBe(before)
  expect(await outline()).toEqual(withAir)
  expect(await page.getByTestId('kyiv-polygon').getAttribute('d')).toBe(polygon)
})

test('artwork, polygon and label stay aligned when the screen resizes', async ({ page }) => {
  await openAir(page)
  await page.getByTestId('period-4').click()
  const sizes = [[1440, 900], [1100, 800], [820, 1100], [390, 844]] as const
  const seen: Awaited<ReturnType<typeof geometry>>[] = []
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height })
    await expect(page.getByTestId('kyiv-polygon')).toBeVisible()
    const g = await geometry(page)
    seen.push(g)
    expect(g.frameRatio).toBeCloseTo(1.6, 2)
    // the polygon's centre is where the projection puts Kyiv, to within one pixel
    expect(Math.abs(g.offsetX)).toBeLessThan(1)
    expect(Math.abs(g.offsetY)).toBeLessThan(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)
  }
  const first = seen[0]!
  for (const g of seen) {
    expect(g.boxCentreX).toBeCloseTo(first.boxCentreX, 2)
    expect(g.boxCentreY).toBeCloseTo(first.boxCentreY, 2)
    expect(g.boxWidthFraction).toBeCloseTo(first.boxWidthFraction, 2)
    // the HTML label's anchor corner follows the same frame fractions
    expect(g.labelCornerX).toBeCloseTo(first.labelCornerX, 2)
    expect(g.labelCornerY).toBeCloseTo(first.labelCornerY, 2)
  }
  await page.screenshot({ path: `${SHOTS}/7-air-april-mobile.png` })
  await page.setViewportSize({ width: 1100, height: 800 })
  await page.screenshot({ path: `${SHOTS}/6-air-april-1100.png` })
})

test('the study area can be selected from the keyboard', async ({ page }) => {
  await openAir(page)
  await page.getByTestId('kyiv-label').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('kyiv-label')).toHaveAttribute('aria-pressed', 'true')
  await openScroll(page)
  await expect(page.getByTestId('evidence-area')).toBeVisible()
  await expect(page.getByTestId('guide-bubble')).toContainText('whole Kyiv study area')
})

test('the scroll follows the element and opens over a map that does not move', async ({ page }) => {
  await page.goto('/#/atlas')
  await expect(page.getByTestId('element-status')).toHaveText('No element selected')
  await expect(page.getByTestId('evidence-scroll')).toHaveAttribute('data-element', 'none')
  const outline = await page.getByTestId('ukraine-outline').boundingBox()
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('evidence-scroll')).toHaveAttribute('data-element', 'air')
  await expect(page.getByTestId('element-status')).toContainText('Air selected')
  await page.getByTestId('evidence-scroll').click()
  await expect(page.getByTestId('evidence-widget')).toBeVisible()
  expect(await page.getByTestId('ukraine-outline').boundingBox()).toEqual(outline)
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('evidence-widget')).toHaveCount(0)
  await expect(page.getByTestId('evidence-scroll')).toBeFocused()
})

test('the tile-map explorer is still the default screen', async ({ page }) => {
  await page.route(/tile\.openstreetmap\.org|arcgisonline\.com/, (route) => route.fulfill({ status: 204 }))
  await page.goto('/')
  await expect(page.getByTestId('ukraine-map')).toBeVisible()
  await expect(page.getByTestId('atlas-page')).toHaveCount(0)
})
