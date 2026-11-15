import definitions from '../atlas/variableDefinitions.json'
import type { ElementId } from '../explorer/elements'
import { variablesOf, type VariableCatalog, type VariableEntry } from './catalog'
import styles from './VariableGuide.module.css'

const DEFS = new Map((definitions as { metric_id: string; definition: string; reading_hint: string }[]).map((d) => [d.metric_id, d]))

interface Props {
  catalog: VariableCatalog
  element: string | null
  elementLabel?: string
  openIds: string[]
  hasData: (v: VariableEntry) => boolean
}

/** The letter's first page: every variable of the chosen element in plain words. */
export function VariableGuide({ catalog, element, elementLabel, openIds, hasData }: Props) {
  if (!element) return <p className={styles.hint} data-testid="variable-guide-empty">Choose an element at the top right. Its variables and what they mean appear here.</p>
  const vars = variablesOf(catalog, element as ElementId)
  return (
    <div className={styles.guide} data-testid="variable-guide" data-element={element}>
      <p className={styles.lead}>{elementLabel}: {vars.length} variables. Definitions are drafts for review.</p>
      <dl className={styles.list}>
        {vars.map((v) => {
          const d = DEFS.get(v.metric_id)
          const open = openIds.includes(v.metric_id)
          const here = hasData(v)
          return (
            <div key={v.metric_id} className={styles.entry} data-testid={`define-${v.metric_id}`}>
              <dt>
                {v.short_label}
                {open ? <span className={styles.tag}>open as a card</span> : null}
                {!here ? <span className={`${styles.tag} ${styles.off}`}>not collected here</span> : null}
              </dt>
              <dd>{d?.definition ?? v.short_label}</dd>
              {d?.reading_hint ? <dd className={styles.read}>{d.reading_hint}</dd> : null}
            </div>
          )
        })}
      </dl>
    </div>
  )
}
