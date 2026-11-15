import type { ElementView, ElementId } from './elements'
import styles from './ElementControls.module.css'

interface Props {
  elements: ElementView[]
  selected: ElementId | null
  onSelect: (id: ElementId) => void
  onClear: () => void
}

export function ElementControls({ elements, selected, onSelect, onClear }: Props) {
  return (
    <div className={styles.wrap}>
      <div role="group" aria-label="Environmental elements" className={styles.group}>
        {elements.map((el) => {
          const isSelected = el.id === selected
          return (
            <button
              key={el.id}
              type="button"
              className={styles.button}
              style={{ '--accent': el.accent, '--soft': el.soft } as React.CSSProperties}
              aria-pressed={isSelected}
              aria-disabled={!el.available}
              data-selected={isSelected}
              data-available={el.available}
              data-testid={`element-${el.id}`}
              onClick={() => {
                if (el.available) onSelect(el.id)
              }}
            >
              <span className={styles.dot} aria-hidden="true" />
              <span className={styles.label}>{el.label}</span>
              {el.statusNote ? <span className={styles.note}>{el.statusNote}</span> : null}
            </button>
          )
        })}
      </div>
      {selected ? (
        <button type="button" className={styles.clear} onClick={onClear} data-testid="clear-element">
          Clear element
        </button>
      ) : (
        <p className={styles.prompt} data-testid="choose-prompt">Choose an element to explore</p>
      )}
    </div>
  )
}
