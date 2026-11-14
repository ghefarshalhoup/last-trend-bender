import type { ElementEntry } from '../../api/types'
import type { SeasonalSummary } from '../../adapters/baselines'
import { formatDays, formatFraction, formatPercent, monthsRangeLabel, yearsRangeLabel } from '../../adapters/format'
import type { MonthRow } from '../../adapters/months'
import styles from './AvatarGuide.module.css'

interface Props {
  summary: SeasonalSummary
  /** The month the reader opened, or null. */
  month: MonthRow | null
  /** Catalog entries, so the guide can say honestly what it cannot read yet. */
  elements: ElementEntry[]
}

/**
 * Placeholder guide (final character art pending). The narration is composed
 * only from API values and follows the selected element (Air), baseline and
 * month. It is descriptive: it never claims significance or a cause.
 */
export function AvatarGuide({ summary, month, elements }: Props) {
  const { comparison } = summary
  const months = monthsRangeLabel(comparison.months_included)
  const baseline = yearsRangeLabel(comparison.baseline_years_requested)
  const waiting = elements.filter((e) => e.status !== 'available').map((e) => e.label)

  return (
    <aside className={styles.wrap} aria-label="Guide narration" data-testid="avatar-intro">
      <svg className={styles.mark} viewBox="0 0 64 64" role="img" aria-label="Guide placeholder (final character art pending)">
        <circle cx="32" cy="32" r="30" fill="#17283f" />
        <circle cx="32" cy="26" r="9" fill="none" stroke="#9db0c7" strokeWidth="2.5" />
        <path d="M14 52c2-11 10-16 18-16s16 5 18 16" fill="none" stroke="#9db0c7" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M20 14c6-5 18-5 24 0" fill="none" stroke="#eb6834" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <div className={styles.text}>
        <p className={styles.name}>
          Your guide <span className={styles.pending}>(character art pending)</span>
        </p>

        <p data-testid="guide-element">
          I came to read what Ukraine's air, fire, water and land recorded. Today I am reading <strong>Air</strong>:{' '}
          {comparison.pct_change === null ? (
            <>the percentage difference for {months} {summary.targetYear} against {baseline} cannot be shown.</>
          ) : (
            <>
              for {months} {summary.targetYear}, the NO₂ column over the Kyiv study area sits{' '}
              <strong>{formatPercent(comparison.pct_change)}</strong> from the {baseline} average.
            </>
          )}
        </p>

        {month ? (
          <p data-testid="guide-month">
            <strong>{month.long} {summary.targetYear}.</strong>{' '}
            {month.target.mean === null ? (
              <>The satellite has no valid measurement for this month.</>
            ) : month.change.pct_change === null ? (
              <>The comparison with {baseline} is not available for this month.</>
            ) : (
              <>
                It sits {formatPercent(month.change.pct_change)} from the {baseline} {month.long} average.
              </>
            )}{' '}
            {month.target.mean !== null ? (
              <>
                The satellite saw {formatDays(month.target.validDays, month.target.calendarDays)} ({formatFraction(month.target.coverage)})
                {month.target.lowCoverage ? ', fewer than half, so I hold this month loosely.' : '.'}
              </>
            ) : null}
          </p>
        ) : (
          <p className={styles.muted}>Pick a month and I will tell you how much of it the satellite actually saw.</p>
        )}

        <p className={styles.limits}>
          This is a measured difference. Before/after significance is not assessed and the cause is not established.
        </p>

        {waiting.length > 0 ? (
          <p className={styles.muted} data-testid="guide-waiting">
            Not yet readable: {waiting.join(', ')}.
          </p>
        ) : null}
      </div>
    </aside>
  )
}
