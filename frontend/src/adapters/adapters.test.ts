import { describe, expect, it } from 'vitest'
import { BASELINES, getSeasonalSummary } from './baselines'
import { formatPercent, formatScientific, monthsRangeLabel } from './format'
import { buildChartPoints, buildMonthRows } from './months'
import { studyFixture } from '../test/fixtures'

describe('format', () => {
  it('uses a true minus sign and keeps the sign of small values', () => {
    expect(formatPercent(-27.9594)).toBe('−28.0%')
    expect(formatPercent(3.2)).toBe('+3.2%')
    expect(formatPercent(-0.001)).toBe('0.0%')
  })
  it('formats scientific notation with superscripts', () => {
    expect(formatScientific(2.357e15)).toBe('2.36 × 10¹⁵')
    expect(formatScientific(-6.59e14)).toBe('−6.59 × 10¹⁴')
  })
  it('labels month ranges', () => {
    expect(monthsRangeLabel([3, 4, 5, 6, 7, 8])).toBe('March–August')
    expect(monthsRangeLabel([3, 5])).toBe('March, May')
  })
})

describe('baseline summaries read the exported comparisons', () => {
  it('primary and sensitivity map to different exported comparisons', () => {
    const [primary, sensitivity] = BASELINES.map((b) => getSeasonalSummary(studyFixture.result, b))
    expect(primary!.comparison.pct_change).toBeCloseTo(-28, 0)
    expect(sensitivity!.comparison.pct_change).toBeCloseTo(-20, 0)
    expect(primary!.comparison).toBe(studyFixture.result.comparisons.primary_2015_2019_valid_day)
  })
})

describe('month rows and chart points', () => {
  it('selects the baseline fields for the chosen baseline', () => {
    const [primary, sensitivity] = BASELINES
    const a = buildMonthRows(studyFixture.result.matched_months, primary!)
    const b = buildMonthRows(studyFixture.result.matched_months, sensitivity!)
    expect(a).toHaveLength(6)
    expect(a[0]!.baseline.mean).not.toBe(b[0]!.baseline.mean)
    expect(a[0]!.target.mean).toBe(b[0]!.target.mean)
  })
  it('preserves nulls instead of converting them to zero', () => {
    const matched = structuredClone(studyFixture.result.matched_months)
    matched[1]!.target_2022.mean_molec_cm2 = null
    matched[2]!.primary_2015_2019.mean_molec_cm2 = null
    matched[2]!.primary_2015_2019.min_molec_cm2 = null
    const points = buildChartPoints(buildMonthRows(matched, BASELINES[0]!))
    expect(points[1]!.y2022).toBeNull()
    expect(points[2]!.baseline).toBeNull()
    expect(points[2]!.band).toBeNull()
    expect(points.every((p) => p.y2022 !== 0 && p.baseline !== 0)).toBe(true)
  })
  it('flags April 2022 as low coverage from the API fields', () => {
    const april = buildMonthRows(studyFixture.result.matched_months, BASELINES[0]!).find((r) => r.calendarMonth === 4)!
    expect(april.target.validDays).toBe(8)
    expect(april.target.calendarDays).toBe(30)
    expect(april.target.lowCoverage).toBe(true)
  })
})
