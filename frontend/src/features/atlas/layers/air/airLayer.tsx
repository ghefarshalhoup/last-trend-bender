import { BASELINES, DEFAULT_BASELINE } from '../../../../adapters/baselines'
import { fetchStudy } from '../../../../api/airStudy'
import type { StudyPackage } from '../../../../api/types'
import type { EvidenceLayer, LayerControls, LayerView } from '../types'
import { AirAbout } from './AirAbout'
import { AirEvidence } from './AirEvidence'
import { AirMapLabel, AirMapSvg } from './AirMap'
import { AirTrend } from './AirTrend'
import { airGuide, baselineLabel, KYIV_FEATURE, readAir } from './airReading'
import { airTrendGuide, DEFAULT_WINDOW, readAirTrend, TREND_WINDOWS } from './airTrend'

const VIEWS: LayerView[] = [
  { id: 'trend', label: 'Long-term trend', question: 'Has NO₂ over Kyiv gone up or down across the years, and is that change real or within the noise?' },
  { id: 'comparison', label: '2022 comparison', question: 'How did the months after the invasion compare with the same months in earlier years?' },
]

/**
 * Air: one fixed study polygon around Kyiv. The view changes what it says
 * (trend verdict or 2022 comparison), never its position or shape.
 */
export const airLayer: EvidenceLayer<StudyPackage> = {
  id: 'air',
  title: 'Air · NO₂ over Kyiv',
  loadingText: 'Reading the Air record for Kyiv…',
  defaultSelection: { view: 'trend', window: DEFAULT_WINDOW, period: null, comparison: DEFAULT_BASELINE.id, feature: null },
  load: fetchStudy,
  present(study, selection, actions) {
    const view = selection.view === 'comparison' ? 'comparison' : 'trend'
    const reading = readAir(study, selection)
    const trend = readAirTrend(study, selection)
    const toggle = () => actions.selectFeature(selection.feature === KYIV_FEATURE ? null : KYIV_FEATURE)
    const boundary = study.map.study_boundary

    const controls: LayerControls =
      view === 'trend'
        ? { windows: { label: 'Analysis period', options: TREND_WINDOWS.map((w) => ({ id: w.id, label: w.label })) } }
        : {
            periods: {
              label: 'Month in 2022',
              wholePeriodLabel: reading.summary.monthsLabel,
              options: reading.rows.map((row) => ({
                id: String(row.calendarMonth),
                label: row.long,
                detail: `${row.target.validDays}/${row.target.calendarDays} days`,
                warning: row.target.lowCoverage ? 'low coverage' : undefined,
              })),
            },
            comparisons: {
              label: 'Compare 2022 with',
              options: BASELINES.map((b) => ({ id: b.id, label: baselineLabel(study, b), detail: b.role })),
            },
          }

    return {
      views: VIEWS,
      controls,
      mapSvg: <AirMapSvg boundary={boundary} view={view} reading={reading} trend={trend} onToggle={toggle} />,
      mapHtml: <AirMapLabel boundary={boundary} view={view} reading={reading} trend={trend} onToggle={toggle} />,
      evidence:
        view === 'trend' ? (
          <AirTrend reading={trend} />
        ) : (
          <AirEvidence study={study} reading={reading} onSelectMonth={(m) => actions.selectPeriod(String(m))} />
        ),
      about: <AirAbout study={study} />,
      guide: view === 'trend' ? airTrendGuide(trend) : airGuide(reading),
    }
  },
}
