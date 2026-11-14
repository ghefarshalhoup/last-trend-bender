import { BASELINES, DEFAULT_BASELINE } from '../../../../adapters/baselines'
import { fetchStudy } from '../../../../api/airStudy'
import type { StudyPackage } from '../../../../api/types'
import type { EvidenceLayer } from '../types'
import { AirEvidence } from './AirEvidence'
import { AirKey } from './AirKey'
import { AirMapLabel, AirMapSvg } from './AirMap'
import { airGuide, baselineLabel, KYIV_FEATURE, readAir } from './airReading'

/**
 * Air: one fixed study polygon around Kyiv. Month and baseline change its
 * colour and label, never its position or shape.
 */
export const airLayer: EvidenceLayer<StudyPackage> = {
  id: 'air',
  title: 'Air · NO₂ over Kyiv',
  loadingText: 'Reading the Air record for Kyiv…',
  defaultSelection: { period: null, comparison: DEFAULT_BASELINE.id, feature: null },
  load: fetchStudy,
  present(study, selection, actions) {
    const reading = readAir(study, selection)
    const toggle = () => actions.selectFeature(reading.featureSelected ? null : KYIV_FEATURE)
    const boundary = study.map.study_boundary
    return {
      controls: {
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
      },
      mapSvg: <AirMapSvg boundary={boundary} reading={reading} onToggle={toggle} />,
      mapHtml: <AirMapLabel boundary={boundary} reading={reading} onToggle={toggle} />,
      mapKey: <AirKey />,
      evidence: <AirEvidence study={study} reading={reading} onSelectMonth={(m) => actions.selectPeriod(String(m))} />,
      guide: airGuide(reading),
    }
  },
}
