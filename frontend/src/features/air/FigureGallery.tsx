import { useState } from 'react'
import { apiUrl } from '../../api/client'
import type { ChartLink } from '../../api/types'
import styles from './FigureGallery.module.css'

function Figure({ chart }: { chart: ChartLink }) {
  const [failed, setFailed] = useState(false)
  const href = apiUrl(chart.url)
  return (
    <li className={styles.item} data-testid={`figure-${chart.chart_id}`}>
      {failed ? (
        <div className={styles.fallback} role="note">
          <p><strong>{chart.title}</strong></p>
          <p>The preview did not load.</p>
          <a href={href} target="_blank" rel="noreferrer">Try opening the PNG directly</a>
        </div>
      ) : (
        <a href={href} target="_blank" rel="noreferrer" className={styles.thumb}>
          <img src={href} alt={`${chart.title} (supplementary figure from the analysis)`} loading="lazy" onError={() => setFailed(true)} />
        </a>
      )}
      <p className={styles.title}>{chart.title}</p>
    </li>
  )
}

/** Renders only the figures the API listed. Nothing is assumed to exist. */
export function FigureGallery({ charts }: { charts: ChartLink[] }) {
  if (charts.length === 0) {
    return (
      <p className={styles.empty} role="status" data-testid="figures-empty">
        No supplementary figures were returned for this study. The interactive chart above is built from the same measurements.
      </p>
    )
  }
  return (
    <ul className={styles.grid} data-testid="figures">
      {charts.map((chart) => (
        <Figure key={chart.chart_id} chart={chart} />
      ))}
    </ul>
  )
}
