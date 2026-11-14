import { formatPercent, monthsRangeLabel, yearsRangeLabel } from '../../adapters/format'
import type { SeasonalSummary } from '../../adapters/baselines'
import styles from './AvatarIntro.module.css'

/**
 * Placeholder guide. Final character art is pending, so the figure is a plain
 * abstract mark. The introduction is composed from API values only.
 */
export function AvatarIntro({ summary }: { summary: SeasonalSummary }) {
  const { comparison, baselineYears } = summary
  const months = monthsRangeLabel(comparison.months_included)
  return (
    <aside className={styles.wrap} aria-label="Guide introduction" data-testid="avatar-intro">
      <svg className={styles.mark} viewBox="0 0 64 64" role="img" aria-label="Guide placeholder (final character art pending)">
        <circle cx="32" cy="32" r="30" fill="#17283f" />
        <circle cx="32" cy="26" r="9" fill="none" stroke="#9db0c7" strokeWidth="2.5" />
        <path d="M14 52c2-11 10-16 18-16s16 5 18 16" fill="none" stroke="#9db0c7" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M20 14c6-5 18-5 24 0" fill="none" stroke="#eb6834" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <div className={styles.text}>
        <p className={styles.name}>Your guide <span className={styles.pending}>(character art pending)</span></p>
        <p>
          I read the satellite record over Kyiv.{' '}
          {comparison.pct_change === null ? (
            <>For {months} {summary.targetYear}, the percentage difference from the {baselineYears} baseline cannot be shown.</>
          ) : (
            <>
              For {months} {summary.targetYear}, the NO₂ column sits {formatPercent(comparison.pct_change)} from the{' '}
              {yearsRangeLabel(comparison.baseline_years_requested)} average.
            </>
          )}{' '}
          That is a measured difference. It is not a significance test and it does not show what caused it.
        </p>
      </div>
    </aside>
  )
}
