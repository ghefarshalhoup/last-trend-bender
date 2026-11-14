import { AvatarMark } from '../../components/Avatar/AvatarMark'
import styles from './GuideBubble.module.css'

/** Small map-corner guide. One or two sentences; the detailed narration lives in the study panel. */
export function GuideBubble({ text, accent }: { text: string; accent?: string }) {
  return (
    <aside className={styles.bubble} aria-label="Guide" data-testid="guide-bubble">
      <AvatarMark size={40} accent={accent} />
      <p className={styles.text}>{text}</p>
    </aside>
  )
}
