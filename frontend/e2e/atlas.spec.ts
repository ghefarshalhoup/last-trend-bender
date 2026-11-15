import { expect, test, type Page } from '@playwright/test'

// Illustrated atlas against the REAL FastAPI backend (see playwright.config.ts).
const SHOTS = '../docs/screenshots/atlas-poc'

async function open(page: Page) {
  await page.goto('/#/atlas')
  await expect(page.getByTestId('place-kyiv_no2_box')).toBeVisible()
}

/** Kyiv city, full record, Air: NO₂ beside wind and cloud. */
async function openKyivAir(page: Page) {
  await page.getByTestId('place-kyiv_no2_box').click()
  await page.getByTestId('investigate').click()
  await page.getByTestId('element-air').click()
  for (const id of ['no2_mean_molec_cm2', 'ws10m', 'cloud_amt']) await page.getByTestId(`variable-${id}`).click()
}

test('phase 1: fixed illustrated map with place pins, no tiles, no cards', async ({ page }) => {
  const tiles: string[] = []
  page.on('request', (r) => { if (/tile|arcgisonline/.test(r.url())) tiles.push(r.url()) })
  await open(page)
  await expect(page.getByTestId('ukraine-outline')).toBeVisible()
  for (const id of ['kyiv_no2_box', 'kyiv_north_belt', 'donbas_kharkiv_east', 'south_steppe_belt', 'central_interior_cand', 'west_ukraine_cand']) {
    await expect(page.getByTestId(`place-${id}`)).toBeVisible()
  }
  await expect(page.getByTestId('card-area')).toHaveCount(0)
  expect(tiles).toHaveLength(0)
  await page.getByTestId('place-donbas_kharkiv_east').hover()
  await expect(page.getByTestId('place-box-hover')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/1-choose-place-desktop.png` })
})

test('pins sit where the projection puts each box centre, at every screen size', async ({ page }) => {
  await open(page)
  for (const [width, height] of [[1440, 900], [1100, 800], [390, 844]] as const) {
    await page.setViewportSize({ width, height })
    await expect(page.getByTestId('place-kyiv_no2_box')).toBeVisible()
    const off = await page.evaluate(() => {
      const frame = document.querySelector('[data-testid="atlas-frame"]')!.getBoundingClientRect()
      const city = document.querySelector('[data-testid="city-Kyiv"]') as SVGGElement
      const dot = document.querySelector('[data-testid="place-kyiv_no2_box"] span')!.getBoundingClientRect()
      const [vx, vy, vw, vh] = document.querySelector('[data-testid="atlas-frame"] svg')!.getAttribute('viewBox')!.split(' ').map(Number)
      const x = frame.left + ((Number(city.dataset.x) - vx!) / vw!) * frame.width
      const y = frame.top + ((Number(city.dataset.y) - vy!) / vh!) * frame.height
      return { dx: dot.left + dot.width / 2 - x, dy: dot.top + dot.height / 2 - y }
    })
    // Kyiv city label in the base map and the Kyiv box centre are both 50.45N, 30.5E
    expect(Math.abs(off.dx)).toBeLessThan(4)
    expect(Math.abs(off.dy)).toBeLessThan(4)
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)
  }
})

test('phase 2: place → investigate → element → variable card with an honest verdict', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  const viewBox = await page.locator('[data-testid="atlas-frame"] svg').getAttribute('viewBox')
  const outline = await page.getByTestId('ukraine-outline').boundingBox()
  await page.getByTestId('place-donbas_kharkiv_east').click()
  await expect(page.getByTestId('place-box')).toBeVisible()
  await page.getByTestId('window-pre_invasion').click()
  await page.getByTestId('investigate').click()
  await expect(page.getByTestId('chosen-place')).toHaveText('East front (Donbas–Kharkiv)')
  // the map is the background now: same frame, same geography
  expect(await page.locator('[data-testid="atlas-frame"] svg').getAttribute('viewBox')).toBe(viewBox)
  expect(await page.getByTestId('ukraine-outline').boundingBox()).toEqual(outline)

  await page.getByTestId('element-water').click()
  await page.getByTestId('variable-prectotcorr').click()
  const card = page.getByTestId('card-prectotcorr')
  await expect(card.getByTestId('card-verdict')).toBeVisible()
  await expect(card.getByTestId('trend-chart')).toBeVisible()
  await expect(card.getByTestId('card-seasonal')).toContainText('vs 2015–2019')
  await page.getByTestId('element-fire').click()
  await page.getByTestId('variable-fire_type0_per_1k_km2_day').click()
  const fire = page.getByTestId('card-fire_type0_per_1k_km2_day')
  await expect(fire.getByTestId('card-verdict')).toContainText('Too little data')
  await expect(fire).toContainText('Only four fire seasons')
  await expect(fire.getByTestId('card-rate')).toHaveCount(0)
  await page.getByTestId('card-flip-prectotcorr').click()
  await expect(card.getByTestId('card-back')).toContainText('NASA POWER')
  await page.screenshot({ path: `${SHOTS}/3-cards-donbas-desktop.png` })
})

test('NO₂ beyond Kyiv: Kharkiv city, a large box, and the confirmed decline in Prague', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await page.getByTestId('place-kharkiv_city').click()
  await page.getByTestId('investigate').click()
  await expect(page.getByTestId('chosen-place')).toHaveText('Kharkiv city')
  await page.getByTestId('element-air').click()
  await page.getByTestId('variable-no2_mean_molec_cm2').click()
  const no2 = page.getByTestId('card-no2_mean_molec_cm2').first()
  await expect(no2.getByTestId('card-verdict')).toHaveText('○ No significant trend')
  await expect(no2.getByTestId('trend-chart')).toBeVisible()
  await expect(no2.getByTestId('card-seasonal')).toContainText('−29.4% vs 2015–2019')
  await page.screenshot({ path: `${SHOTS}/5-no2-kharkiv-desktop.png` })

  await page.getByTestId('change-place').click()
  await page.getByTestId('place-south_steppe_belt').click()
  await page.getByTestId('investigate').click()
  await expect(no2.getByTestId('card-verdict')).toHaveText('○ No significant trend')
  await expect(no2.getByTestId('card-rate')).toContainText('−0.0233 ×10¹⁵ molecules/cm² per year')

  // compare the South with Prague: the one significant trend is in the comparison city
  await page.getByTestId('compare-czechia_prague').click()
  const prague = page.getByTestId('half-compare').getByTestId('card-no2_mean_molec_cm2')
  await expect(page.getByTestId('half-main')).toContainText('South (Kherson–Crimea edge)')
  await expect(page.getByTestId('half-compare')).toContainText('Prague, Czechia')
  await expect(prague.getByTestId('card-verdict')).toContainText('Significant fall')
  await expect(prague.getByTestId('card-rate')).toContainText('−0.147 ×10¹⁵ molecules/cm² per year')
  await page.getByTestId('window-pre_invasion').click()
  await expect(prague.getByTestId('card-verdict')).toContainText('Significant fall')
  await page.getByTestId('window-full_record').click()
  await page.getByTestId('card-flip-no2_mean_molec_cm2').last().click()
  await expect(prague.getByTestId('card-back')).toContainText('April–September')
  await page.getByTestId('card-flip-no2_mean_molec_cm2').last().click()
  await page.screenshot({ path: `${SHOTS}/6-no2-prague-desktop.png` })
})

test('dated periods and the Kraków comparison: temperature data, fire not collected, marker', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await expect(page.getByTestId('window-full_record')).toContainText('2015 – 2022')
  await expect(page.getByTestId('window-pre_invasion')).toContainText('2015 – Feb 2022')

  await page.getByTestId('place-donbas_kharkiv_east').click()
  await page.getByTestId('compare-poland_krakow').click()
  await expect(page.getByTestId('outside-marker')).toContainText('Kraków, Poland')
  await page.getByTestId('investigate').click()
  await page.getByTestId('element-fire').click()
  await page.getByTestId('variable-t2m').click()
  await page.getByTestId('variable-fire_type0_per_1k_km2_day').click()
  const main = page.getByTestId('half-main')
  const other = page.getByTestId('half-compare')
  await expect(main.getByTestId('card-t2m').getByTestId('card-verdict')).toBeVisible()
  const krakowTemp = other.getByTestId('card-t2m')
  await expect(krakowTemp.getByTestId('card-verdict')).toHaveText('○ No significant trend')
  await expect(krakowTemp.getByTestId('card-span')).toContainText('Jan 2015 – Dec 2022')
  await page.getByTestId('window-pre_invasion').click()
  await expect(krakowTemp.getByTestId('card-span')).toContainText('Jan 2015 – Feb 2022')
  // fire was never collected outside Ukraine: the Kraków card says so and how to get it
  await expect(other.getByTestId('card-fire_type0_per_1k_km2_day').getByTestId('card-no-data')).toContainText('Not collected')
  await expect(main.getByTestId('card-fire_type0_per_1k_km2_day').getByTestId('card-verdict')).toContainText('Too little data')
  await page.screenshot({ path: `${SHOTS}/7-compare-krakow-desktop.png` })

  await page.getByTestId('compare-czechia_prague').click()
  await expect(other).toContainText('Prague, Czechia')
  await expect(page.getByTestId('outside-marker')).toContainText('beyond this map')
  await expect(other.getByTestId('card-t2m').getByTestId('trend-chart')).toBeVisible()
})

test('Kyiv NO₂ with wind and cloud: numbers from the API, insights from the portrait', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await openKyivAir(page)
  const no2 = page.getByTestId('card-no2_mean_molec_cm2')
  await expect(no2.getByTestId('card-verdict')).toHaveText('○ No significant trend')
  await expect(no2.getByTestId('card-rate')).toContainText('−0.0418 ×10¹⁵ molecules/cm² per year')
  await expect(no2.getByTestId('card-seasonal')).toContainText('−28.0% vs 2015–2019')
  await expect(page.getByTestId('card-ws10m').getByTestId('card-verdict')).toBeVisible()
  await expect(page.getByTestId('card-cloud_amt').getByTestId('card-verdict')).toBeVisible()
  // the portrait opens the guide's insights, one per card
  await expect(page.getByTestId('avatar-badge')).toHaveText('3')
  await page.getByTestId('avatar-button').click()
  const panel = page.getByTestId('avatar-panel')
  await expect(panel.getByTestId('insight-no2_mean_molec_cm2-kyiv_no2_box')).toContainText('averaged 28% below the 2015–2019 average')
  await expect(page.getByTestId('avatar-badge')).toHaveText('3')
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${SHOTS}/2-kyiv-insights-desktop.png` })
  // folded back to the portrait, the guide never hides a chart at this size
  await page.getByTestId('avatar-close').click()
  await expect(panel).toHaveCount(0)
  const portrait = (await page.getByTestId('avatar-button').boundingBox())!
  const chartBox = (await no2.getByTestId('trend-chart').boundingBox())!
  expect(chartBox.y + chartBox.height).toBeLessThanOrEqual(portrait.y)
  await page.screenshot({ path: `${SHOTS}/2b-cards-portrait-desktop.png` })

  await page.getByTestId('window-pre_invasion').click()
  await expect(no2.getByTestId('card-rate')).toContainText('−0.0173')
  await page.getByTestId('change-place').click()
  await expect(page.getByTestId('place-kyiv_no2_box')).toHaveAttribute('aria-pressed', 'true')
})

