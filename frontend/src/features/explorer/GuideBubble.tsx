import { AvatarMark } from '../../components/Avatar/AvatarMark'
import styles from './GuideBubble.module.css'

/** Small map-corner guide. One or two sentences; the detailed narration lives in the study panel. */
export function GuideBubble({ text, accent, action }: { text: string; accent?: string; action?: { label: string; onClick: () => void } }) {
  return (
    <aside className={styles.bubble} aria-label="Guide" data-testid="guide-bubble">
      <AvatarMark size={40} accent={accent} />
      <div className={styles.body}>
        <p className={styles.text} aria-live="polite">{text}</p>
        {action ? (
          <button type="button" className={styles.action} onClick={action.onClick} data-testid="guide-action">
            {action.label}
          </button>
        ) : null}
      </div>
    </aside>
  )
}
