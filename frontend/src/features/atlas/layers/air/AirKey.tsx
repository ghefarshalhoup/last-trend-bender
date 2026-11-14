import { SCALE_COLOURS } from './colourScale'
import styles from './AirLayer.module.css'

/** Fixed key: the scale and its labels never change with month or baseline. */
export function AirKey() {
  return (
    <div className={styles.key} data-testid="air-key" role="group" aria-label="Map key: NO₂ change against the baseline">
      <p className={styles.keyTitle}>2022 NO₂ against the baseline</p>
      <div className={styles.swatches} aria-hidden="true">
        {SCALE_COLOURS.map((c) => (
          <span key={c} style={{ background: c }} />
        ))}
      </div>
      <div className={styles.ticks} aria-hidden="true">
        <span>−50%</span>
        <span>−25%</span>
        <span>0</span>
        <span>+25%</span>
        <span>+50%</span>
      </div>
      <p className={styles.ends}>
        <span>Lower than baseline</span>
        <span>Higher</span>
      </p>
      <ul className={styles.keyList}>
        <li><span className={`${styles.chip} ${styles.chipHatch}`} aria-hidden="true" /> Low coverage: under half the days observed</li>
        <li><span className={`${styles.chip} ${styles.chipNone}`} aria-hidden="true" /> No value</li>
      </ul>
      <p className={styles.keyNote}>The box is one area average, drawn at its true size.</p>
    </div>
  )
}
