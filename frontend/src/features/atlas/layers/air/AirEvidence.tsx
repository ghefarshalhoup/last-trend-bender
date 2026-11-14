import type { StudyPackage } from '../../../../api/types'
import { ComparisonChart } from '../../../air/ComparisonChart'
import { CoverageWarnings } from '../../../air/CoverageWarnings'
import type { AirReading } from './airReading'
import styles from './AirLayer.module.css'

interface Props {
  study: StudyPackage
  reading: AirReading
  onSelectMonth: (calendarMonth: number) => void
}

/** Evidence widget body for Air: the selected reading, the NO₂ timeline, coverage and sources. */
export function AirEvidence({ study, reading, onSelectMonth }: Props) {
  const { dataset, region } = study.result
  return (
    <div className={styles.evidence}>
      <section aria-label="Selected reading" className={styles.reading} data-testid="evidence-reading">
        <p className={styles.readingPeriod}>{reading.periodLabel} · compared with {reading.baselineYears}</p>
        <p className={styles.readingValue} data-testid="evidence-value">{reading.pctText}</p>
        <p className={styles.readingMeta}>
          Tropospheric NO₂, average over the Kyiv study area. {reading.daysText}.
        </p>
        {reading.lowCoverage ? (
          <p className={styles.warning} role="note" data-testid="evidence-low-coverage">
            <span aria-hidden="true">▲</span> Low coverage: the satellite observed {reading.validDays} of {reading.calendarDays} days. Treat this month as uncertain.
          </p>
        ) : null}
      </section>

      {reading.featureSelected ? (
        <section className={styles.area} data-testid="evidence-area">
          <h3>Study area</h3>
          <p>{region.spatial_note}</p>
          <p>{study.map.note}</p>
        </section>
      ) : null}

      <section>
        <h3>Monthly NO₂: 2022 and the baseline</h3>
        <ComparisonChart
          rows={reading.rows}
          baselineYears={reading.summary.comparison.baseline_years_requested}
          selectedMonth={reading.row?.calendarMonth ?? null}
          onSelectMonth={onSelectMonth}
        />
      </section>

      <CoverageWarnings warnings={study.highlights.coverage_warnings} notices={study.highlights.notices} />

      <section className={styles.source}>
        <h3>Source</h3>
        <p>
          {dataset.provider} · {dataset.instrument} · {dataset.product} ({dataset.version}). Comparisons are precomputed by the
          project pipeline and served unchanged by the API.
        </p>
      </section>
    </div>
  )
}
