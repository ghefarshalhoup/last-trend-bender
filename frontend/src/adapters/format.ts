/**
 * Presentation helpers only. Nothing here derives a scientific result; it turns
 * numbers the API already computed into readable text.
 */

const SUPERSCRIPT: Record<string, string> = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻',
}

export const MINUS = '−'

export function toSuperscript(n: number): string {
  return String(n)
    .split('')
    .map((ch) => SUPERSCRIPT[ch] ?? ch)
    .join('')
}

/** 2357619230901594 → "2.36 × 10¹⁵". Negative values use a true minus sign. */
export function formatScientific(value: number, digits = 2): string {
  const [mantissa = '0', exponent = '0'] = Math.abs(value).toExponential(digits).split('e')
  const sign = value < 0 ? MINUS : ''
  return `${sign}${mantissa} × 10${toSuperscript(Number(exponent))}`
}

/** Like formatScientific but with an explicit "+" for increases. */
export function formatSignedScientific(value: number, digits = 2): string {
  if (value > 0) return `+${formatScientific(value, digits)}`
  return formatScientific(value, digits)
}

/** -27.9594 → "−28.0%". */
export function formatPercent(value: number, digits = 1): string {
  const rounded = Math.abs(value).toFixed(digits)
  if (value < 0 && Number(rounded) !== 0) return `${MINUS}${rounded}%`
  if (value > 0 && Number(rounded) !== 0) return `+${rounded}%`
  return `${rounded}%`
}

/** A fraction (0.2667) as a whole percent: "27%". */
export function formatFraction(fraction: number): string {
  return `${Math.round(fraction * 100)}%`
}

export function formatDays(valid: number, calendar: number): string {
  return `${valid} of ${calendar} days`
}

export const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
] as const

export function monthName(calendarMonth: number): string {
  return MONTH_NAMES[calendarMonth - 1] ?? `Month ${calendarMonth}`
}

/** "2022-04" → 4. Returns null when the string is not a year-month. */
export function calendarMonthOf(yearMonth: string): number | null {
  const match = /^\d{4}-(\d{2})$/.exec(yearMonth)
  if (!match) return null
  const month = Number(match[1])
  return month >= 1 && month <= 12 ? month : null
}

/** "2022-04" → "April 2022". */
export function formatYearMonth(yearMonth: string): string {
  const month = calendarMonthOf(yearMonth)
  if (month === null) return yearMonth
  return `${monthName(month)} ${yearMonth.slice(0, 4)}`
}

/** [3,4,5,6,7,8] → "March–August"; non-contiguous sets are listed. */
export function monthsRangeLabel(months: number[]): string {
  if (months.length === 0) return 'no months'
  const sorted = [...months].sort((a, b) => a - b)
  const first = sorted[0] as number
  const last = sorted[sorted.length - 1] as number
  const contiguous = sorted.every((m, i) => i === 0 || m === (sorted[i - 1] as number) + 1)
  if (sorted.length === 1) return monthName(first)
  if (contiguous) return `${monthName(first)}–${monthName(last)}`
  return sorted.map(monthName).join(', ')
}

/** [2015..2019] → "2015–2019". */
export function yearsRangeLabel(years: number[]): string {
  if (years.length === 0) return 'no years'
  const min = Math.min(...years)
  const max = Math.max(...years)
  return min === max ? String(min) : `${min}–${max}`
}
