import type { ElementEntry } from '../../api/types'
import styles from './Masthead.module.css'

interface Props {
  caseName: string
  elements: ElementEntry[]
}

export function Masthead({ caseName, elements }: Props) {
  return (
    <header className={styles.bar}>
      <nav aria-label="Breadcrumb" className={styles.crumbs}>
        <ol>
          <li>
            <span>{caseName}</span>
          </li>
          <li aria-current="page">Air — NO₂</li>
        </ol>
      </nav>
      <ul className={styles.elements} aria-label="Environmental elements for this case">
        {elements.map((element) => {
          const available = element.status === 'available'
          const current = element.element_id === 'air'
          return (
            <li
              key={element.element_id}
              className={styles.element}
              data-state={current ? 'current' : available ? 'available' : 'unavailable'}
            >
              <span>{element.label}</span>
              {available ? null : <span className={styles.soon}>not yet available</span>}
            </li>
          )
        })}
      </ul>
    </header>
  )
}
