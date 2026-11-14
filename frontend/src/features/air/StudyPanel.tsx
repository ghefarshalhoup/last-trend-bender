import type { BaselineOption } from '../../adapters/baselines'
import type { SeasonalSummary as Summary } from '../../adapters/baselines'
import type { MonthRow } from '../../adapters/months'
import type { ElementEntry, StudyPackage } from '../../api/types'
import { Disclosure } from '../../components/Disclosure/Disclosure'
import { AvatarGuide } from './AvatarGuide'
import { BaselineSelector } from './BaselineSelector'
import { ComparisonChart } from './ComparisonChart'
import { CoverageWarnings } from './CoverageWarnings'
import { EvidencePanel } from './EvidencePanel'
import { FigureGallery } from './FigureGallery'
import { MonthInspector } from './MonthInspector'
import { MonthPicker } from './MonthPicker'
import { SeasonalSummary } from './SeasonalSummary'
import styles from './StudyPanel.module.css'

interface Props {
  study: StudyPackage
  elements: ElementEntry[]
  baseline: BaselineOption
  onBaselineChange: (b: BaselineOption) => void
  summary: Summary
  rows: MonthRow[]
  selectedMonth: number | null
  onSelectMonth: (calendarMonth: number) => void
  onClose: () => void
  onClear: () => void
}

/** Kyiv · NO₂ evidence. Everything here is read from the study package. */
export function StudyPanel({ study, elements, baseline, onBaselineChange, summary, rows, selectedMonth, onSelectMonth, onClose, onClear }: Props) {
  const { result, highlights, charts, map } = study
  const selectedRow = rows.find((r) => r.calendarMonth === selectedMonth) ?? null
  const baselineYears = summary.comparison.baseline_years_requested

  return (
    <section className={styles.panel} aria-labelledby="panel-title" data-testid="study-panel">
      <header className={styles.head}>
        <div>
          <h2 id="panel-title" className={styles.title}>Kyiv</h2>
          <p className={styles.sub}>Tropospheric NO₂ column · {summary.monthsLabel} {summary.targetYear}</p>
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.action} onClick={onClose} data-testid="close-panel">Close panel</button>
          <button type="button" className={styles.action} onClick={onClear}>Clear element</button>
        </div>
      </header>

      <dl className={styles.where}>
        <div><dt>Location</dt><dd>{result.region.name}</dd></div>
        <div><dt>Variable</dt><dd>{result.dataset.variable}</dd></div>
        <div><dt>Study period</dt><dd>{summary.monthsLabel} {summary.targetYear}</dd></div>
      </dl>

      <p className={styles.mapNote} data-testid="map-note">{map.note}</p>

      <BaselineSelector value={baseline} onChange={onBaselineChange} comparisons={result.comparisons} />
      <SeasonalSummary summary={summary} />
      <CoverageWarnings warnings={highlights.coverage_warnings} notices={highlights.notices} />

      <div className={styles.chartBlock}>
        <h3 className={styles.h3}>Month by month, 2022 against {summary.baselineYears}</h3>
        <ComparisonChart rows={rows} baselineYears={baselineYears} selectedMonth={selectedMonth} onSelectMonth={onSelectMonth} />
        <MonthPicker rows={rows} selectedMonth={selectedMonth} onSelect={onSelectMonth} />
      </div>

      <MonthInspector row={selectedRow} baseline={baseline} baselineYears={baselineYears} />
      <AvatarGuide summary={summary} month={selectedRow} elements={elements} />

      <div className={styles.more}>
        <EvidencePanel result={result} highlights={highlights} />
        <Disclosure title="Supplementary figures" hint={`${charts.length} returned by the backend`}>
          <FigureGallery charts={charts} />
        </Disclosure>
      </div>
    </section>
  )
}
