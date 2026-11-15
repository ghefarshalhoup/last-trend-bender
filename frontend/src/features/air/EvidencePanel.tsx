import { Disclosure } from '../../components/Disclosure/Disclosure'
import { AbsenceMark } from '../../components/Absence/Absence'
import { formatScientific, formatSignedScientific, formatYearMonth } from '../../adapters/format'
import type { AirResult, Highlights, TrendWindow } from '../../api/types'
import styles from './EvidencePanel.module.css'

function labelise(value: string): string {
  return value.replace(/_/g, ' ')
}

function TrendBlock({ window: w, slot }: { window: TrendWindow; slot: string }) {
  return (
    <div className={styles.trend} data-testid={`trend-${slot}`}>
      <h4 className={styles.h4}>{w.label}</h4>
      <p className={styles.small}>
        {formatYearMonth(w.start_month)} to {formatYearMonth(w.end_month)}, {w.n_months} months · {w.primary_method}
      </p>
      <dl className={styles.kv}>
        <div>
          <dt>Slope</dt>
          <dd>
            {w.slope_molec_cm2_per_year === null ? (
              <AbsenceMark kind="not_assessed" />
            ) : (
              <>{formatSignedScientific(w.slope_molec_cm2_per_year)} molecules/cm² per year</>
            )}
          </dd>
        </div>
        <div>
          <dt>95% confidence interval</dt>
          <dd>
            {w.ci_95_lower_molec_cm2_per_year === null || w.ci_95_upper_molec_cm2_per_year === null ? (
              <AbsenceMark kind="not_assessed" />
            ) : (
              <>
                {formatSignedScientific(w.ci_95_lower_molec_cm2_per_year)} to {formatSignedScientific(w.ci_95_upper_molec_cm2_per_year)}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>p-value</dt>
          <dd>{w.p_value === null ? <AbsenceMark kind="not_assessed" /> : w.p_value.toFixed(3)}</dd>
        </div>
        <div>
          <dt>Significant at α = 0.05</dt>
          <dd>
            {w.significant_at_alpha_0_05 === null ? <AbsenceMark kind="not_assessed" /> : w.significant_at_alpha_0_05 ? 'Yes' : 'No'}
          </dd>
        </div>
      </dl>
      {w.assumptions_and_caveats.length > 0 ? (
        <ul className={styles.bullets}>
          {w.assumptions_and_caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

interface Props {
  result: AirResult
  highlights: Highlights
}

export function EvidencePanel({ result, highlights }: Props) {
  const ds = result.dataset
  const ba = result.statistics.before_after_seasonal_inference
  const trend = result.statistics.multi_year_seasonality_aware_trend
  const claims = highlights.claim_status

  return (
    <div className={styles.panel} data-testid="evidence">
      <Disclosure title="Sources" hint="Where the numbers come from">
        <dl className={styles.kv}>
          <div><dt>Provider</dt><dd>{ds.provider}</dd></div>
          <div><dt>Instrument and product</dt><dd>{ds.instrument}, {ds.product} {ds.version}</dd></div>
          <div><dt>Variable</dt><dd>{ds.variable} ({ds.units})</dd></div>
          <div><dt>Study area</dt><dd>{result.region.name}</dd></div>
        </dl>
        <ul className={styles.links}>
          {ds.catalogue_url ? <li><a href={ds.catalogue_url} target="_blank" rel="noreferrer">Product catalogue</a></li> : null}
          {ds.reproducibility_url ? <li><a href={ds.reproducibility_url} target="_blank" rel="noreferrer">Reproduce this request in Giovanni</a></li> : null}
        </ul>
      </Disclosure>

      <Disclosure title="Methods" hint="How the comparison is built">
        <p>{highlights.seasonal_differences.description}</p>
        {ds.cloud_screen_rule ? <p>Cloud screening: {ds.cloud_screen_rule}</p> : null}
        {result.quality_rules.proposed_coverage_flag_rule ? <p>Coverage rule: {result.quality_rules.proposed_coverage_flag_rule}</p> : null}
        <p>{result.region.spatial_note}</p>
        <p className={styles.small}>Every figure on this page is read from the API response; none is recalculated in the browser.</p>
      </Disclosure>

      <Disclosure title="Limitations" hint={`${result.limitations.length} caveats from the analysis`}>
        <ul className={styles.bullets} data-testid="limitations">
          {result.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Disclosure>

      <Disclosure title="Statistical status" hint="What was tested, what was not">
        <div className={styles.group} data-testid="stat-before-after">
          <h4 className={styles.h4}>Seasonal before/after significance</h4>
          <p>
            <AbsenceMark kind="not_assessed" context="Before/after significance" />
          </p>
          <dl className={styles.kv}>
            <div><dt>Status</dt><dd>{labelise(ba.status)}</dd></div>
            <div>
              <dt>p-value</dt>
              <dd>{ba.p_value === null ? <AbsenceMark kind="not_assessed" /> : ba.p_value.toFixed(3)}</dd>
            </div>
            <div>
              <dt>95% confidence interval</dt>
              <dd>
                {ba.ci_95_lower_molec_cm2 === null || ba.ci_95_upper_molec_cm2 === null ? (
                  <AbsenceMark kind="not_assessed" />
                ) : (
                  <>{formatScientific(ba.ci_95_lower_molec_cm2)} to {formatScientific(ba.ci_95_upper_molec_cm2)}</>
                )}
              </dd>
            </div>
          </dl>
          {ba.reasons_not_assessed.length > 0 ? (
            <ul className={styles.bullets}>
              {ba.reasons_not_assessed.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className={styles.group} data-testid="stat-trend">
          <h4 className={styles.h4}>Multi-year trend (a separate question)</h4>
          <p className={styles.small}>{highlights.multi_year_trend.description}</p>
          <TrendBlock slot="pre_invasion" window={trend.pre_invasion} />
          <TrendBlock slot="full_record" window={trend.full_record} />
        </div>

        <div className={styles.group} data-testid="stat-claims">
          <h4 className={styles.h4}>Claim status</h4>
          <dl className={styles.kv}>
            <div><dt>Causal attribution to the war</dt><dd>{labelise(claims.causal_attribution)}</dd></div>
            <div><dt>Before/after significance</dt><dd>{labelise(claims.before_after_significance)}</dd></div>
            <div><dt>Reference-region comparison</dt><dd>{labelise(claims.reference_region_comparison)}</dd></div>
          </dl>
        </div>
      </Disclosure>
    </div>
  )
}
