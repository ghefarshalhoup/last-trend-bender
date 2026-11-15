import { AbsenceMark } from '../../components/Absence/Absence'
import { pctStatusReason } from '../../adapters/absence'
import type { SeasonalSummary as Summary } from '../../adapters/baselines'
import { formatPercent, formatScientific, formatSignedScientific, formatYearMonth } from '../../adapters/format'
import type { Comparison } from '../../api/types'
import styles from './SeasonalSummary.module.css'

function PctValue({ comparison }: { comparison: Comparison }) {
  if (comparison.pct_change === null) {
    return (
      <AbsenceMark kind="unavailable" context="Percent change" reason={pctStatusReason(comparison.pct_change_status)} />
    )
  }
  return <>{formatPercent(comparison.pct_change)}</>
}

export function SeasonalSummary({ summary }: { summary: Summary }) {
  const { comparison, excludingLowCoverage, baselineYears, monthsLabel, targetYear } = summary
  const direction =
    comparison.pct_change === null ? null : comparison.pct_change < 0 ? 'lower' : comparison.pct_change > 0 ? 'higher' : 'unchanged'

  return (
    <section className={styles.summary} aria-labelledby="seasonal-heading" data-testid="seasonal-summary">
      <h2 id="seasonal-heading" className={styles.heading}>
        {monthsLabel} {targetYear}, seasonal difference
      </h2>

      <p className={styles.number} data-testid="seasonal-pct" data-baseline={summary.option.id}>
        <PctValue comparison={comparison} />
      </p>
      <p className={styles.sentence}>
        {direction && direction !== 'unchanged' ? (
          <>
            tropospheric NO₂ over the study area was <strong>{direction}</strong> than the {baselineYears} average for the same
            months.
          </>
        ) : (
          <>Compared with the {baselineYears} average for the same months.</>
        )}
      </p>

      <dl className={styles.facts}>
        <div>
          <dt>Absolute change</dt>
          <dd data-testid="seasonal-abs">
            {comparison.absolute_change_molec_cm2 === null ? (
              <AbsenceMark kind="unavailable" />
            ) : (
              <>
                {formatSignedScientific(comparison.absolute_change_molec_cm2)} <span className={styles.unit}>molecules/cm²</span>
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>{baselineYears} mean</dt>
          <dd>
            {comparison.baseline_mean_molec_cm2 === null ? (
              <AbsenceMark kind="unavailable" />
            ) : (
              formatScientific(comparison.baseline_mean_molec_cm2)
            )}
          </dd>
        </div>
        <div>
          <dt>{targetYear} mean</dt>
          <dd>
            {comparison.target_mean_molec_cm2 === null ? (
              <AbsenceMark kind="unavailable" />
            ) : (
              formatScientific(comparison.target_mean_molec_cm2)
            )}
          </dd>
        </div>
      </dl>

      <p className={styles.method}>
        {comparison.label}. Weighted by valid observation days, {comparison.target_valid_days} of {comparison.target_calendar_days}{' '}
        days observed in {targetYear}.
      </p>

      {excludingLowCoverage ? (
        <p className={styles.sensitivity} data-testid="sensitivity-line">
          Leaving out the months observed on fewer than half of their days
          {excludingLowCoverage.flagged_months_in_target.length > 0
            ? ` (${excludingLowCoverage.flagged_months_in_target.map((m) => formatYearMonth(m.month)).join(', ')})`
            : ''}
          :{' '}
          <strong>
            {excludingLowCoverage.pct_change === null ? (
              <AbsenceMark kind="unavailable" reason={pctStatusReason(excludingLowCoverage.pct_change_status)} />
            ) : (
              formatPercent(excludingLowCoverage.pct_change)
            )}
          </strong>
          .
        </p>
      ) : null}
    </section>
  )
}
