import { Disclosure } from '../../../../components/Disclosure/Disclosure'
import { TrendChart } from '../../TrendChart'
import type { AirTrendReading } from './airTrend'
import styles from './AirLayer.module.css'

const VERDICT_WORD = { significant: 'Significant', not_significant: 'Not statistically significant', not_assessed: 'Not assessed' } as const
const VERDICT_ICON = { significant: '●', not_significant: '○', not_assessed: '–' } as const

/** Long-term trend view: the full timeline, then the verdict, the rate with its uncertainty, and the test details. */
export function AirTrend({ reading }: { reading: AirTrendReading }) {
  const { window } = reading
  return (
    <div className={styles.evidence}>
      <section aria-label="Verdict" className={styles.verdict} data-verdict={reading.verdict} data-testid="trend-verdict">
        <p className={styles.verdictTag}>
          <span aria-hidden="true">{VERDICT_ICON[reading.verdict]}</span> {VERDICT_WORD[reading.verdict]}
          <span className={styles.verdictPeriod}> · {reading.windowLabel}, {reading.rangeLabel}</span>
        </p>
        <p className={styles.verdictText} data-testid="trend-verdict-text">{reading.verdictText}</p>
        {reading.rateText ? (
          <dl className={styles.facts}>
            <div>
              <dt>Estimated change</dt>
              <dd data-testid="trend-rate">{reading.rateText}</dd>
            </div>
            {reading.intervalText ? (
              <div>
                <dt>95% confidence interval</dt>
                <dd data-testid="trend-interval">{reading.intervalText}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        {reading.verdict === 'not_significant' ? (
          <p className={styles.small}>The interval includes zero, so the data are consistent with no change at all.</p>
        ) : null}
      </section>

      <section aria-label="Timeline">
        <h3>Monthly NO₂ over Kyiv, {reading.rangeLabel.replace(/^[A-Za-z]+ /, '').replace(/ – [A-Za-z]+ /, '–')}</h3>
        <TrendChart
          points={reading.points}
          unitLabel="NO₂ column (×10¹⁵ molecules/cm²)"
          seriesLabel="Monthly mean"
          lowLabel="Under half the days seen"
          eventT={reading.invasionT}
          eventLabel="Invasion, 24 Feb 2022"
          analysisEndT={reading.analysisEndT}
          rateLine={reading.rateLine}
          formatValue={(v) => `${v.toFixed(2)} × 10¹⁵ molecules/cm²`}
          ariaLabel={`Monthly NO₂ over the Kyiv study area with the invasion date marked. ${reading.verdictText}`}
        />
        <p className={styles.small}>
          The tall peaks are winters: NO₂ rises and falls with the seasons every year. The dashed line shows the estimated rate,
          drawn through the period&rsquo;s average for illustration.
        </p>
      </section>

      <Disclosure title="How this was tested" hint="test, p-value, assumptions">
        <dl className={styles.facts} data-testid="trend-details">
          <div>
            <dt>Test</dt>
            <dd>{window.primary_method}</dd>
          </div>
          <div>
            <dt>p-value</dt>
            <dd>{reading.pValueText ?? 'Not assessed'}</dd>
          </div>
          {reading.mannKendallPText ? (
            <div>
              <dt>Mann–Kendall check (rank-based)</dt>
              <dd>p = {reading.mannKendallPText}</dd>
            </div>
          ) : null}
          <div>
            <dt>Months analysed</dt>
            <dd>{window.n_months}</dd>
          </div>
        </dl>
        <p className={styles.small}>A result counts as significant when p is below 0.05.</p>
        <ul className={styles.caveats}>
          {window.assumptions_and_caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Disclosure>
    </div>
  )
}