test('mobile: cards stack under the map with no sideways scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)
  await openKyivAir(page)
  await expect(page.getByTestId('card-no2_mean_molec_cm2').getByTestId('card-verdict')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)
  await page.screenshot({ path: `${SHOTS}/4-cards-mobile.png`, fullPage: true })
})

test('the field guide: variables of the chosen element with definitions, how to read, Escape closes', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await page.getByTestId('evidence-scroll').click()
  await expect(page.getByTestId('variable-guide-empty')).toBeVisible()
  await page.getByTestId('element-water').click()
  await expect(page.getByTestId('variable-guide')).toHaveAttribute('data-element', 'water')
  await expect(page.getByTestId('define-prectotcorr')).toBeVisible()
  await page.getByTestId('element-water').click()
  await page.getByTestId('element-air').click()
  await expect(page.getByTestId('define-no2_mean_molec_cm2')).toContainText('nitrogen dioxide')
  await page.waitForTimeout(500) // let the unroll animation finish
  await page.screenshot({ path: `${SHOTS}/8-field-guide-air-desktop.png` })
  await page.getByRole('tab', { name: 'How to read' }).click()
  await expect(page.getByTestId('scroll-help')).toContainText('Not assessed')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('scroll-help')).toHaveCount(0)
  await expect(page.getByTestId('evidence-scroll')).toBeFocused()
})

