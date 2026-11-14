import type { StudyPackage } from '../../../../api/types'
import styles from './AirLayer.module.css'

/** About tab: what NO₂ is, where the numbers come from, and what they cannot tell you. */
export function AirAbout({ study }: { study: StudyPackage }) {
  const { dataset, region, limitations } = study.result
  return (
    <div className={styles.evidence} data-testid="air-about">
      <section>
        <h3>What it measures</h3>
        <p>
          Nitrogen dioxide (NO₂) is a gas released mainly when fuel is burned: traffic, power plants, industry and fires. The
          satellite measures how much NO₂ is in the column of air above the Kyiv study area.
        </p>
      </section>
      <section className={styles.source}>
        <h3>Study area</h3>
        <p>{region.spatial_note}</p>
        <p>{study.map.note}</p>
      </section>
      <section className={styles.source}>
        <h3>Source</h3>
        <p>
          {dataset.provider} · {dataset.instrument} · {dataset.product}. Results are precomputed by the project pipeline and
          served unchanged by the API.
        </p>
        <p>
          {dataset.reproducibility_url ? <a href={dataset.reproducibility_url} target="_blank" rel="noreferrer">Reproduce this series in NASA Giovanni</a> : null}
          {dataset.reproducibility_url && dataset.catalogue_url ? ' · ' : null}
          {dataset.catalogue_url ? <a href={dataset.catalogue_url} target="_blank" rel="noreferrer">Dataset page</a> : null}
        </p>
      </section>
      <section className={styles.source}>
        <h3>What this cannot tell you</h3>
        <ul className={styles.caveats}>
          {[...study.highlights.notices, ...limitations].map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
