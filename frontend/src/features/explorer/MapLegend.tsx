import { useId, useState } from 'react'
import styles from './MapLegend.module.css'

interface Props {
  airActive: boolean
  mapNote: string | null
}

/** "L Legend" toggle. Neutral state explains the interface; with Air active it explains the study marks. */
export function MapLegend({ airActive, mapNote }: Props) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <div className={styles.wrap}>
      <button type="button" className={styles.toggle} aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)} data-testid="legend-toggle">
        <span className={styles.l} aria-hidden="true">L</span>
        <span>Legend</span>
      </button>
      {open ? (
        <div id={id} role="region" aria-label="Legend" className={styles.panel} data-testid="legend">
          {airActive ? (
            <ul className={styles.list}>
              <li><span className={styles.boundary} aria-hidden="true" /> Study boundary: the box the Air numbers describe</li>
              <li><span className={styles.pin} aria-hidden="true" /> Selected-area marker: Kyiv · NO₂ study</li>
              {mapNote ? <li className={styles.note}>{mapNote}</li> : null}
            </ul>
          ) : (
            <ul className={styles.list}>
              <li><span className={styles.chip} aria-hidden="true">Air</span> Elements. Available ones open a study.</li>
              <li><span className={styles.chip} data-off aria-hidden="true">Fire</span> “Coming later” elements are not open yet.</li>
              <li>Drag to pan, scroll or use + / − to zoom.</li>
              <li>“Reset Ukraine view” returns to the country.</li>
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
