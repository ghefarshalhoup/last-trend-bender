import { formatDays, formatFraction, formatYearMonth } from '../../adapters/format'
import type { FlaggedMonth } from '../../api/types'
import styles from './CoverageWarnings.module.css'

interface Props {
  warnings: FlaggedMonth[]
  notices: string[]
}

/**
 * Coverage warnings and the backend's scientific notices. Both stay on screen
 * at all times: they are part of the result, not decoration around it.
 */
export function CoverageWarnings({ warnings, notices }: Props) {
  return (
    <aside className={styles.wrap} aria-label="Coverage warnings and scientific notices" data-testid="warnings">
      {warnings.length > 0 ? (
        <div className={styles.coverage} role="note">
          <p className={styles.title}>
            <span className={styles.icon} aria-hidden="true">▲</span> Low coverage
          </p>
          <ul className={styles.list}>
            {warnings.map((w) => (
              <li key={w.month} data-testid={`coverage-${w.month}`}>
                <strong>{formatYearMonth(w.month)}</strong>: satellite observed {formatDays(w.valid_days, w.calendar_days)} (
                {formatFraction(w.coverage_fraction)}). Below half of the month, so its mean may not represent the whole month.
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {notices.length > 0 ? (
        <div className={styles.notices}>
          <p className={styles.title}>
            <span className={styles.icon} aria-hidden="true">ⓘ</span> What this result does not claim
          </p>
          <ul className={styles.list}>
            {notices.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  )
}