test('Show me around: a tour of the current controls, without changing anything, replayable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  const popover = page.locator('.driver-popover')
  await page.getByTestId('show-me-around').click()
  await expect(popover).toBeVisible()
  await expect(popover).toContainText('Study areas')
  await expect(popover).toContainText('1 of 7')
  await page.screenshot({ path: `${SHOTS}/9-tour-step1-desktop.png` })
  await popover.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(popover).toContainText('Tested period')
  await expect(popover).toContainText('2 of 7')
  await popover.getByRole('button', { name: 'Back' }).click()
  await expect(popover).toContainText('Study areas')
  for (let i = 0; i < 6; i += 1) await popover.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(popover).toContainText('Field guide')
  await expect(popover).toContainText('7 of 7')
  await popover.locator('.driver-popover-next-btn').click() // labelled Close on the last stop
  await expect(popover).toHaveCount(0)
  // nothing was selected or opened by the tour
  await expect(page.getByTestId('chosen-place')).toHaveText('Press a place on the map')
  await expect(page.getByTestId('card-area')).toHaveCount(0)

  // replay, then leave with Escape
  await page.getByTestId('show-me-around').click()
  await expect(popover).toContainText('1 of 7')
  await page.keyboard.press('Escape')
  await expect(popover).toHaveCount(0)

  // after Investigate the tour explains the evidence screen and skips nothing on screen
  await openKyivAir(page)
  await page.getByTestId('show-me-around').click()
  await expect(popover).toContainText('Variables')
  await expect(popover).toContainText('1 of 7')
  await popover.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(popover).toContainText('Cards')
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SHOTS}/9b-tour-cards-desktop.png` })
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('card-no2_mean_molec_cm2')).toBeVisible()
})

test('the tile-map explorer is still the default screen', async ({ page }) => {
  await page.route(/tile\.openstreetmap\.org|arcgisonline\.com/, (route) => route.fulfill({ status: 204 }))
  await page.goto('/')
  await expect(page.getByTestId('ukraine-map')).toBeVisible()
  await expect(page.getByTestId('atlas-page')).toHaveCount(0)
})
