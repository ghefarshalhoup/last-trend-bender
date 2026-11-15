import { AnimatePresence, motion } from 'motion/react'
import { pctStatusReason } from '../../adapters/absence'
import { AbsenceMark } from '../../components/Absence/Absence'
import type { BaselineOption } from '../../adapters/baselines'
import { formatDays, formatFraction, formatPercent, formatScientific, formatSignedScientific, yearsRangeLabel } from '../../adapters/format'
import type { MonthRow } from '../../adapters/months'
import styles from './MonthInspector.module.css'

interface Props {
  row: MonthRow | null
  baseline: BaselineOption
  baselineYears: number[]
}

export function MonthInspector({ row, baseline, baselineYears }: Props) {
  const baselineLabel = yearsRangeLabel(baselineYears)
  return (
    <section className={styles.panel} aria-labelledby="inspector-heading" aria-live="polite" data-testid="month-inspector">
      <AnimatePresence mode="wait" initial={false}>
        {row === null ? (
          <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <h3 id="inspector-heading" className={styles.heading}>Month inspector</h3>
            <p className={styles.empty}>
              Choose a month on the chart or from the month buttons to see its measurement, how it compares with the {baselineLabel}{' '}
              baseline, and how many days the satellite observed.
            </p>
          </motion.div>
        ) : (
          <motion.div
            key={`${row.calendarMonth}-${baseline.id}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          >
            <h3 id="inspector-heading" className={styles.heading} data-testid="inspector-title">
              {row.long} 2022
            </h3>
            <p className={styles.scope}>
              Monthly detail. The seasonal headline above is not changed by the month you pick.
            </p>

            {row.target.lowCoverage ? (
              <p className={styles.lowCoverage} role="note" data-testid="inspector-low-coverage">
                <span aria-hidden="true">▲ </span>
                Low coverage: {formatDays(row.target.validDays, row.target.calendarDays)} observed (
                {formatFraction(row.target.coverage)}). Treat this month's mean with caution.
              </p>
            ) : null}

            <dl className={styles.list}>
              <div>
                <dt>2022 measurement</dt>
                <dd data-testid="inspector-2022">
                  {row.target.mean === null ? (
                    <AbsenceMark kind="missing_measurement" />
                  ) : (
                    <>
                      {formatScientific(row.target.mean)} <span className={styles.unit}>molecules/cm²</span>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>Days observed</dt>
                <dd data-testid="inspector-days">
                  {formatDays(row.target.validDays, row.target.calendarDays)} ({formatFraction(row.target.coverage)})
                </dd>
              </div>
              <div>
                <dt>{baselineLabel} mean for {row.long}</dt>
                <dd data-testid="inspector-baseline">
                  {row.baseline.mean === null ? (
                    <AbsenceMark kind="missing_measurement" />
                  ) : (
                    <>
                      {formatScientific(row.baseline.mean)} <span className={styles.unit}>molecules/cm²</span>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>Range across baseline years</dt>
                <dd>
                  {row.baseline.min === null || row.baseline.max === null ? (
                    <AbsenceMark kind="missing_measurement" />
                  ) : (
                    <>
                      {formatScientific(row.baseline.min)} to {formatScientific(row.baseline.max)}
                      <span className={styles.note}> Variability between years, not a confidence interval.</span>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>Change vs {baselineLabel}</dt>
                <dd data-testid="inspector-change">
                  {row.change.pct_change === null ? (
                    <AbsenceMark kind="unavailable" reason={pctStatusReason(row.change.pct_change_status)} />
                  ) : (
                    <>
                      <strong>{formatPercent(row.change.pct_change)}</strong>
                      {row.change.absolute_change_molec_cm2 === null ? null : (
                        <span className={styles.unit}> ({formatSignedScientific(row.change.absolute_change_molec_cm2)} molecules/cm²)</span>
                      )}
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt>Baseline years used</dt>
                <dd>
                  {row.baseline.availableYears.length > 0 ? yearsRangeLabel(row.baseline.availableYears) : <AbsenceMark kind="missing_measurement" />}
                  {row.baseline.unavailableYears.length > 0 ? (
                    <span className={styles.note}> No valid data in {row.baseline.unavailableYears.join(', ')}.</span>
                  ) : null}
                  {row.baseline.flaggedYearsDetail.length > 0 ? (
                    <span className={styles.note}> Low coverage in {row.baseline.flaggedYearsDetail.join('; ')}.</span>
                  ) : null}
                </dd>
              </div>
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
