import type { ElementId, ElementView } from '../explorer/elements'
import { ELEMENT_ART, ElementGlyph } from './elementArt'
import styles from './ElementMedallions.module.css'

interface Props {
  elements: ElementView[]
  active: ElementId | null
  onSelect: (id: ElementId) => void
  onClear: () => void
}

/** Top-right element chooser: four medallions and a status line. */
export function ElementMedallions({ elements, active, onSelect, onClear }: Props) {
  const current = elements.find((e) => e.id === active)
  return (
    <section className={styles.panel} aria-label="Choose an element" data-testid="element-medallions">
      <div role="group" aria-label="Environmental elements" className={styles.grid}>
        {elements.map((el) => {
          const art = ELEMENT_ART[el.id]
          const selected = el.id === active
          return (
            <button
              key={el.id}
              type="button"
              className={styles.medallion}
              aria-pressed={selected}
              aria-disabled={!el.available}
              data-available={el.available}
              data-testid={`element-${el.id}`}
              style={{ '--light': art.light, '--deep': art.deep, '--ink': art.ink } as React.CSSProperties}
              onClick={() => {
                if (!el.available) return
                if (selected) onClear()
                else onSelect(el.id)
              }}
            >
              <span className={styles.disc}>
                <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
                  <ElementGlyph id={el.id} color={art.ink} />
                </svg>
              </span>
              <span className={styles.name}>{el.label}</span>
              {el.statusNote ? <span className={styles.note}>{el.statusNote}</span> : null}
            </button>
          )
        })}
      </div>
      <div className={styles.status} aria-live="polite">
        {current ? (
          <>
            <span data-testid="element-status">{current.label} selected</span>
            <button type="button" className={styles.clear} onClick={onClear} data-testid="clear-element">
              Clear
            </button>
          </>
        ) : (
          <span data-testid="element-status">No element selected</span>
        )}
      </div>
    </section>
  )
}
