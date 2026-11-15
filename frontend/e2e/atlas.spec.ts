import { expect, test, type Page } from '@playwright/test'

// Illustrated atlas against the REAL FastAPI backend (see playwright.config.ts).
const SHOTS = '../docs/screenshots/atlas-poc'

async function open(page: Page) {
  await page.goto('/#/atlas')
  await expect(page.getByTestId('place-kyiv_no2_box')).toBeVisible()
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
      const x = frame.left + (Number(city.dataset.x) / 1600) * frame.width
      const y = frame.top + (Number(city.dataset.y) / 1000) * frame.height
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

test('guided example: Kyiv NO₂ with wind and cloud, numbers from the API', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await page.getByTestId('guided-example').click()
  const no2 = page.getByTestId('card-no2_mean_molec_cm2')
  await expect(no2.getByTestId('card-verdict')).toHaveText('○ No significant trend')
  await expect(no2.getByTestId('card-rate')).toContainText('−0.0418 ×10¹⁵ molecules/cm² per year')
  await expect(no2.getByTestId('card-seasonal')).toContainText('−28.0% vs 2015–2019')
  await expect(page.getByTestId('card-ws10m').getByTestId('card-verdict')).toBeVisible()
  await expect(page.getByTestId('card-cloud_amt').getByTestId('card-verdict')).toBeVisible()
  await expect(page.getByTestId('guide-bubble')).toContainText('averaged 28% below the 2015–2019 average')
  // the guide never hides a card at this size
  const guide = (await page.getByTestId('guide-bubble').boundingBox())!
  const chartBox = (await no2.getByTestId('trend-chart').boundingBox())!
  expect(chartBox.y + chartBox.height).toBeLessThanOrEqual(guide.y)
  await page.screenshot({ path: `${SHOTS}/2-guided-example-desktop.png` })

  await page.getByTestId('window-pre_invasion').click()
  await expect(no2.getByTestId('card-rate')).toContainText('−0.0173')
  await page.getByTestId('change-place').click()
  await expect(page.getByTestId('place-kyiv_no2_box')).toHaveAttribute('aria-pressed', 'true')
})

test('mobile: cards stack under the map with no sideways scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)
  await page.getByTestId('guided-example').click()
  await expect(page.getByTestId('card-no2_mean_molec_cm2').getByTestId('card-verdict')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)
  await page.screenshot({ path: `${SHOTS}/4-guided-example-mobile.png`, fullPage: true })
})

test('the how-to-read scroll explains the three verdicts and closes with Escape', async ({ page }) => {
  await open(page)
  await page.getByTestId('evidence-scroll').click()
  await expect(page.getByTestId('scroll-help')).toContainText('Not assessed')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('scroll-help')).toHaveCount(0)
  await expect(page.getByTestId('evidence-scroll')).toBeFocused()
})

test('the tile-map explorer is still the default screen', async ({ page }) => {
  await page.route(/tile\.openstreetmap\.org|arcgisonline\.com/, (route) => route.fulfill({ status: 204 }))
  await page.goto('/')
  await expect(page.getByTestId('ukraine-map')).toBeVisible()
  await expect(page.getByTestId('atlas-page')).toHaveCount(0)
})
