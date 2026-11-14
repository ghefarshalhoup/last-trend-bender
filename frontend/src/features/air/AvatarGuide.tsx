import type { ElementEntry } from '../../api/types'
import { resolveElements } from '../explorer/elements'
import type { SeasonalSummary } from '../../adapters/baselines'
import { formatDays, formatFraction, formatPercent, monthsRangeLabel, yearsRangeLabel } from '../../adapters/format'
import type { MonthRow } from '../../adapters/months'
import { AvatarMark } from '../../components/Avatar/AvatarMark'
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
  const waiting = resolveElements(elements).filter((e) => !e.available).map((e) => e.label)

  return (
    <aside className={styles.wrap} aria-label="Guide narration" data-testid="avatar-intro">
      <AvatarMark />
      <div className={styles.text}>
        <p className={styles.name}>
          Your guide <span className={styles.pending}>(character art pending)</span>
        </p>

        <p data-testid="guide-element">
          I came to read what Ukraine's air, fire, water and earth recorded. Today I am reading <strong>Air</strong>:{' '}
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
