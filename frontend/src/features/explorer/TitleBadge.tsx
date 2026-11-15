import styles from './TitleBadge.module.css'

export function TitleBadge() {
  return (
    <div className={styles.badge}>
      <h1 className={styles.title}>Environmental Fingerprints of War</h1>
      <p className={styles.sub}>Ukraine, seen from space</p>
    </div>
  )
}
