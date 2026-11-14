import { MotionConfig } from 'motion/react'
import { useMemo, useState } from 'react'
import { DEFAULT_BASELINE, getSeasonalSummary, type BaselineOption } from '../../adapters/baselines'
import { buildMonthRows } from '../../adapters/months'
import type { AirStudyBundle } from '../../api/airStudy'
import { AvatarGuide } from './AvatarGuide'
import { BaselineSelector } from './BaselineSelector'
import { ComparisonChart } from './ComparisonChart'
import { CoverageWarnings } from './CoverageWarnings'
import { EvidencePanel } from './EvidencePanel'
import { FigureGallery } from './FigureGallery'
import { Masthead } from './Masthead'
import { MonthInspector } from './MonthInspector'
import { MonthPicker } from './MonthPicker'
import { SeasonalSummary } from './SeasonalSummary'
import { StudyMap } from './StudyMap'
import styles from './AirScreen.module.css'

export function AirScreen({ bundle }: { bundle: AirStudyBundle }) {
  const { study, caseEntry, elements } = bundle
  const { result, highlights, map, charts } = study

  // Two independent pieces of state: the baseline drives the seasonal headline
  // AND the chart series; the month only opens detail and never touches the headline.
  const [baseline, setBaseline] = useState<BaselineOption>(DEFAULT_BASELINE)
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null)

  const summary = useMemo(() => getSeasonalSummary(result, baseline), [result, baseline])
  const rows = useMemo(() => buildMonthRows(result.matched_months, baseline), [result, baseline])
  const selectedRow = rows.find((r) => r.calendarMonth === selectedMonth) ?? null
  const baselineYears = summary.comparison.baseline_years_requested

  return (
    <MotionConfig reducedMotion="user">
      <div className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.inner}>
            <Masthead caseName={caseEntry.name} elements={elements} />
            <div className={styles.heroGrid}>
              <div className={styles.heroText}>
                <h1 className={styles.question}>Was NO₂ different above Kyiv in 2022?</h1>
                <p className={styles.lede}>
                  A satellite looked down at the air over the city every day. Here is how its March–August record for 2022 compares with
                  earlier years.
                </p>
                <BaselineSelector value={baseline} onChange={setBaseline} comparisons={result.comparisons} />
                <SeasonalSummary summary={summary} />
              </div>
              <div className={styles.heroMap}>
                <StudyMap map={map} />
              </div>
            </div>
            <div className={styles.warnings}>
              <CoverageWarnings warnings={highlights.coverage_warnings} notices={highlights.notices} />
            </div>
          </div>
        </section>

        <main className={styles.main}>
          <section className={styles.block} aria-labelledby="chart-heading">
            <h2 id="chart-heading" className={styles.h2}>Month by month, 2022 against {summary.baselineYears}</h2>
            <p className={styles.sectionLede}>
              Same baseline as the headline above. Pick a month to see its measurement and how many days the satellite actually saw.
            </p>
            <div className={styles.chartGrid}>
              <div className={styles.chartCol}>
                <ComparisonChart rows={rows} baselineYears={baselineYears} selectedMonth={selectedMonth} onSelectMonth={setSelectedMonth} />
                <MonthPicker rows={rows} selectedMonth={selectedMonth} onSelect={setSelectedMonth} />
              </div>
              <div className={styles.sideCol}>
                <MonthInspector row={selectedRow} baseline={baseline} baselineYears={baselineYears} />
                <AvatarGuide summary={summary} month={selectedRow} elements={elements} />
              </div>
            </div>
          </section>

          <section className={styles.block} aria-labelledby="evidence-heading">
            <h2 id="evidence-heading" className={styles.h2}>Evidence and limits</h2>
            <EvidencePanel result={result} highlights={highlights} />
          </section>

          <section className={styles.block} aria-labelledby="figures-heading">
            <h2 id="figures-heading" className={styles.h2}>Supplementary figures</h2>
            <p className={styles.sectionLede}>Static figures from the analysis, served by the backend.</p>
            <FigureGallery charts={charts} />
          </section>
        </main>
      </div>
    </MotionConfig>
  )
}
