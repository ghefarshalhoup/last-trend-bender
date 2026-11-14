import { ABSENCE_EXPLANATION, ABSENCE_LABEL, type Absence } from '../../adapters/absence'
import styles from './Absence.module.css'

interface Props {
  kind: Absence
  /** Extra context from the field, e.g. "Before/after significance". */
  context?: string
  /** Replaces the default explanation when the API gave a specific reason. */
  reason?: string | null
}

/**
 * The one place a missing value is rendered. Three kinds, three labels, never a
 * zero. The word is always present so colour is never the only signal.
 */
export function AbsenceMark({ kind, context, reason }: Props) {
  const explanation = reason ?? ABSENCE_EXPLANATION[kind]
  return (
    <span className={`${styles.absence} ${styles[kind]}`} data-absence={kind} title={explanation}>
      <span className={styles.glyph} aria-hidden="true">
        {kind === 'missing_measurement' ? '∅' : kind === 'not_assessed' ? '–' : '⊘'}
      </span>
      <span>
        {context ? `${context}: ` : ''}
        {ABSENCE_LABEL[kind]}
      </span>
      <span className="sr-only">. {explanation}</span>
    </span>
  )
}
